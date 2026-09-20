from __future__ import annotations

import numpy as np
import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.forecast_inventory import _dataset_schema, _get_features, _sanitize
from app.core.auth import get_current_user
from app.core.database import get_db
from app.inventory.optimization import (
    InventoryPolicy,
    abc_analysis,
    combine_abc_xyz,
    compute_inventory,
    xyz_analysis,
)
from app.models.orm import User

router = APIRouter(prefix="/api", tags=["segmentation_alerts_simulation"])


@router.get("/analytics/abc-xyz")
async def get_abc_xyz(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    schema = _dataset_schema(db, dataset_id)
    store_col, item_col, sales_col = schema["store_col"], schema["item_col"], schema["sales_col"]
    features = _get_features(db, dataset_id, schema)

    per_sku = (
        features.groupby([store_col, item_col])
        .agg(annual_value=(sales_col, "sum"), demand_mean=(sales_col, "mean"), demand_std=(sales_col, "std"))
        .reset_index()
    )
    per_sku["cv"] = per_sku["demand_std"] / per_sku["demand_mean"].replace(0, np.nan)

    combined = combine_abc_xyz(xyz_analysis(abc_analysis(per_sku, value_col="annual_value"), cv_col="cv"))

    def quadrant(row):
        high_value = row["abc_class"] == "A"
        high_risk = row["xyz_class"] in ("Y", "Z")
        if high_value and high_risk:
            return "High Value + High Risk"
        if high_value and not high_risk:
            return "High Value + Low Risk"
        if not high_value and high_risk:
            return "Low Value + High Risk"
        return "Low Value + Low Risk"

    combined["priority_quadrant"] = combined.apply(quadrant, axis=1)

    return _sanitize({
        "dataset_id": dataset_id,
        "segments": combined[[store_col, item_col, "annual_value", "contribution_pct", "cumulative_pct",
                                "abc_class", "cv", "xyz_class", "segment", "priority_quadrant"]]
        .round(3).to_dict(orient="records"),
    })


@router.get("/alerts")
async def get_alerts(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    schema = _dataset_schema(db, dataset_id)
    store_col, item_col, sales_col = schema["store_col"], schema["item_col"], schema["sales_col"]
    features = _get_features(db, dataset_id, schema)

    alerts = []
    for (store_id, item_id), g in features.groupby([store_col, item_col]):
        recent = g[sales_col].tail(90)
        avg = float(recent.mean())
        std = float(recent.std()) if len(recent) > 1 else 0.0
        cv = std / avg if avg else 0.0

        last7 = g[sales_col].tail(7).mean()
        prior28 = g[sales_col].tail(35).head(28).mean() if len(g) >= 35 else np.nan
        if pd.notna(prior28) and prior28 > 0 and last7 > prior28 * 1.5:
            alerts.append({
                "type": "DEMAND_SPIKE", "severity": "MEDIUM", "store_id": int(store_id), "item_id": int(item_id),
                "message": f"Last 7-day average demand ({last7:.1f}) is {last7/prior28:.1f}x the prior 28-day average.",
            })
        if cv > 0.6:
            alerts.append({
                "type": "HIGH_VOLATILITY", "severity": "LOW", "store_id": int(store_id), "item_id": int(item_id),
                "message": f"Coefficient of variation is {cv:.2f}, indicating highly unpredictable demand.",
            })

    return _sanitize({
        "dataset_id": dataset_id,
        "alerts": alerts,
        "note": "Demand-based alerts (spike, volatility) are computed from real history. "
        "Stock-level alerts (low stock, stockout, overstock) require a real current_stock — "
        "use /api/inventory/optimize for those, per item.",
    })


@router.post("/scenarios/what-if")
async def what_if(
    dataset_id: int, store_id: int, item_id: int,
    lead_time_days: int = 7, service_level: float = 0.95,
    ordering_cost: float = 50.0, holding_cost_per_unit_per_year: float = 5.0,
    current_stock: float = 100.0, demand_growth_pct: float = 0.0,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    schema = _dataset_schema(db, dataset_id)
    store_col, item_col, sales_col = schema["store_col"], schema["item_col"], schema["sales_col"]
    features = _get_features(db, dataset_id, schema)

    history = features[(features[store_col] == store_id) & (features[item_col] == item_id)]
    if history.empty:
        raise HTTPException(status_code=404, detail="No history found for this store/item combination.")

    base_avg = float(history[sales_col].tail(90).mean())
    base_std = float(history[sales_col].tail(90).std())
    base_annual = float(history[sales_col].tail(365).sum()) if len(history) >= 30 else base_avg * 365

    base_policy = InventoryPolicy(
        lead_time_days=lead_time_days, service_level=service_level, ordering_cost=ordering_cost,
        holding_cost_per_unit_per_year=holding_cost_per_unit_per_year, current_stock=current_stock,
    )
    baseline_result = compute_inventory(base_avg, base_std, base_annual, base_policy)

    growth_factor = 1 + demand_growth_pct / 100.0
    scenario_result = compute_inventory(base_avg * growth_factor, base_std * growth_factor,
                                         base_annual * growth_factor, base_policy)

    return _sanitize({
        "dataset_id": dataset_id, "store_id": store_id, "item_id": item_id,
        "scenario": {"demand_growth_pct": demand_growth_pct, "lead_time_days": lead_time_days},
        "baseline": {"avg_daily_demand": round(base_avg, 2), **baseline_result.__dict__},
        "after_scenario": {"avg_daily_demand": round(base_avg * growth_factor, 2), **scenario_result.__dict__},
        "delta": {
            "safety_stock": round(scenario_result.safety_stock - baseline_result.safety_stock, 2),
            "reorder_point": round(scenario_result.reorder_point - baseline_result.reorder_point, 2),
            "suggested_order": round(scenario_result.suggested_order - baseline_result.suggested_order, 2),
        },
    })
