"""
AI Insights (spec §51) — a natural-language question interface that answers
ONLY from data this app has actually computed. This is intentionally a
deterministic intent router + real query execution, not a generative LLM
call: every fact returned traces directly to a computation elsewhere in
this codebase (inventory optimization, anomaly detection, demand behavior
profiling). This guarantees the "never fabricates data" requirement in the
spec, which a free-text LLM answer could not guarantee without a live,
grounded retrieval step of its own.
"""
from __future__ import annotations

import re

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

import joblib

from app.analytics.anomaly_detection import detect_anomalies
from app.api.forecast_inventory import _dataset_schema, _get_features, _sanitize
from app.core.auth import get_current_user
from app.core.database import get_db
from app.inventory.optimization import InventoryPolicy, abc_analysis, compute_inventory
from app.ml.explainability import business_friendly_explanation, compute_shap_values, local_explanation
from app.ml.features import demand_behavior_profile
from app.models.orm import ModelVersion, User

router = APIRouter(prefix="/api", tags=["ai_insights"])

DEFAULT_POLICY = dict(lead_time_days=7, service_level=0.95, ordering_cost=50.0,
                       holding_cost_per_unit_per_year=5.0)


def _all_sku_inventory(features: pd.DataFrame, store_col: str, item_col: str, sales_col: str,
                        assumed_current_stock_days: float = 10.0) -> pd.DataFrame:
    """Runs the real inventory formula for every SKU using an assumed
    current-stock level (documented, since no per-SKU stock table exists
    yet) so cross-SKU questions ('highest risk', 'what should we reorder')
    have something concrete to rank."""
    rows = []
    for (store_id, item_id), g in features.groupby([store_col, item_col]):
        avg = float(g[sales_col].tail(90).mean())
        std = float(g[sales_col].tail(90).std())
        annual = float(g[sales_col].tail(365).sum()) if len(g) >= 30 else avg * 365
        assumed_stock = avg * assumed_current_stock_days
        policy = InventoryPolicy(current_stock=assumed_stock, **DEFAULT_POLICY)
        result = compute_inventory(avg, std, annual, policy)
        rows.append({"store_id": int(store_id), "item_id": int(item_id), "avg_daily_demand": round(avg, 2),
                     "assumed_current_stock": round(assumed_stock, 2), **result.__dict__})
    return pd.DataFrame(rows)


INTENT_PATTERNS = [
    (re.compile(r"stockout|reorder|which (products|skus|items).*(risk|reorder)", re.I), "stockout_risk"),
    (re.compile(r"unusual|anomal|spike|collapse", re.I), "anomalies"),
    (re.compile(r"overstock|excess|declining", re.I), "overstock_declining"),
    (re.compile(r"explain.*forecast|why.*(demand|forecast).*(increase|decrease|change)", re.I), "explain_forecast"),
    (re.compile(r"top|best.?sell|highest value|most (valuable|important)", re.I), "top_value"),
    (re.compile(r"reorder", re.I), "reorder"),
]

_STORE_RE = re.compile(r"store\s*#?\s*(\d+)", re.I)
_ITEM_RE = re.compile(r"(?:item|sku|product)\s*#?\s*(\d+)", re.I)


def classify_intent(question: str) -> str:
    for pattern, intent in INTENT_PATTERNS:
        if pattern.search(question):
            return intent
    return "unknown"


@router.get("/insights/ask")
async def ask_ai_insights(dataset_id: int, question: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    schema = _dataset_schema(db, dataset_id)
    store_col, item_col, date_col, sales_col = (
        schema["store_col"], schema["item_col"], schema["date_col"], schema["sales_col"],
    )
    features = _get_features(db, dataset_id, schema)
    intent = classify_intent(question)

    if intent == "stockout_risk":
        inv = _all_sku_inventory(features, store_col, item_col, sales_col)
        risk_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
        inv["_rank"] = inv["stockout_risk"].map(risk_order)
        top = inv.sort_values("_rank").head(10).drop(columns="_rank")
        answer = (
            f"Based on an assumed {DEFAULT_POLICY['lead_time_days']}-day lead time and {int(DEFAULT_POLICY['service_level']*100)}% "
            f"service level, {len(inv[inv.stockout_risk.isin(['CRITICAL','HIGH'])])} of {len(inv)} SKUs are at "
            "HIGH or CRITICAL stockout risk. Top items shown below."
        )
        return _sanitize({"question": question, "intent": intent, "answer": answer, "data": top.round(2).to_dict(orient="records")})

    if intent == "anomalies":
        anomalies = detect_anomalies(features, store_col, item_col, date_col, sales_col, z_threshold=3.0).head(10)
        anomalies[date_col] = anomalies[date_col].astype(str)
        answer = (
            f"{len(anomalies)} statistically unusual sales events found (z-score ≥ 3 against each SKU's own "
            "trailing 28-day history). Listed by severity below." if len(anomalies) else
            "No statistically unusual sales events found at the current threshold."
        )
        return _sanitize({"question": question, "intent": intent, "answer": answer, "data": anomalies.round(2).to_dict(orient="records")})

    if intent == "overstock_declining":
        inv = _all_sku_inventory(features, store_col, item_col, sales_col, assumed_current_stock_days=25.0)
        profile = demand_behavior_profile(features, store_col, item_col, sales_col)
        merged = inv.merge(profile, on=[store_col, item_col], how="left")
        flagged = merged[(merged["overstock_risk"]) & (merged["trend_label"] == "Decreasing")]
        answer = (
            f"{len(flagged)} SKUs show both a potential overstock signal and a declining demand trend."
            if len(flagged) else "No SKUs currently show both overstock and a declining demand trend together."
        )
        return _sanitize({"question": question, "intent": intent, "answer": answer,
                           "data": flagged[[store_col, item_col, "assumed_current_stock", "avg_daily_demand",
                                            "trend_label", "demand_pattern"]].round(2).to_dict(orient="records")})

    if intent == "explain_forecast":
        store_match, item_match = _STORE_RE.search(question), _ITEM_RE.search(question)
        if not (store_match and item_match):
            return _sanitize({
                "question": question, "intent": intent,
                "answer": "To explain a forecast, mention both a store and an item/SKU number, "
                "e.g. 'Explain the forecast for store 1 item 3'.",
                "data": [],
            })
        store_id, item_id = int(store_match.group(1)), int(item_match.group(1))

        mv = db.query(ModelVersion).filter(ModelVersion.dataset_version_id == dataset_id).order_by(ModelVersion.trained_at.desc()).first()
        if mv is None:
            return _sanitize({"question": question, "intent": intent,
                               "answer": "No trained model exists yet for this dataset — train one on the Forecasting page first.",
                               "data": []})

        model = joblib.load(mv.model_artifact_path)
        row = features[(features[store_col] == store_id) & (features[item_col] == item_id)].dropna(subset=mv.feature_cols_json).tail(1)
        if row.empty:
            return _sanitize({"question": question, "intent": intent,
                               "answer": f"No feature-ready history found for store {store_id}, item {item_id}.",
                               "data": []})
        X = row[mv.feature_cols_json]
        point = float(max(0.0, model.predict(X)[0]))
        shap_values, _ = compute_shap_values(model, X)
        local = local_explanation(shap_values, mv.feature_cols_json, row_idx=0)
        explanation_text = business_friendly_explanation(local)
        return _sanitize({
            "question": question, "intent": intent,
            "answer": f"Forecast for store {store_id}, item {item_id}: {round(point, 2)} units. {explanation_text}",
            "data": local,
        })

    if intent == "top_value":
        per_sku = (
            features.groupby([store_col, item_col])[sales_col].sum().reset_index().rename(columns={sales_col: "annual_value"})
        )
        top = abc_analysis(per_sku, value_col="annual_value").head(10)
        answer = "Top 10 SKUs by total sales value in this dataset, with their contribution to overall value."
        return _sanitize({"question": question, "intent": intent, "answer": answer,
                           "data": top[[store_col, item_col, "annual_value", "contribution_pct", "abc_class"]].round(2).to_dict(orient="records")})

    return _sanitize({
        "question": question, "intent": "unknown",
        "answer": "This question isn't recognized yet. Supported question types: "
        "stockout/reorder risk, unusual demand (anomalies), overstock + declining demand, "
        "explain a forecast for a specific store/item, top-value products.",
        "data": [],
    })
