"""
Generates a clearly-labeled SYNTHETIC demo dataset matching the academic
schema: Date, Store ID, Item ID, Sales — 10 stores x 50 items x 5 years
(2013-2017), ~913,000 daily records, with intentionally injected data-quality
issues (missing values, duplicates, negative sales, outliers) so the
ingestion/profiling module has something real to detect.

This is DEMO DATA ONLY. It must never be presented as the real project
dataset — the ingestion API tags every dataset_version with is_demo=True
when it originates from this generator.
"""
import numpy as np
import pandas as pd
from pathlib import Path

RNG = np.random.default_rng(42)

N_STORES = 10
N_ITEMS = 50
START_DATE = "2013-01-01"
END_DATE = "2017-12-31"


def base_demand(store_id: int, item_id: int, dates: pd.DatetimeIndex) -> np.ndarray:
    """Deterministic-ish synthetic demand: trend + weekly seasonality +
    yearly seasonality + store/item-specific level + noise."""
    n = len(dates)
    t = np.arange(n)

    store_level = 8 + (store_id % N_STORES) * 1.7
    item_level = 3 + (item_id % N_ITEMS) * 0.35

    trend = t * (0.0006 + 0.00005 * (item_id % 5))

    day_of_week = dates.dayofweek.values
    weekly = 3.0 * np.sin(2 * np.pi * day_of_week / 7) + (day_of_week >= 5) * 2.5

    day_of_year = dates.dayofyear.values
    yearly = 5.0 * np.sin(2 * np.pi * day_of_year / 365.25 + item_id * 0.1)

    noise = RNG.normal(0, 1.8, size=n)

    demand = store_level + item_level + trend + weekly + yearly + noise
    return np.clip(demand, 0, None)


def generate() -> pd.DataFrame:
    dates = pd.date_range(START_DATE, END_DATE, freq="D")
    rows = []
    for store_id in range(1, N_STORES + 1):
        for item_id in range(1, N_ITEMS + 1):
            demand = base_demand(store_id, item_id, dates)
            sales = RNG.poisson(demand).astype(float)
            rows.append(
                pd.DataFrame(
                    {
                        "date": dates,
                        "store_id": store_id,
                        "item_id": item_id,
                        "sales": sales,
                    }
                )
            )
    df = pd.concat(rows, ignore_index=True)
    return df


def inject_quality_issues(df: pd.DataFrame) -> pd.DataFrame:
    """Injects realistic, known issues so the profiling/cleaning module has
    ground truth to detect (used for demo + tests)."""
    df = df.copy()
    n = len(df)

    # Missing sales values (~0.05%)
    missing_idx = RNG.choice(n, size=int(n * 0.0005), replace=False)
    df.loc[missing_idx, "sales"] = np.nan

    # Negative sales (data entry errors, ~0.01%)
    neg_idx = RNG.choice(n, size=int(n * 0.0001), replace=False)
    df.loc[neg_idx, "sales"] = -RNG.integers(1, 10, size=len(neg_idx))

    # Outlier spikes (~0.02%)
    outlier_idx = RNG.choice(n, size=int(n * 0.0002), replace=False)
    df.loc[outlier_idx, "sales"] = df.loc[outlier_idx, "sales"] * RNG.integers(15, 40, size=len(outlier_idx))

    # Duplicate rows (~0.03%)
    dup_idx = RNG.choice(n, size=int(n * 0.0003), replace=False)
    dup_rows = df.loc[dup_idx]
    df = pd.concat([df, dup_rows], ignore_index=True)

    # Shuffle so duplicates/issues aren't trivially at the end
    df = df.sample(frac=1.0, random_state=42).reset_index(drop=True)
    return df


def main():
    out_dir = Path(__file__).resolve().parents[1] / "data" / "demo"
    out_dir.mkdir(parents=True, exist_ok=True)

    df = generate()
    df = inject_quality_issues(df)

    out_path = out_dir / "retail_sales_demo.csv"
    df.to_csv(out_path, index=False)
    print(f"Wrote {len(df):,} rows to {out_path}")
    print(df.describe(include="all"))


if __name__ == "__main__":
    main()
