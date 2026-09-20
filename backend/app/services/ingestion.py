"""
Data Ingestion Engine (Module 1).

Responsibilities:
  - Detect date / store / item / sales columns from an uploaded CSV/XLSX.
  - Produce a data profiling report (counts, types, missingness, duplicates,
    outliers, invalid dates, negative sales, zero-sales rate).
  - Compute a documented Data Quality Score.
  - Run non-destructive cleaning and produce a full Data Transformation Log.

Nothing here fabricates numbers: every figure returned is computed directly
from the dataframe passed in.
"""
from __future__ import annotations

import dataclasses
from typing import Optional

import numpy as np
import pandas as pd

# --- Column detection -------------------------------------------------------

_DATE_CANDIDATES = {"date", "sale_date", "order_date", "day", "transaction_date"}
_STORE_CANDIDATES = {"store_id", "store", "storeid", "shop_id", "location_id"}
_ITEM_CANDIDATES = {"item_id", "item", "itemid", "sku", "product_id", "product"}
_SALES_CANDIDATES = {"sales", "quantity", "qty", "units_sold", "demand", "sales_qty"}


def _match_column(columns: list[str], candidates: set[str]) -> Optional[str]:
    lowered = {c.lower().strip(): c for c in columns}
    for cand in candidates:
        if cand in lowered:
            return lowered[cand]
    # fallback: substring match
    for col_lower, original in lowered.items():
        if any(cand in col_lower for cand in candidates):
            return original
    return None


@dataclasses.dataclass
class DetectedSchema:
    date_col: Optional[str]
    store_col: Optional[str]
    item_col: Optional[str]
    sales_col: Optional[str]

    @property
    def is_complete(self) -> bool:
        return all([self.date_col, self.store_col, self.item_col, self.sales_col])


def detect_schema(df: pd.DataFrame) -> DetectedSchema:
    columns = list(df.columns)
    return DetectedSchema(
        date_col=_match_column(columns, _DATE_CANDIDATES),
        store_col=_match_column(columns, _STORE_CANDIDATES),
        item_col=_match_column(columns, _ITEM_CANDIDATES),
        sales_col=_match_column(columns, _SALES_CANDIDATES),
    )


# --- Profiling ---------------------------------------------------------------

def profile_dataset(df: pd.DataFrame, schema: DetectedSchema) -> dict:
    """Computes every figure directly from df — nothing hardcoded."""
    n = len(df)
    report: dict = {
        "total_records": n,
        "columns": list(df.columns),
        "dtypes": {c: str(t) for c, t in df.dtypes.items()},
        "missing_values": {c: int(df[c].isna().sum()) for c in df.columns},
        "duplicate_rows": int(df.duplicated().sum()),
    }

    if schema.store_col:
        report["unique_stores"] = int(df[schema.store_col].nunique(dropna=True))
    if schema.item_col:
        report["unique_products"] = int(df[schema.item_col].nunique(dropna=True))

    if schema.date_col:
        parsed_dates = pd.to_datetime(df[schema.date_col], errors="coerce")
        invalid_dates = int(parsed_dates.isna().sum() - df[schema.date_col].isna().sum())
        report["invalid_dates"] = max(invalid_dates, 0)
        valid_dates = parsed_dates.dropna()
        if not valid_dates.empty:
            report["date_range"] = {
                "start": str(valid_dates.min().date()),
                "end": str(valid_dates.max().date()),
            }
        else:
            report["date_range"] = None

    if schema.sales_col:
        sales = pd.to_numeric(df[schema.sales_col], errors="coerce")
        non_null_sales = sales.dropna()
        report["negative_sales"] = int((non_null_sales < 0).sum())
        report["zero_sales_percentage"] = (
            round(float((non_null_sales == 0).mean() * 100), 2) if len(non_null_sales) else 0.0
        )
        report["outliers"] = _count_outliers_iqr(non_null_sales)
    else:
        report["negative_sales"] = None
        report["zero_sales_percentage"] = None
        report["outliers"] = None

    report["data_quality_score"], report["data_quality_breakdown"] = compute_quality_score(report, n)
    return report


def _count_outliers_iqr(series: pd.Series) -> int:
    if series.empty:
        return 0
    q1, q3 = series.quantile([0.25, 0.75])
    iqr = q3 - q1
    if iqr == 0:
        return 0
    lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return int(((series < lower) | (series > upper)).sum())


def compute_quality_score(report: dict, n: int) -> tuple[int, dict]:
    """
    Documented scoring formula (out of 100), each deduction proportional to
    the share of affected rows so the score is explainable, not arbitrary:

      - Missing values:      up to -25 points  (25 * missing_rate, capped)
      - Duplicate rows:       up to -20 points  (20 * duplicate_rate, capped)
      - Invalid dates:        up to -20 points  (20 * invalid_date_rate, capped)
      - Negative sales:       up to -20 points  (20 * negative_rate, capped)
      - Outliers:             up to -15 points  (15 * outlier_rate, capped)

    Each component's rate is (affected rows / total rows), capped at 1.0
    before multiplying, so a single component can never push the score
    below 0 on its own beyond its allotted weight.
    """
    if n == 0:
        return 0, {"note": "empty dataset"}

    total_missing = sum(report["missing_values"].values())
    missing_rate = min(total_missing / n, 1.0)
    duplicate_rate = min(report["duplicate_rows"] / n, 1.0)
    invalid_date_rate = min((report.get("invalid_dates") or 0) / n, 1.0)
    negative_rate = min((report.get("negative_sales") or 0) / n, 1.0)
    outlier_rate = min((report.get("outliers") or 0) / n, 1.0)

    deductions = {
        "missing_values": round(25 * missing_rate, 2),
        "duplicate_rows": round(20 * duplicate_rate, 2),
        "invalid_dates": round(20 * invalid_date_rate, 2),
        "negative_sales": round(20 * negative_rate, 2),
        "outliers": round(15 * outlier_rate, 2),
    }
    score = max(0, round(100 - sum(deductions.values())))
    breakdown = {
        "base_score": 100,
        "deductions": deductions,
        "final_score": score,
    }
    return score, breakdown


# --- Cleaning (non-destructive, fully logged) --------------------------------

@dataclasses.dataclass
class CleaningResult:
    cleaned_df: pd.DataFrame
    flagged_rows: pd.DataFrame  # rows that were altered/removed, for inspection
    transformation_log: list[dict]


def clean_dataset(df: pd.DataFrame, schema: DetectedSchema) -> CleaningResult:
    """Every transformation is logged with a count and a description. No
    transformation happens silently."""
    log: list[dict] = []
    flagged_frames: list[pd.DataFrame] = []
    working = df.copy()

    # 1. Duplicate rows
    dup_mask = working.duplicated()
    n_dupes = int(dup_mask.sum())
    if n_dupes:
        flagged_frames.append(working.loc[dup_mask].assign(_issue="duplicate_row"))
        working = working.loc[~dup_mask].copy()
    log.append({"step": "remove_duplicates", "count": n_dupes})

    # 2. Date parsing / invalid dates
    n_invalid_dates = 0
    if schema.date_col:
        parsed = pd.to_datetime(working[schema.date_col], errors="coerce")
        invalid_mask = parsed.isna() & working[schema.date_col].notna()
        n_invalid_dates = int(invalid_mask.sum())
        if n_invalid_dates:
            flagged_frames.append(working.loc[invalid_mask].assign(_issue="invalid_date"))
            working = working.loc[~invalid_mask].copy()
            parsed = parsed.loc[working.index]
        working[schema.date_col] = parsed
    log.append({"step": "parse_and_validate_dates", "invalid_records_removed": n_invalid_dates})

    # 3. Missing sales values -> flagged, not silently imputed
    n_missing_sales = 0
    if schema.sales_col:
        missing_mask = working[schema.sales_col].isna()
        n_missing_sales = int(missing_mask.sum())
        if n_missing_sales:
            flagged_frames.append(working.loc[missing_mask].assign(_issue="missing_sales"))
    log.append({"step": "flag_missing_sales", "count": n_missing_sales,
                "action": "flagged for review, not auto-imputed"})

    # 4. Negative sales -> invalid records, flagged and removed from the
    #    modeling-ready set (kept in flagged_rows for inspection)
    n_negative = 0
    if schema.sales_col:
        neg_mask = pd.to_numeric(working[schema.sales_col], errors="coerce") < 0
        n_negative = int(neg_mask.sum())
        if n_negative:
            flagged_frames.append(working.loc[neg_mask].assign(_issue="negative_sales"))
            working = working.loc[~neg_mask].copy()
    log.append({"step": "remove_negative_sales", "count": n_negative})

    # 5. Outlier detection (IQR) -> flagged only, kept in the dataset
    n_outliers = 0
    if schema.sales_col:
        sales_numeric = pd.to_numeric(working[schema.sales_col], errors="coerce")
        q1, q3 = sales_numeric.quantile([0.25, 0.75])
        iqr = q3 - q1
        if iqr > 0:
            lower, upper = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            outlier_mask = (sales_numeric < lower) | (sales_numeric > upper)
            n_outliers = int(outlier_mask.sum())
            if n_outliers:
                flagged_frames.append(working.loc[outlier_mask].assign(_issue="outlier_sales"))
    log.append({"step": "flag_outliers_iqr", "count": n_outliers,
                "action": "flagged for review, retained in dataset"})

    # 6. Chronological sort by store/item/date
    if schema.date_col and schema.store_col and schema.item_col:
        working = working.sort_values([schema.store_col, schema.item_col, schema.date_col])
        log.append({"step": "chronological_sort", "sorted_by": [schema.store_col, schema.item_col, schema.date_col]})

    flagged_rows = (
        pd.concat(flagged_frames, ignore_index=True) if flagged_frames else pd.DataFrame()
    )

    return CleaningResult(
        cleaned_df=working.reset_index(drop=True),
        flagged_rows=flagged_rows,
        transformation_log=log,
    )
