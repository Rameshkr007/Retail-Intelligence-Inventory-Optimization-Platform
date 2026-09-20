"""
Smart Business Recommendation Engine (spec §52). Converts real computed
signals (stockout/overstock risk, anomalies, model drift) into structured
actions — never a generic "everything is fine" filler, and never an
unsupported financial claim (no invented cost-savings numbers).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.analytics.anomaly_detection import detect_anomalies
from app.api.forecast_inventory import _dataset_schema, _get_features, _sanitize
from app.api.model_registry import MONITORING_MAE_THRESHOLD
from app.core.auth import get_current_user
from app.core.database import get_db
from app.inventory.optimization import InventoryPolicy, compute_inventory
from app.models.orm import ModelVersion, User

router = APIRouter(prefix="/api", tags=["recommendations"])

DEFAULT_POLICY = dict(lead_time_days=7, service_level=0.95, ordering_cost=50.0, holding_cost_per_unit_per_year=5.0)


@router.get("/recommendations")
async def get_recommendations(dataset_id: int, limit: int = 20, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    schema = _dataset_schema(db, dataset_id)
    store_col, item_col, date_col, sales_col = (
        schema["store_col"], schema["item_col"], schema["date_col"], schema["sales_col"],
    )
    features = _get_features(db, dataset_id, schema)

    recommendations = []

    for (store_id, item_id), g in features.groupby([store_col, item_col]):
        avg = float(g[sales_col].tail(90).mean())
        std = float(g[sales_col].tail(90).std())
        annual = float(g[sales_col].tail(365).sum()) if len(g) >= 30 else avg * 365
        assumed_stock = avg * 10
        policy = InventoryPolicy(current_stock=assumed_stock, **DEFAULT_POLICY)
        result = compute_inventory(avg, std, annual, policy)

        if result.stockout_risk in ("HIGH", "CRITICAL"):
            recommendations.append({
                "action": "Reorder",
                "reason": f"Store {store_id}, Item {item_id} is at {result.stockout_risk} stockout risk.",
                "evidence": {"reorder_point": result.reorder_point, "suggested_order": result.suggested_order,
                              "assumed_current_stock": round(assumed_stock, 2)},
                "priority": "HIGH" if result.stockout_risk == "CRITICAL" else "MEDIUM",
                "expected_impact": "Reduces risk of lost sales from a stockout, based on the computed reorder point.",
            })
        if result.overstock_risk:
            recommendations.append({
                "action": "Reduce excess inventory",
                "reason": f"Store {store_id}, Item {item_id} shows a potential overstock signal.",
                "evidence": {"assumed_current_stock": round(assumed_stock, 2), "avg_daily_demand": round(avg, 2)},
                "priority": "LOW",
                "expected_impact": "May reduce holding cost — exact savings depend on your actual holding cost rate.",
            })

    anomalies = detect_anomalies(features, store_col, item_col, date_col, sales_col, z_threshold=3.0).head(10)
    for _, row in anomalies.iterrows():
        recommendations.append({
            "action": "Investigate demand anomaly",
            "reason": f"Store {int(row[store_col])}, Item {int(row[item_col])} showed a "
                      f"{'spike' if row['anomaly_type']=='SPIKE' else 'collapse'} in sales on {row[date_col]}.",
            "evidence": {"observed_sales": float(row[sales_col]), "expected_sales": float(row["expected_sales"]),
                          "anomaly_score": float(row["anomaly_score"])},
            "priority": "MEDIUM",
            "expected_impact": "Confirms whether this reflects a real demand shift, a data error, or a one-off event.",
        })

    latest_model = db.query(ModelVersion).filter(ModelVersion.dataset_version_id == dataset_id).order_by(ModelVersion.trained_at.desc()).first()
    if latest_model and (latest_model.test_metrics_json.get("mae") or 0) > MONITORING_MAE_THRESHOLD:
        recommendations.append({
            "action": "Retrain forecasting model",
            "reason": f"Latest model's test MAE ({latest_model.test_metrics_json.get('mae'):.2f}) exceeds the "
                      f"configured threshold ({MONITORING_MAE_THRESHOLD}).",
            "evidence": {"model_version_id": latest_model.id, "test_mae": latest_model.test_metrics_json.get("mae")},
            "priority": "MEDIUM",
            "expected_impact": "Improves forecast accuracy, which flows through to inventory calculations.",
        })

    priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    recommendations.sort(key=lambda r: priority_order.get(r["priority"], 3))

    return _sanitize({
        "dataset_id": dataset_id,
        "recommendation_count": len(recommendations),
        "recommendations": recommendations[:limit],
        "note": "Every recommendation traces to a computed signal (risk calculation, anomaly detection, or "
        "model monitoring) above. No unsupported financial claims — 'expected impact' describes direction, not a dollar figure.",
    })


@router.get("/models/compare")
async def compare_models(model_version_ids: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Experiment comparison (spec §35): pass comma-separated ids, e.g. ?model_version_ids=1,2"""
    ids = [int(x) for x in model_version_ids.split(",") if x.strip()]
    versions = db.query(ModelVersion).filter(ModelVersion.id.in_(ids)).all()
    rows = [
        {
            "model_version_id": v.id, "dataset_version_id": v.dataset_version_id, "algorithm": v.algorithm,
            "status": v.status, "trained_at": v.trained_at.isoformat(), "horizon": v.horizon,
            "val_metrics": v.val_metrics_json, "test_metrics": v.test_metrics_json,
        }
        for v in versions
    ]
    return _sanitize({"compared": rows})
