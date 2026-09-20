from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.forecast_inventory import _dataset_schema, _get_features, _sanitize
from app.core.auth import get_current_user
from app.core.database import get_db
from app.inventory.optimization import InventoryPolicy, compute_inventory
from app.ml.features import demand_behavior_profile
from app.models.orm import User

router = APIRouter(prefix="/api", tags=["scenario_planning_insights"])

# Documented, fixed scenario definitions (spec §24) — demand_growth_pct and
# lead_time_multiplier are business assumptions, not fitted from data.
SCENARIOS = {
    "BASELINE": {"demand_growth_pct": 0.0, "lead_time_multiplier": 1.0},
    "HIGH_DEMAND": {"demand_growth_pct": 30.0, "lead_time_multiplier": 1.0},
    "LOW_DEMAND": {"demand_growth_pct": -25.0, "lead_time_multiplier": 1.0},
    "PROMOTIONAL_SPIKE": {"demand_growth_pct": 60.0, "lead_time_multiplier": 1.0},
    "SUPPLY_DELAY": {"demand_growth_pct": 0.0, "lead_time_multiplier": 2.0},
}


@router.get("/scenarios/planning")
async def scenario_planning(
    dataset_id: int, store_id: int, item_id: int,
    lead_time_days: int = 7, service_level: float = 0.95,
    ordering_cost: float = 50.0, holding_cost_per_unit_per_year: float = 5.0,
    current_stock: float = 100.0,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Compares inventory requirements across 5 standard business scenarios
    (spec §24) using the same real demand history and inventory formulas as
    /api/inventory/optimize — no separate/fabricated logic per scenario."""
    schema = _dataset_schema(db, dataset_id)
    store_col, item_col, sales_col = schema["store_col"], schema["item_col"], schema["sales_col"]
    features = _get_features(db, dataset_id, schema)

    history = features[(features[store_col] == store_id) & (features[item_col] == item_id)]
    if history.empty:
        raise HTTPException(status_code=404, detail="No history found for this store/item combination.")

    base_avg = float(history[sales_col].tail(90).mean())
    base_std = float(history[sales_col].tail(90).std())
    base_annual = float(history[sales_col].tail(365).sum()) if len(history) >= 30 else base_avg * 365

    results = {}
    for name, params in SCENARIOS.items():
        growth_factor = 1 + params["demand_growth_pct"] / 100.0
        scenario_lead_time = round(lead_time_days * params["lead_time_multiplier"])
        policy = InventoryPolicy(
            lead_time_days=scenario_lead_time, service_level=service_level, ordering_cost=ordering_cost,
            holding_cost_per_unit_per_year=holding_cost_per_unit_per_year, current_stock=current_stock,
        )
        result = compute_inventory(base_avg * growth_factor, base_std * growth_factor, base_annual * growth_factor, policy)
        results[name] = {
            "assumptions": params,
            "forecast_demand": round(base_avg * growth_factor, 2),
            "lead_time_days": scenario_lead_time,
            **result.__dict__,
        }

    return _sanitize({
        "dataset_id": dataset_id, "store_id": store_id, "item_id": item_id,
        "scenarios": results,
        "note": "Scenario growth/lead-time multipliers are fixed documented business assumptions "
        "(spec section 24), not derived from historical promotional data unless such data exists.",
    })


@router.get("/analytics/demand-behavior")
async def get_demand_behavior(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Per-SKU Demand Behavior Profile (spec §8) — pattern, trend, stability,
    all derived from the same feature table used for forecasting."""
    schema = _dataset_schema(db, dataset_id)
    store_col, item_col, sales_col = schema["store_col"], schema["item_col"], schema["sales_col"]
    features = _get_features(db, dataset_id, schema)

    profile = demand_behavior_profile(features, store_col, item_col, sales_col)
    return _sanitize({"dataset_id": dataset_id, "profiles": profile.round(3).to_dict(orient="records")})
