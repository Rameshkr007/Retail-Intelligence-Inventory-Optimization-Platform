"""
Isolated unit tests — pure functions only, no API/DB/model training. These
verify the actual math (Safety Stock, ROP, EOQ, forecast metrics, ABC/XYZ
classification, inventory health score) matches hand-computed expectations.
Run with: python3 tests/test_formulas_unit.py
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import pandas as pd

from app.inventory.optimization import (
    InventoryPolicy,
    abc_analysis,
    compute_inventory,
    inventory_health_score,
    xyz_analysis,
)
from app.ml.forecasting import compute_metrics


def test_safety_stock_formula():
    # Safety Stock = z * sigma_D * sqrt(L); z(0.95) = 1.6449
    policy = InventoryPolicy(lead_time_days=9, service_level=0.95, ordering_cost=10, holding_cost_per_unit_per_year=2, current_stock=0)
    result = compute_inventory(avg_daily_demand=10, demand_std=3, annual_demand=3650, policy=policy)
    expected_safety_stock = 1.6449 * 3 * math.sqrt(9)
    assert abs(result.safety_stock - round(expected_safety_stock, 2)) < 0.05, result.safety_stock
    print(f"safety_stock OK: {result.safety_stock} ≈ {expected_safety_stock:.2f}")


def test_reorder_point_formula():
    policy = InventoryPolicy(lead_time_days=5, service_level=0.90, ordering_cost=10, holding_cost_per_unit_per_year=2, current_stock=0)
    result = compute_inventory(avg_daily_demand=20, demand_std=4, annual_demand=7300, policy=policy)
    lead_time_demand = 20 * 5
    expected_rop = lead_time_demand + result.safety_stock
    assert abs(result.reorder_point - round(expected_rop, 2)) < 0.05
    print(f"reorder_point OK: {result.reorder_point} == lead_time_demand({lead_time_demand}) + safety_stock({result.safety_stock})")


def test_eoq_formula():
    # EOQ = sqrt(2*D*S/H)
    policy = InventoryPolicy(lead_time_days=7, service_level=0.95, ordering_cost=50, holding_cost_per_unit_per_year=5, current_stock=0)
    result = compute_inventory(avg_daily_demand=10, demand_std=2, annual_demand=3650, policy=policy)
    expected_eoq = math.sqrt(2 * 3650 * 50 / 5)
    assert abs(result.eoq - round(expected_eoq, 2)) < 0.5, (result.eoq, expected_eoq)
    print(f"eoq OK: {result.eoq} ≈ {expected_eoq:.2f}")


def test_eoq_zero_holding_cost_no_division_error():
    policy = InventoryPolicy(lead_time_days=7, service_level=0.95, ordering_cost=50, holding_cost_per_unit_per_year=0, current_stock=0)
    result = compute_inventory(avg_daily_demand=10, demand_std=2, annual_demand=3650, policy=policy)
    assert result.eoq == 0.0
    print("eoq zero-holding-cost edge case OK (no ZeroDivisionError, returns 0.0)")


def test_stockout_risk_classification():
    policy = InventoryPolicy(lead_time_days=7, service_level=0.95, ordering_cost=50, holding_cost_per_unit_per_year=5, current_stock=1000)
    result = compute_inventory(10, 2, 3650, policy)
    assert result.stockout_risk == "LOW", result.stockout_risk

    policy2 = InventoryPolicy(lead_time_days=7, service_level=0.95, ordering_cost=50, holding_cost_per_unit_per_year=5, current_stock=1)
    result2 = compute_inventory(10, 2, 3650, policy2)
    assert result2.stockout_risk == "CRITICAL", result2.stockout_risk
    print("stockout_risk classification OK: high stock -> LOW, near-zero stock -> CRITICAL")


def test_forecast_metrics_known_values():
    y_true = np.array([10, 20, 30, 40])
    y_pred = np.array([12, 18, 33, 36])
    m = compute_metrics(y_true, y_pred)
    expected_mae = np.mean([2, 2, 3, 4])
    assert abs(m.mae - expected_mae) < 1e-9, (m.mae, expected_mae)
    expected_bias = np.mean([2, -2, 3, -4])
    assert abs(m.bias - expected_bias) < 1e-9
    print(f"forecast metrics OK: MAE={m.mae:.3f} (expected {expected_mae:.3f}), bias={m.bias:.3f} (expected {expected_bias:.3f})")


def test_metrics_perfect_prediction_is_zero_error():
    y = np.array([5, 10, 15])
    m = compute_metrics(y, y)
    assert m.mae == 0 and m.rmse == 0 and m.wape == 0
    print("perfect-prediction edge case OK: MAE/RMSE/WAPE all 0")


def test_abc_classification_pareto():
    df = pd.DataFrame({"sku": ["A", "B", "C", "D"], "annual_value": [800, 150, 40, 10]})
    result = abc_analysis(df, value_col="annual_value")
    a_class = result[result["sku"] == "A"]["abc_class"].iloc[0]
    assert a_class == "A", a_class  # 800/1000 = 80% cumulative, at the A cutoff
    d_class = result[result["sku"] == "D"]["abc_class"].iloc[0]
    assert d_class == "C", d_class
    print("ABC classification OK: dominant-value SKU -> A, smallest -> C")


def test_xyz_classification_by_cv():
    df = pd.DataFrame({"sku": ["X", "Y", "Z"], "cv": [0.1, 0.7, 1.5]})
    result = xyz_analysis(df, cv_col="cv")
    assert result[result.sku == "X"]["xyz_class"].iloc[0] == "X"
    assert result[result.sku == "Y"]["xyz_class"].iloc[0] == "Y"
    assert result[result.sku == "Z"]["xyz_class"].iloc[0] == "Z"
    print("XYZ classification OK: low/medium/high CV map to X/Y/Z respectively")


def test_inventory_health_score_bounds():
    perfect = inventory_health_score("LOW", False, 0.0, 10, 7)
    assert perfect["score"] == 100, perfect
    worst = inventory_health_score("CRITICAL", True, 2.0, 50, 7)
    assert worst["score"] < perfect["score"]
    assert 0 <= worst["score"] <= 100
    print(f"inventory_health_score OK: best case=100, degraded case={worst['score']} (bounded 0-100)")


if __name__ == "__main__":
    tests = [v for k, v in list(globals().items()) if k.startswith("test_")]
    for t in tests:
        t()
    print(f"\nALL {len(tests)} ISOLATED FORMULA UNIT TESTS PASSED")
