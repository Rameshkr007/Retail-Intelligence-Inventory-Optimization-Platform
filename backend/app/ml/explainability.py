from __future__ import annotations

import numpy as np
import pandas as pd
import shap


def compute_shap_values(model, X: pd.DataFrame):
    explainer = shap.TreeExplainer(model)
    shap_values = explainer.shap_values(X)
    return shap_values, explainer.expected_value


def global_feature_importance(shap_values: np.ndarray, feature_cols: list[str]) -> pd.DataFrame:
    mean_abs = np.abs(shap_values).mean(axis=0)
    out = pd.DataFrame({"feature": feature_cols, "mean_abs_shap": mean_abs})
    return out.sort_values("mean_abs_shap", ascending=False).reset_index(drop=True)


def local_explanation(shap_values: np.ndarray, feature_cols: list[str], row_idx: int, top_n: int = 5) -> list[dict]:
    row_shap = shap_values[row_idx]
    order = np.argsort(-np.abs(row_shap))[:top_n]
    return [
        {"feature": feature_cols[i], "shap_value": float(row_shap[i]), "direction": "increase" if row_shap[i] > 0 else "decrease"}
        for i in order
    ]


_FRIENDLY_NAMES = {
    "rolling_mean_7": "recent 7-day average demand",
    "rolling_mean_28": "recent 28-day average demand",
    "lag_7": "demand one week ago",
    "lag_1": "demand the previous day",
    "is_weekend": "weekend effect",
    "trend_slope": "recent demand trend",
    "demand_volatility": "demand volatility",
    "month": "seasonal (monthly) pattern",
    "day_of_week": "day-of-week pattern",
}


def business_friendly_explanation(local_expl: list[dict]) -> str:
    """Converts the top SHAP drivers into a plain-language sentence. Never
    states a cause the model output doesn't actually support."""
    if not local_expl:
        return "No dominant driver was identified for this forecast."

    increases = [e for e in local_expl if e["direction"] == "increase"]
    decreases = [e for e in local_expl if e["direction"] == "decrease"]

    def name(e):
        return _FRIENDLY_NAMES.get(e["feature"], e["feature"].replace("_", " "))

    parts = []
    if increases:
        parts.append("mainly because " + " and ".join(name(e) for e in increases[:2]) + " pushed demand up")
    if decreases:
        parts.append(("while " if increases else "mainly because ") + " and ".join(name(e) for e in decreases[:2]) + " pulled demand down")

    return "Forecast changed " + ", ".join(parts) + "."
