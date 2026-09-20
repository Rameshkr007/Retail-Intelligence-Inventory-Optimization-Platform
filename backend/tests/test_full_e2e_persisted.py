"""
Full end-to-end test exercising the ENTIRE backend: registration/login (JWT),
dataset upload persisted to DB+disk, LightGBM training persisted as a
ModelVersion + joblib artifact, forecast+SHAP, inventory optimization
persisted as InventoryRecommendation, ABC-XYZ, alerts, what-if simulator,
model registry/monitoring, and report generation (CSV/XLSX/PDF).

Uses SQLite (RETAIL_DB_FALLBACK_SQLITE=1) so it runs without a provisioned
PostgreSQL server; the same code path works against Postgres via
DATABASE_URL in production (see docker-compose.yml).
"""
import json
import os
import sys
from pathlib import Path

os.environ["RETAIL_DB_FALLBACK_SQLITE"] = "1"
db_path = Path(__file__).resolve().parents[1] / "retail_intelligence.db"
if db_path.exists():
    db_path.unlink()

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd
from fastapi.testclient import TestClient

from app.main import app
from app.core.database import init_db

init_db()
client = TestClient(app)
DEMO_PATH = Path(__file__).resolve().parents[2] / "data" / "demo" / "retail_sales_demo.csv"


def auth_headers():
    reg = client.post("/api/auth/register", json={"email": "admin@retailintel.example.com", "password": "SuperSecret123", "role": "admin"})
    assert reg.status_code == 200, reg.text
    login = client.post("/api/auth/login", json={"email": "admin@retailintel.example.com", "password": "SuperSecret123"})
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def main():
    headers = auth_headers()
    print("Auth OK, role:", client.get("/api/auth/me", headers=headers).json())

    # Reject unauthenticated request
    unauth = client.get("/api/datasets")
    assert unauth.status_code == 401
    print("Unauthenticated request correctly rejected with 401")

    df = pd.read_csv(DEMO_PATH)
    subset = df[df["store_id"].isin([1, 2, 3]) & df["item_id"].isin([1, 2, 3, 4, 5])].copy()
    subset_path = Path("/tmp/retail_subset.csv")
    subset.to_csv(subset_path, index=False)

    with open(subset_path, "rb") as f:
        resp = client.post("/api/datasets/upload", files={"file": ("retail_subset.csv", f, "text/csv")},
                            params={"is_demo": True}, headers=headers)
    assert resp.status_code == 200, resp.text
    dataset_id = resp.json()["dataset_id"]
    print(f"\nUploaded dataset_id={dataset_id}, quality_score={resp.json()['profiling_report']['data_quality_score']}")

    # Confirm persistence: list datasets should show it
    listed = client.get("/api/datasets", headers=headers)
    assert any(d["dataset_id"] == dataset_id for d in listed.json())
    print("Dataset persisted and listed from DB:", [d["dataset_id"] for d in listed.json()])

    train_resp = client.post("/api/models/train", params={"dataset_id": dataset_id, "horizon": 14}, headers=headers)
    assert train_resp.status_code == 200, train_resp.text
    print("\n--- TRAINING ---")
    print(json.dumps(train_resp.json(), indent=2, default=str)[:1500])

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
    print("\n--- ALERTS ---", len(alerts_resp.json()["alerts"]), "alerts found")

    whatif_resp = client.post("/api/scenarios/what-if", params={
        "dataset_id": dataset_id, "store_id": 1, "item_id": 1, "current_stock": 40, "demand_growth_pct": 40,
    }, headers=headers)
    assert whatif_resp.status_code == 200, whatif_resp.text
    print("\n--- WHAT-IF delta ---", whatif_resp.json()["delta"])

    registry_resp = client.get("/api/models/registry", headers=headers)
    assert registry_resp.status_code == 200, registry_resp.text
    print("\n--- MODEL REGISTRY ---")
    print(json.dumps(registry_resp.json(), indent=2, default=str))

    monitoring_resp = client.get("/api/models/monitoring", params={"dataset_id": dataset_id}, headers=headers)
    assert monitoring_resp.status_code == 200, monitoring_resp.text
    print("\n--- MONITORING ---")
    print(json.dumps(monitoring_resp.json(), indent=2, default=str))

    anomaly_resp = client.get("/api/analytics/anomalies", params={"dataset_id": dataset_id, "z_threshold": 2.5}, headers=headers)
    assert anomaly_resp.status_code == 200, anomaly_resp.text
    print("\n--- ANOMALIES ---", anomaly_resp.json()["anomaly_count"], "found")
    print(json.dumps(anomaly_resp.json()["anomalies"][:3], indent=2, default=str))

    search_resp = client.get("/api/search", params={"q": "retail_subset"}, headers=headers)
    assert search_resp.status_code == 200, search_resp.text
    print("\n--- GLOBAL SEARCH ---")
    print(json.dumps(search_resp.json(), indent=2, default=str))

    planning_resp = client.get("/api/scenarios/planning", params={
        "dataset_id": dataset_id, "store_id": 1, "item_id": 1, "current_stock": 40,
    }, headers=headers)
    assert planning_resp.status_code == 200, planning_resp.text
    print("\n--- SCENARIO PLANNING ---")
    print(json.dumps(planning_resp.json()["scenarios"], indent=2, default=str)[:2000])

    behavior_resp = client.get("/api/analytics/demand-behavior", params={"dataset_id": dataset_id}, headers=headers)
    assert behavior_resp.status_code == 200, behavior_resp.text
    print("\n--- DEMAND BEHAVIOR PROFILE (first 3) ---")
    print(json.dumps(behavior_resp.json()["profiles"][:3], indent=2, default=str))

    for q in ["Which products are at highest stockout risk?",
              "Which stores have unusual demand?",
              "Show me products with high inventory and declining demand.",
              "Explain the forecast for store 1 item 1",
              "What are the top selling products?",
              "What is the capital of France?"]:
        ai_resp = client.get("/api/insights/ask", params={"dataset_id": dataset_id, "question": q}, headers=headers)
        assert ai_resp.status_code == 200, ai_resp.text
        body = ai_resp.json()
        print(f"\n--- AI INSIGHTS: \"{q}\" ---")
        print("Intent:", body["intent"], "| Answer:", body["answer"], "| Data rows:", len(body["data"]))

    csv_resp = client.get("/api/reports/forecast.csv", params={"dataset_id": dataset_id}, headers=headers)
    assert csv_resp.status_code == 200, csv_resp.text
    print("\n--- REPORT forecast.csv ---", len(csv_resp.content), "bytes")

    xlsx_resp = client.get("/api/reports/inventory.xlsx", params={"dataset_id": dataset_id}, headers=headers)
    assert xlsx_resp.status_code == 200, xlsx_resp.text
    print("--- REPORT inventory.xlsx ---", len(xlsx_resp.content), "bytes")

    pdf_resp = client.get("/api/reports/executive.pdf", params={"dataset_id": dataset_id}, headers=headers)
    assert pdf_resp.status_code == 200, pdf_resp.text
    print("--- REPORT executive.pdf ---", len(pdf_resp.content), "bytes")

    # Non-admin role should be forbidden from changing model status
    reg2 = client.post("/api/auth/register", json={"email": "analyst@retailintel.example.com", "password": "SuperSecret123", "role": "analyst"})
    login2 = client.post("/api/auth/login", json={"email": "analyst@retailintel.example.com", "password": "SuperSecret123"})
    analyst_headers = {"Authorization": f"Bearer {login2.json()['access_token']}"}
    mv_id = registry_resp.json()[0]["model_version_id"]
    forbidden = client.patch(f"/api/models/registry/{mv_id}/status", params={"status": "Production"}, headers=analyst_headers)
    assert forbidden.status_code == 403
    print("\nRBAC correctly blocked analyst from changing model status (403)")

    allowed = client.patch(f"/api/models/registry/{mv_id}/status", params={"status": "Production"}, headers=headers)
    assert allowed.status_code == 200, allowed.text
    print("Admin successfully promoted model to Production:", allowed.json())

    audit_resp = client.get("/api/audit-logs", headers=headers)
    assert audit_resp.status_code == 200, audit_resp.text
    print("\n--- AUDIT LOG (recent actions) ---")
    print(json.dumps(audit_resp.json()[:5], indent=2, default=str))

    audit_forbidden = client.get("/api/audit-logs", headers=analyst_headers)
    assert audit_forbidden.status_code == 403
    print("Audit log correctly restricted to admin (403 for analyst)")

    print("\nFULL END-TO-END BACKEND TEST PASSED (auth + DB persistence + ML + inventory + reports + RBAC)")

    # --- Events / Real-Time Simulation (explicitly labeled SIMULATED) ---
    event_resp = client.post(f"/api/events?dataset_id={dataset_id}", json={
        "name": "Diwali", "start_date": "2017-10-15", "end_date": "2017-10-22", "expected_demand_impact_pct": 45,
    }, headers=headers)
    assert event_resp.status_code == 200, event_resp.text
    event_id = event_resp.json()["event_id"]
    print("\n--- EVENT CREATED ---", event_resp.json())

    events_list = client.get(f"/api/events?dataset_id={dataset_id}", headers=headers)
    assert events_list.status_code == 200
    print("--- EVENTS LIST ---", events_list.json())

    apply_resp = client.post(f"/api/events/{event_id}/apply", params={
        "dataset_id": dataset_id, "store_id": 1, "item_id": 1, "current_stock": 40,
    }, headers=headers)
    assert apply_resp.status_code == 200, apply_resp.text
    print("--- EVENT APPLIED TO INVENTORY ---")
    print(json.dumps(apply_resp.json(), indent=2, default=str))

    sale_resp = client.post("/api/simulation/sale", params={
        "dataset_id": dataset_id, "store_id": 1, "item_id": 1, "quantity": 5,
    }, headers=headers)
    assert sale_resp.status_code == 200, sale_resp.text
    print("\n--- SIMULATED SALE #1 ---")
    print(json.dumps(sale_resp.json(), indent=2, default=str))

    sale_resp2 = client.post("/api/simulation/sale", params={
        "dataset_id": dataset_id, "store_id": 1, "item_id": 1, "quantity": 50,
    }, headers=headers)
    assert sale_resp2.status_code == 200, sale_resp2.text
    print("\n--- SIMULATED SALE #2 (bigger draw-down) ---")
    print(json.dumps(sale_resp2.json(), indent=2, default=str))

    state_resp = client.get("/api/simulation/state", params={"dataset_id": dataset_id, "store_id": 1, "item_id": 1}, headers=headers)
    assert state_resp.status_code == 200
    print("\n--- SIMULATION STATE ---", state_resp.json())

    audit_resp = client.get("/api/audit-logs", headers=headers)
    assert audit_resp.status_code == 200, audit_resp.text
    print(f"\n--- AUDIT LOGS --- {len(audit_resp.json())} entries")

    print("\n\nEVENTS + SIMULATION + AUDIT TESTS PASSED")

    health_resp = client.post("/api/inventory/optimize", params={
        "dataset_id": dataset_id, "store_id": 1, "item_id": 1, "current_stock": 40,
    }, headers=headers)
    assert health_resp.status_code == 200
    print("\n--- INVENTORY HEALTH SCORE ---", health_resp.json()["inventory_health_score"])

    rec_resp = client.get("/api/recommendations", params={"dataset_id": dataset_id}, headers=headers)
    assert rec_resp.status_code == 200, rec_resp.text
    print(f"\n--- SMART RECOMMENDATIONS --- {rec_resp.json()['recommendation_count']} found")
    print(json.dumps(rec_resp.json()["recommendations"][:2], indent=2, default=str))

    mv_ids = ",".join(str(v["model_version_id"]) for v in registry_resp.json()[:2])
    compare_resp = client.get("/api/models/compare", params={"model_version_ids": mv_ids}, headers=headers)
    assert compare_resp.status_code == 200, compare_resp.text
    print("\n--- MODEL COMPARISON ---", len(compare_resp.json()["compared"]), "versions compared")

    # Rate limiting: 6th login attempt within a minute should be blocked (limit is 5/minute)
    limited = None
    for i in range(6):
        limited = client.post("/api/auth/login", json={"email": "admin@retailintel.example.com", "password": "wrong-password"})
    assert limited.status_code == 429, f"Expected 429 after repeated attempts, got {limited.status_code}"
    print("\nRate limiting correctly triggered 429 after repeated login attempts")

    print("\n\nALL NEW FEATURE TESTS PASSED (health score, recommendations, model comparison, rate limiting)")


if __name__ == "__main__":
    main()
