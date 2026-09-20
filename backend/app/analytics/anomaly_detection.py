"""
Statistical anomaly detection on actual sales history (not simulated).

Method: for each (store, item), compute a rolling z-score of daily sales
against a trailing 28-day window (mean/std), flagging points beyond a
configurable threshold. This is a documented, explainable statistical
method — not a black-box "AI anomaly" claim.
"""
from __future__ import annotations

import numpy as np
import pandas as pd


def detect_anomalies(
    df: pd.DataFrame,
    store_col: str,
    item_col: str,
    date_col: str,
    sales_col: str,
    window: int = 28,
    z_threshold: float = 3.0,
) -> pd.DataFrame:
    df = df.sort_values([store_col, item_col, date_col]).copy()

    grouped = df.groupby([store_col, item_col])[sales_col]
    rolling_mean = grouped.transform(lambda s: s.shift(1).rolling(window, min_periods=10).mean())
    rolling_std = grouped.transform(lambda s: s.shift(1).rolling(window, min_periods=10).std())

    df["expected_sales"] = rolling_mean
    df["z_score"] = (df[sales_col] - rolling_mean) / rolling_std.replace(0, np.nan)

    anomalies = df[df["z_score"].abs() >= z_threshold].copy()
    anomalies["anomaly_type"] = np.where(anomalies["z_score"] > 0, "SPIKE", "COLLAPSE")
    anomalies["anomaly_score"] = anomalies["z_score"].abs().round(2)

    return anomalies[[store_col, item_col, date_col, sales_col, "expected_sales", "anomaly_score", "anomaly_type"]].sort_values(
        "anomaly_score", ascending=False
    )
