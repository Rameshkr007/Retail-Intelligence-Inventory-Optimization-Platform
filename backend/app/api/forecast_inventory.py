from __future__ import annotations

import joblib
import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from pathlib import Path

from app.api.datasets import load_cleaned_df
from app.core.auth import get_current_user
from app.core.database import get_db
from app.inventory.optimization import InventoryPolicy, compute_inventory, inventory_health_score
from app.ml.features import build_feature_set
from app.models.orm import AuditLog, InventoryRecommendation, ModelVersion, User

router = APIRouter(prefix="/api", tags=["forecast_inventory"])

ARTIFACT_DIR = Path(__file__).resolve().parents[3] / "ml" / "artifacts"
ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)

# In-memory cache of the built feature set + loaded model per dataset_id, so
# repeated /forecast calls in the same process don't re-run feature
# engineering every time. The model itself is always persisted to disk +
# referenced from the DB (ModelVersion row), so it survives a restart —
# this cache is purely a performance optimization, not the source of truth.
_FEATURE_CACHE: dict[int, pd.DataFrame] = {}


def _sanitize(obj):
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize(v) for v in obj]
    if isinstance(obj, (np.floating, float)) and (np.isnan(obj) or np.isinf(obj)):
        return None
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


def _get_features(db: Session, dataset_id: int, schema: dict) -> pd.DataFrame:
    if dataset_id in _FEATURE_CACHE:
        return _FEATURE_CACHE[dataset_id]
    df, _ = load_cleaned_df(db, dataset_id)
    df[schema["date_col"]] = pd.to_datetime(df[schema["date_col"]])
    features = build_feature_set(df, schema["date_col"], schema["store_col"], schema["item_col"], schema["sales_col"])
    features = features.dropna(subset=[c for c in features.columns if c.startswith("lag_")])
    features = features.dropna(subset=[schema["sales_col"]])
    _FEATURE_CACHE[dataset_id] = features
    return features


def _latest_model_version(db: Session, dataset_id: int) -> ModelVersion:
    mv = (
        db.query(ModelVersion)
        .filter(ModelVersion.dataset_version_id == dataset_id)
        .order_by(ModelVersion.trained_at.desc())
        .first()
    )
    if mv is None:
        raise HTTPException(status_code=400, detail="Model not trained for this dataset yet. Call /api/models/train first.")
    return mv


@router.post("/models/train")
async def train_model(
    dataset_id: int, horizon: int = 14,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    from app.ml.forecasting import BASELINES, compute_metrics, time_based_split, train_lightgbm

    df, schema = load_cleaned_df(db, dataset_id)
    date_col, store_col, item_col, sales_col = (
        schema["date_col"], schema["store_col"], schema["item_col"], schema["sales_col"],
    )
    df[date_col] = pd.to_datetime(df[date_col])

    features = build_feature_set(df, date_col, store_col, item_col, sales_col)
    features = features.dropna(subset=[c for c in features.columns if c.startswith("lag_")])
    features = features.dropna(subset=[sales_col])
    _FEATURE_CACHE[dataset_id] = features

    train, val, test = time_based_split(features, date_col, val_days=90, test_days=horizon)
    if len(train) == 0 or len(val) == 0 or len(test) == 0:
        raise HTTPException(status_code=422, detail="Not enough history for a train/val/test split at this horizon.")

    model, feature_cols = train_lightgbm(train, val, sales_col)

    val_pred = np.clip(model.predict(val[feature_cols]), 0, None)
    val_metrics = compute_metrics(val[sales_col].values, val_pred)
    residual_std = float(np.std(val[sales_col].values - val_pred))

    test_pred = np.clip(model.predict(test[feature_cols]), 0, None)
    test_metrics = compute_metrics(test[sales_col].values, test_pred)

    baseline_metrics = {}
    for name, fn in BASELINES.items():
        preds, actuals = [], []
        for (_, _), g in test.groupby([store_col, item_col]):
            train_g = train[(train[store_col] == g[store_col].iloc[0]) & (train[item_col] == g[item_col].iloc[0])]
            if len(train_g) < 10:
                continue
            pred = fn(train_g[sales_col], len(g))
            preds.extend(pred[: len(g)])
            actuals.extend(g[sales_col].values)
        if preds:
            baseline_metrics[name] = compute_metrics(np.array(actuals), np.array(preds)).as_dict()

    model_version = ModelVersion(
        dataset_version_id=dataset_id,
        algorithm="LightGBM",
        status="Validated",
        horizon=horizon,
        train_range={"start": str(train[date_col].min().date()), "end": str(train[date_col].max().date())},
        val_range={"start": str(val[date_col].min().date()), "end": str(val[date_col].max().date())},
        test_range={"start": str(test[date_col].min().date()), "end": str(test[date_col].max().date())},
        val_metrics_json=_sanitize(val_metrics.as_dict()),
        test_metrics_json=_sanitize(test_metrics.as_dict()),
        baseline_metrics_json=_sanitize(baseline_metrics),
        model_artifact_path="",
        feature_cols_json=feature_cols,
        residual_std=residual_std,
    )
    db.add(model_version)
    db.commit()
    db.refresh(model_version)

    artifact_path = ARTIFACT_DIR / f"model_{model_version.id}.joblib"
    joblib.dump(model, artifact_path)
    model_version.model_artifact_path = str(artifact_path)
    db.add(AuditLog(user_email=user.email, action="model_train", entity=f"model_version:{model_version.id}",
                     metadata_json={"dataset_id": dataset_id, "horizon": horizon}))
    db.commit()

    return _sanitize({
        "dataset_id": dataset_id,
        "model_version_id": model_version.id,
        "model": "LightGBM",
        "train_range": model_version.train_range,
        "val_range": model_version.val_range,
        "test_range": model_version.test_range,
        "val_metrics": val_metrics.as_dict(),
        "test_metrics": test_metrics.as_dict(),
        "baseline_comparison": baseline_metrics,
        "note": "All metrics computed from actual walk-forward evaluation on this dataset. "
        "LightGBM remains the primary production model per project spec; baselines shown for comparison only.",
    })


@router.get("/forecast")
async def get_forecast(
    dataset_id: int, store_id: int, item_id: int,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    from app.ml.explainability import business_friendly_explanation, compute_shap_values, local_explanation
    from app.ml.forecasting import predict_with_uncertainty

    model_version = _latest_model_version(db, dataset_id)
    model = joblib.load(model_version.model_artifact_path)
    feature_cols = model_version.feature_cols_json

    features = _get_features(db, dataset_id, _dataset_schema(db, dataset_id))
    schema = _dataset_schema(db, dataset_id)
    store_col, item_col = schema["store_col"], schema["item_col"]

    row = features[(features[store_col] == store_id) & (features[item_col] == item_id)].dropna(
        subset=feature_cols
    ).tail(1)
    if row.empty:
        raise HTTPException(status_code=404, detail="No feature-ready history found for this store/item combination.")

    X = row[feature_cols]
    pred_df = predict_with_uncertainty(model, X, model_version.residual_std)

    shap_values, _ = compute_shap_values(model, X)
    local = local_explanation(shap_values, feature_cols, row_idx=0)
    explanation_text = business_friendly_explanation(local)

    return _sanitize({
        "dataset_id": dataset_id,
        "model_version_id": model_version.id,
        "store_id": store_id,
        "item_id": item_id,
        "horizon": model_version.horizon,
        "point_forecast": round(float(pred_df["point"].iloc[0]), 2),
        "lower_bound": round(float(pred_df["lower"].iloc[0]), 2),
        "upper_bound": round(float(pred_df["upper"].iloc[0]), 2),
        "top_drivers": local,
        "explanation": explanation_text,
    })


def _dataset_schema(db: Session, dataset_id: int) -> dict:
    from app.api.datasets import _get_version_or_404
    return _get_version_or_404(db, dataset_id).schema_json


@router.get("/models/{dataset_id}/feature-importance")
async def feature_importance(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from app.ml.explainability import compute_shap_values, global_feature_importance

    model_version = _latest_model_version(db, dataset_id)
    model = joblib.load(model_version.model_artifact_path)
    feature_cols = model_version.feature_cols_json
    schema = _dataset_schema(db, dataset_id)
    features = _get_features(db, dataset_id, schema)

    sample = features.dropna(subset=feature_cols).sample(min(500, len(features)), random_state=42)
    shap_values, _ = compute_shap_values(model, sample[feature_cols])
    importance = global_feature_importance(shap_values, feature_cols)
    return _sanitize({"dataset_id": dataset_id, "model_version_id": model_version.id,
                       "global_feature_importance": importance.to_dict(orient="records")})


@router.post("/inventory/optimize")
async def optimize_inventory(
    dataset_id: int, store_id: int, item_id: int,
    lead_time_days: int = 7, service_level: float = 0.95,
    ordering_cost: float = 50.0, holding_cost_per_unit_per_year: float = 5.0,
    current_stock: float = 100.0, min_order_qty: float = 0.0,
    max_stock_capacity: float | None = None,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    schema = _dataset_schema(db, dataset_id)
    store_col, item_col, sales_col = schema["store_col"], schema["item_col"], schema["sales_col"]
    features = _get_features(db, dataset_id, schema)

    history = features[(features[store_col] == store_id) & (features[item_col] == item_id)]
    if history.empty:
        raise HTTPException(status_code=404, detail="No history found for this store/item combination.")

    avg_daily_demand = float(history[sales_col].tail(90).mean())
    demand_std = float(history[sales_col].tail(90).std())
    annual_demand = float(history[sales_col].tail(365).sum()) if len(history) >= 30 else avg_daily_demand * 365

    policy = InventoryPolicy(
        lead_time_days=lead_time_days, service_level=service_level, ordering_cost=ordering_cost,
        holding_cost_per_unit_per_year=holding_cost_per_unit_per_year, current_stock=current_stock,
        min_order_qty=min_order_qty, max_stock_capacity=max_stock_capacity,
    )
    result = compute_inventory(avg_daily_demand, demand_std, annual_demand, policy)
    cv = (demand_std / avg_daily_demand) if avg_daily_demand else None
    days_of_inventory = (current_stock / avg_daily_demand) if avg_daily_demand else None
    health = inventory_health_score(result.stockout_risk, result.overstock_risk, cv, days_of_inventory, lead_time_days)

    rec = InventoryRecommendation(
        dataset_version_id=dataset_id, store_id=store_id, item_id=item_id,
        safety_stock=result.safety_stock, reorder_point=result.reorder_point, eoq=result.eoq,
        suggested_order=result.suggested_order, stockout_risk=result.stockout_risk,
        overstock_risk=result.overstock_risk, reason=result.reason,
    )
    db.add(rec)
    db.commit()

    return _sanitize({
        "dataset_id": dataset_id, "store_id": store_id, "item_id": item_id,
        "avg_daily_demand": round(avg_daily_demand, 2), "demand_std": round(demand_std, 2),
        "annual_demand": round(annual_demand, 2), **result.__dict__,
        "inventory_health_score": health,
    })
