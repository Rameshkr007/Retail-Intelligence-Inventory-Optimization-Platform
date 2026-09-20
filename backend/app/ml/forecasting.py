from __future__ import annotations

import dataclasses

import lightgbm as lgb
import numpy as np
import pandas as pd

FEATURE_COLS = [
    "year", "month", "quarter", "week", "day", "day_of_week", "is_weekend",
    "is_month_start", "is_month_end",
    *[f"lag_{l}" for l in [1, 2, 3, 7, 14, 21, 28, 30, 60, 90]],
    "rolling_mean_7", "rolling_mean_14", "rolling_mean_28", "rolling_mean_30",
    "rolling_std_7", "rolling_std_28", "rolling_min_28", "rolling_max_28", "rolling_median_28",
    "demand_volatility", "coefficient_of_variation", "trend_slope", "recent_growth_rate",
    "intermittent_demand_indicator", "demand_stability_score",
]


@dataclasses.dataclass
class EvalMetrics:
    mae: float
    rmse: float
    mape: float
    smape: float
    wape: float
    bias: float

    def as_dict(self) -> dict:
        return dataclasses.asdict(self)


def compute_metrics(y_true: np.ndarray, y_pred: np.ndarray) -> EvalMetrics:
    y_true = np.asarray(y_true, dtype=float)
    y_pred = np.asarray(y_pred, dtype=float)
    err = y_pred - y_true
    abs_err = np.abs(err)

    mae = float(np.mean(abs_err))
    rmse = float(np.sqrt(np.mean(err ** 2)))
    bias = float(np.mean(err))

    nonzero = y_true != 0
    mape = float(np.mean(abs_err[nonzero] / np.abs(y_true[nonzero])) * 100) if nonzero.any() else float("nan")

    denom = np.abs(y_true) + np.abs(y_pred)
    smape_terms = np.where(denom == 0, 0, abs_err / denom)
    smape = float(np.mean(smape_terms) * 200)

    wape = float(np.sum(abs_err) / np.sum(np.abs(y_true))) * 100 if np.sum(np.abs(y_true)) > 0 else float("nan")

    return EvalMetrics(mae=mae, rmse=rmse, mape=mape, smape=smape, wape=wape, bias=bias)


def time_based_split(df: pd.DataFrame, date_col: str, val_days: int = 90, test_days: int = 90):
    """Strict chronological split — never random — for time-series evaluation."""
    max_date = df[date_col].max()
    test_start = max_date - pd.Timedelta(days=test_days - 1)
    val_start = test_start - pd.Timedelta(days=val_days)

    train = df[df[date_col] < val_start]
    val = df[(df[date_col] >= val_start) & (df[date_col] < test_start)]
    test = df[df[date_col] >= test_start]
    return train, val, test


# ---- Baselines --------------------------------------------------------------

def naive_forecast(train_target: pd.Series, horizon: int) -> np.ndarray:
    last_value = train_target.iloc[-1]
    return np.full(horizon, last_value)


def seasonal_naive_forecast(train_target: pd.Series, horizon: int, season: int = 7) -> np.ndarray:
    tail = train_target.iloc[-season:].values
    reps = int(np.ceil(horizon / season))
    return np.tile(tail, reps)[:horizon]


def moving_average_forecast(train_target: pd.Series, horizon: int, window: int = 28) -> np.ndarray:
    avg = train_target.iloc[-window:].mean()
    return np.full(horizon, avg)


def exponential_smoothing_forecast(train_target: pd.Series, horizon: int, alpha: float = 0.3) -> np.ndarray:
    level = train_target.iloc[0]
    for v in train_target.iloc[1:]:
        level = alpha * v + (1 - alpha) * level
    return np.full(horizon, level)


BASELINES = {
    "naive": naive_forecast,
    "seasonal_naive": seasonal_naive_forecast,
    "moving_average": moving_average_forecast,
    "exponential_smoothing": exponential_smoothing_forecast,
}


# ---- LightGBM (primary production model) ------------------------------------

def train_lightgbm(train: pd.DataFrame, val: pd.DataFrame, target_col: str, feature_cols: list[str] | None = None):
    feature_cols = feature_cols or [c for c in FEATURE_COLS if c in train.columns]
    X_train, y_train = train[feature_cols], train[target_col]
    X_val, y_val = val[feature_cols], val[target_col]

    model = lgb.LGBMRegressor(
        objective="regression",
        n_estimators=1000,
        learning_rate=0.05,
        num_leaves=63,
        subsample=0.8,
        colsample_bytree=0.8,
        random_state=42,
        verbosity=-1,
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="l1",
        callbacks=[lgb.early_stopping(50, verbose=False)],
    )
    return model, feature_cols


def predict_with_uncertainty(model, X: pd.DataFrame, residual_std: float, z: float = 1.28) -> pd.DataFrame:
    """Uncertainty bounds derived from the model's own residual std on the
    validation set (≈80% interval at z=1.28) — not an arbitrary +/-X%."""
    point = model.predict(X)
    point = np.clip(point, 0, None)
    lower = np.clip(point - z * residual_std, 0, None)
    upper = point + z * residual_std
    return pd.DataFrame({"point": point, "lower": lower, "upper": upper})
