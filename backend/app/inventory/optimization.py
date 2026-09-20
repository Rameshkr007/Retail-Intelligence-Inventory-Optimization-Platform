from __future__ import annotations

import dataclasses

import numpy as np
import pandas as pd

# z-scores for common service levels (standard normal inverse CDF)
SERVICE_LEVEL_Z = {0.90: 1.2816, 0.95: 1.6449, 0.975: 1.9600, 0.99: 2.3263}


@dataclasses.dataclass
class InventoryPolicy:
    lead_time_days: int
    service_level: float
    ordering_cost: float
    holding_cost_per_unit_per_year: float
    current_stock: float
    min_order_qty: float = 0.0
    max_stock_capacity: float | None = None


@dataclasses.dataclass
class InventoryResult:
    safety_stock: float
    reorder_point: float
    eoq: float
    lead_time_demand: float
    suggested_order: float
    stockout_risk: str
    overstock_risk: bool
    reason: str


def _z_for_service_level(service_level: float) -> float:
    if service_level in SERVICE_LEVEL_Z:
        return SERVICE_LEVEL_Z[service_level]
    # nearest documented value rather than fabricating precision
    closest = min(SERVICE_LEVEL_Z, key=lambda k: abs(k - service_level))
    return SERVICE_LEVEL_Z[closest]


def compute_inventory(
    avg_daily_demand: float,
    demand_std: float,
    annual_demand: float,
    policy: InventoryPolicy,
) -> InventoryResult:
    z = _z_for_service_level(policy.service_level)
    lead_time_demand = avg_daily_demand * policy.lead_time_days

    # Safety Stock = z * sigma_D * sqrt(L)
    safety_stock = z * demand_std * np.sqrt(policy.lead_time_days)

    # Reorder Point = Lead-Time Demand + Safety Stock
    reorder_point = lead_time_demand + safety_stock

    # EOQ = sqrt(2 * D * S / H)
    if policy.holding_cost_per_unit_per_year > 0 and annual_demand > 0:
        eoq = float(np.sqrt(2 * annual_demand * policy.ordering_cost / policy.holding_cost_per_unit_per_year))
    else:
        eoq = 0.0

    target_stock = reorder_point + eoq
    suggested_order = max(0.0, target_stock - policy.current_stock)
    if policy.min_order_qty and 0 < suggested_order < policy.min_order_qty:
        suggested_order = policy.min_order_qty
    if policy.max_stock_capacity is not None:
        suggested_order = min(suggested_order, max(0.0, policy.max_stock_capacity - policy.current_stock))

    # Stockout risk classification
    if policy.current_stock < safety_stock:
        stockout_risk = "CRITICAL"
        reason = "Current stock is below the calculated safety stock level."
    elif policy.current_stock < reorder_point:
        stockout_risk = "HIGH"
        reason = "Current stock has fallen below the reorder point."
    elif policy.current_stock < reorder_point * 1.25:
        stockout_risk = "MEDIUM"
        reason = "Current stock is approaching the reorder point."
    else:
        stockout_risk = "LOW"
        reason = "Current stock comfortably exceeds the reorder point."

    days_of_inventory = policy.current_stock / avg_daily_demand if avg_daily_demand > 0 else float("inf")
    overstock_risk = days_of_inventory > (policy.lead_time_days + (safety_stock / avg_daily_demand if avg_daily_demand > 0 else 0)) * 3
    if overstock_risk:
        reason += " Current inventory is well above expected demand for the lead time plus safety buffer."

    return InventoryResult(
        safety_stock=round(safety_stock, 2),
        reorder_point=round(reorder_point, 2),
        eoq=round(eoq, 2),
        lead_time_demand=round(lead_time_demand, 2),
        suggested_order=round(suggested_order, 2),
        stockout_risk=stockout_risk,
        overstock_risk=bool(overstock_risk),
        reason=reason,
    )


# ---- ABC / XYZ segmentation --------------------------------------------------

def abc_analysis(df: pd.DataFrame, value_col: str, a_cutoff: float = 0.80, b_cutoff: float = 0.95) -> pd.DataFrame:
    out = df.sort_values(value_col, ascending=False).copy()
    total = out[value_col].sum()
    out["contribution_pct"] = out[value_col] / total * 100 if total > 0 else 0
    out["cumulative_pct"] = out["contribution_pct"].cumsum()

    def classify(cum):
        if cum <= a_cutoff * 100:
            return "A"
        if cum <= b_cutoff * 100:
            return "B"
        return "C"

    out["abc_class"] = out["cumulative_pct"].apply(classify)
    return out


def xyz_analysis(df: pd.DataFrame, cv_col: str, x_cutoff: float = 0.5, y_cutoff: float = 1.0) -> pd.DataFrame:
    out = df.copy()

    def classify(cv):
        if pd.isna(cv):
            return "Unknown"
        if cv <= x_cutoff:
            return "X"
        if cv <= y_cutoff:
            return "Y"
        return "Z"

    out["xyz_class"] = out[cv_col].apply(classify)
    return out


def combine_abc_xyz(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out["segment"] = out["abc_class"] + "-" + out["xyz_class"]
    return out


# ---- Inventory Health Score (spec §17) -------------------------------------

RISK_PENALTY = {"LOW": 0, "MEDIUM": 15, "HIGH": 30, "CRITICAL": 45}


def inventory_health_score(
    stockout_risk: str,
    overstock_risk: bool,
    demand_cv: float | None,
    days_of_inventory: float | None,
    lead_time_days: float,
) -> dict:
    """
    Documented, explainable composite score (0-100, higher is healthier):
      - Start at 100
      - Stockout risk: -0/-15/-30/-45 (LOW/MEDIUM/HIGH/CRITICAL)
      - Overstock risk: -15 if flagged
      - Demand volatility: -min(20, cv*20) — higher CV = higher deduction, capped at 20
      - Days-of-inventory imbalance: -10 if days_of_inventory > 3x lead time
        (excess) or < 0.5x lead time (dangerously low) — a rough tail check
        beyond what stockout/overstock risk already capture
    Every deduction traces to a real computed input; nothing is arbitrary.
    """
    deductions = {"stockout_risk": RISK_PENALTY.get(stockout_risk, 0)}
    deductions["overstock_risk"] = 15 if overstock_risk else 0
    cv = demand_cv if demand_cv is not None and not np.isnan(demand_cv) else 0.0
    deductions["demand_volatility"] = round(min(20, cv * 20), 2)

    doi_penalty = 0
    if days_of_inventory is not None and not np.isnan(days_of_inventory) and lead_time_days > 0:
        if days_of_inventory > lead_time_days * 3:
            doi_penalty = 10
        elif days_of_inventory < lead_time_days * 0.5:
            doi_penalty = 10
    deductions["days_of_inventory_imbalance"] = doi_penalty

    score = max(0, round(100 - sum(deductions.values())))
    return {"score": score, "deductions": deductions}
