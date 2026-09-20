"""
Module 2 — Feature Engineering (leakage-safe).

All lag/rolling features for a (store, item) group at time t use only data
with timestamp <= t (lags) or a shift(1) before the rolling window (rolling),
so no future information ever leaks into a feature.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

LAGS = [1, 2, 3, 7, 14, 21, 28, 30, 60, 90]
ROLLING_WINDOWS = [7, 14, 28, 30]


def add_calendar_features(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    df = df.copy()
    d = df[date_col]
    df["year"] = d.dt.year
    df["month"] = d.dt.month
    df["quarter"] = d.dt.quarter
    df["week"] = d.dt.isocalendar().week.astype(int)
    df["day"] = d.dt.day
    df["day_of_week"] = d.dt.dayofweek
    df["is_weekend"] = (df["day_of_week"] >= 5).astype(int)
    df["day_of_month"] = d.dt.day
    df["week_of_year"] = df["week"]
    df["is_month_start"] = d.dt.is_month_start.astype(int)
    df["is_month_end"] = d.dt.is_month_end.astype(int)
    return df


def add_lag_features(df: pd.DataFrame, group_cols: list[str], date_col: str, target_col: str) -> pd.DataFrame:
    df = df.sort_values(group_cols + [date_col]).copy()
    grouped = df.groupby(group_cols)[target_col]
    for lag in LAGS:
        df[f"lag_{lag}"] = grouped.shift(lag)
    return df


def add_rolling_features(df: pd.DataFrame, group_cols: list[str], date_col: str, target_col: str) -> pd.DataFrame:
    df = df.sort_values(group_cols + [date_col]).copy()
    # shift(1) first so the rolling window never includes the current row
    shifted = df.groupby(group_cols)[target_col].shift(1)
    df["_shifted_target"] = shifted
    g = df.groupby(group_cols)["_shifted_target"]
    for w in ROLLING_WINDOWS:
        df[f"rolling_mean_{w}"] = g.transform(lambda s: s.rolling(w, min_periods=max(2, w // 2)).mean())
    df["rolling_std_7"] = g.transform(lambda s: s.rolling(7, min_periods=3).std())
    df["rolling_std_28"] = g.transform(lambda s: s.rolling(28, min_periods=5).std())
    df["rolling_min_28"] = g.transform(lambda s: s.rolling(28, min_periods=5).min())
    df["rolling_max_28"] = g.transform(lambda s: s.rolling(28, min_periods=5).max())
    df["rolling_median_28"] = g.transform(lambda s: s.rolling(28, min_periods=5).median())
    df = df.drop(columns=["_shifted_target"])
    return df


def add_demand_behavior_features(df: pd.DataFrame, group_cols: list[str], target_col: str) -> pd.DataFrame:
    """Per-SKU (store+item) summary behavior — computed from historical data
    only (expanding stats up to each row), not from the full series at once,
    to avoid leakage when used as a training feature."""
    df = df.copy()
    grouped = df.groupby(group_cols)[target_col]

    expanding_mean = grouped.transform(lambda s: s.shift(1).expanding(min_periods=5).mean())
    expanding_std = grouped.transform(lambda s: s.shift(1).expanding(min_periods=5).std())

    df["demand_volatility"] = expanding_std
    df["coefficient_of_variation"] = (expanding_std / expanding_mean.replace(0, np.nan))

    # trend slope: recent 28d rolling mean minus prior 28d rolling mean (shifted)
    shifted = grouped.transform(lambda s: s.shift(1))
    g = df.assign(_s=shifted).groupby(group_cols)["_s"]
    recent = g.transform(lambda s: s.rolling(28, min_periods=5).mean())
    prior = g.transform(lambda s: s.shift(28).rolling(28, min_periods=5).mean())
    df["trend_slope"] = (recent - prior) / 28.0
    df["recent_growth_rate"] = ((recent - prior) / prior.replace(0, np.nan))

    df["intermittent_demand_indicator"] = grouped.transform(
        lambda s: s.shift(1).rolling(28, min_periods=5).apply(lambda x: (x == 0).mean())
    )
    df["demand_stability_score"] = 1 - df["coefficient_of_variation"].clip(0, 1).fillna(1)
    return df


def build_feature_set(
    df: pd.DataFrame,
    date_col: str,
    store_col: str,
    item_col: str,
    target_col: str,
) -> pd.DataFrame:
    group_cols = [store_col, item_col]
    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col])
    df = add_calendar_features(df, date_col)
    df = add_lag_features(df, group_cols, date_col, target_col)
    df = add_rolling_features(df, group_cols, date_col, target_col)
    df = add_demand_behavior_features(df, group_cols, target_col)
    return df


def demand_behavior_profile(df_features: pd.DataFrame, store_col: str, item_col: str, target_col: str) -> pd.DataFrame:
    """Latest-row snapshot per (store, item) — the 'Demand Behavior Profile'
    surfaced in the UI (spec section 8)."""
    latest = (
        df_features.sort_values([store_col, item_col, "year", "month", "day"])
        .groupby([store_col, item_col])
        .tail(1)
    )
    out = latest[[store_col, item_col, "demand_volatility", "coefficient_of_variation",
                   "trend_slope", "recent_growth_rate", "demand_stability_score",
                   "intermittent_demand_indicator"]].copy()

    def pattern(cv):
        if pd.isna(cv):
            return "Unknown"
        return "High Volatility" if cv > 0.5 else ("Moderate Volatility" if cv > 0.25 else "Stable")

    def trend(g):
        if pd.isna(g):
            return "Unknown"
        return "Increasing" if g > 0.05 else ("Decreasing" if g < -0.05 else "Flat")

    out["demand_pattern"] = out["coefficient_of_variation"].apply(pattern)
    out["trend_label"] = out["recent_growth_rate"].apply(trend)
    return out.reset_index(drop=True)
