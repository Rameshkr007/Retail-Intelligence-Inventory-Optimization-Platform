"""
Full-stack backend integration test: register -> login -> upload dataset
(persisted to DB + parquet on disk) -> train model (persisted ModelVersion +
joblib artifact) -> forecast + SHAP -> inventory optimize (persisted
recommendation) -> ABC-XYZ -> alerts -> what-if -> model registry ->
reports (CSV/XLSX/PDF). Uses SQLite fallback so it runs without a live
Postgres server; the same code path works against Postgres via DATABASE_URL.
"""
import json
import os
import sys
from pathlib import Path

os.environ["RETAIL_DB_FALLBACK_SQLITE"] = "1"

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Remove any stale sqlite db from a previous run for a clean test
db_path = Path(__file__).resolve().parents[1] / "retail_intelligence.db"
if db_path.exists():
    db_path.unlink()

from fastapi.testclient import TestClient  # noqa: E402
from app.main import app  # noqa: E402

client = TestClient(app)
with client:
    pass  # triggers the startup event (init_db) once, outside the `with` below too
DEMO_PATH = Path(__file__).resolve().parents[2] / "data" / "demo" / "retail_sales_demo.csv"


def auth_headers():
    resp = client.post("/api/auth/register", json={"email": "ramesh@example.com", "password": "password123", "role": "admin"})
    assert resp.status_code == 200, resp.text
    login = client.post("/api/auth/login", json={"email": "ramesh@example.com", "password": "password123"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def main():
    headers = auth_headers()
    print("Auth OK — token acquired")

    me = client.get("/api/auth/me", headers=headers)
    assert me.status_code == 200
    print("Whoami:", me.json())

    df = pd.read_csv(DEMO_PATH)
    subset = df[df["store_id"].isin([1, 2, 3]) & df["item_id"].isin([1, 2, 3, 4, 5])].copy()
    subset_path = Path("/tmp/retail_subset.csv")
    subset.to_csv(subset_path, index=False)

    with open(subset_path, "rb") as f:
        resp = client.post("/api/datasets/upload", files={"file": ("retail_subset.csv", f, "text/csv")},
                            params={"is_demo": True}, headers=headers)
    assert resp.status_code == 200, resp.text
    dataset_id = resp.json()["dataset_id"]
    print("\nUploaded + persisted dataset_id =", dataset_id, "| quality score:", resp.json()["profiling_report"]["data_quality_score"])

    # confirm it's actually in the DB by listing datasets
    listed = client.get("/api/datasets", headers=headers)
    assert listed.status_code == 200 and any(d["dataset_id"] == dataset_id for d in listed.json())
    print("Confirmed persisted in dataset list:", listed.json())

    train_resp = client.post("/api/models/train", params={"dataset_id": dataset_id, "horizon": 14}, headers=headers)
    assert train_resp.status_code == 200, train_resp.text
    print("\n--- TRAINING ---")
    print(json.dumps(train_resp.json(), indent=2, default=str))

    forecast_resp = client.get("/api/forecast", params={"dataset_id": dataset_id, "store_id": 1, "item_id": 1}, headers=headers)
    assert forecast_resp.status_code == 200, forecast_resp.text
    print("\n--- FORECAST ---")
    print(json.dumps(forecast_resp.json(), indent=2, default=str))

    inv_resp = client.post("/api/inventory/optimize", params={
        "dataset_id": dataset_id, "store_id": 1, "item_id": 1, "lead_time_days": 7,
        "service_level": 0.95, "ordering_cost": 50, "holding_cost_per_unit_per_year": 5, "current_stock": 40,
    }, headers=headers)
    assert inv_resp.status_code == 200, inv_resp.text
    print("\n--- INVENTORY ---")
    print(json.dumps(inv_resp.json(), indent=2, default=str))

    abcxyz_resp = client.get("/api/analytics/abc-xyz", params={"dataset_id": dataset_id}, headers=headers)
    assert abcxyz_resp.status_code == 200, abcxyz_resp.text
    print("\n--- ABC-XYZ (first 3) ---")
    print(json.dumps(abcxyz_resp.json()["segments"][:3], indent=2, default=str))

    alerts_resp = client.get("/api/alerts", params={"dataset_id": dataset_id}, headers=headers)
    assert alerts_resp.status_code == 200, alerts_resp.text
    print("\n--- ALERTS ---", len(alerts_resp.json()["alerts"]), "found")

    whatif_resp = client.post("/api/scenarios/what-if", params={
        "dataset_id": dataset_id, "store_id": 1, "item_id": 1, "current_stock": 40, "demand_growth_pct": 40,
    }, headers=headers)
    assert whatif_resp.status_code == 200, whatif_resp.text
    print("\n--- WHAT-IF (+40%) ---")
    print(json.dumps(whatif_resp.json()["delta"], indent=2, default=str))

    registry_resp = client.get("/api/models/registry", headers=headers)
    assert registry_resp.status_code == 200, registry_resp.text
    print("\n--- MODEL REGISTRY ---")
    print(json.dumps(registry_resp.json(), indent=2, default=str))

    csv_resp = client.get("/api/reports/forecast.csv", params={"dataset_id": dataset_id}, headers=headers)
    assert csv_resp.status_code == 200, csv_resp.text
    print("\nforecast.csv report bytes:", len(csv_resp.content))

    xlsx_resp = client.get("/api/reports/inventory.xlsx", params={"dataset_id": dataset_id}, headers=headers)
    assert xlsx_resp.status_code == 200, xlsx_resp.text
    print("inventory.xlsx report bytes:", len(xlsx_resp.content))

    pdf_resp = client.get("/api/reports/executive.pdf", params={"dataset_id": dataset_id}, headers=headers)
    assert pdf_resp.status_code == 200, pdf_resp.text
    print("executive.pdf report bytes:", len(pdf_resp.content))

    # confirm the sqlite file now actually contains rows -> real persistence
    import sqlite3
    conn = sqlite3.connect(db_path)
    counts = {}
    for table in ["users", "dataset_versions", "model_versions", "inventory_recommendations", "audit_logs"]:
        counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    conn.close()
    print("\n--- DB ROW COUNTS (proof of persistence) ---")
    print(counts)
    assert all(v > 0 for v in counts.values())

    print("\nFULL STACK BACKEND PIPELINE PASSED END TO END")


if __name__ == "__main__":
    main()
