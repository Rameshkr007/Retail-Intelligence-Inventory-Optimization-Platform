# Retail Intelligence — Architecture & Roadmap

## 1. System Overview

```
Frontend (React/Vite/TS/Tailwind)
        |
        v
FastAPI REST API (Pydantic, JWT auth)
        |
        v
Service Layer (business logic)
        |
        +--> ML / Forecasting Engine (LightGBM, baselines, SHAP)
        +--> Inventory Optimization Engine (Safety Stock, ROP, EOQ)
        +--> Analytics Engine (ABC/XYZ, anomaly detection, alerts)
        |
        v
PostgreSQL (via SQLAlchemy)
```

Background jobs (training, forecasting, report generation) run via a worker
queue (`app/workers`) rather than inside request/response cycles.

## 2. Database ER Design (core tables)

- `users(id, email, password_hash, role, created_at)`
- `roles(id, name)`
- `stores(id, name, region)`
- `products(id, sku, name, category)`
- `dataset_versions(id, filename, uploaded_at, record_count, date_range_start, date_range_end, quality_score, schema_json)`
- `sales(id, dataset_version_id, store_id, product_id, date, quantity)` — partitioned/indexed on (store_id, product_id, date)
- `features(id, sales_id, feature_set_version, payload_json)`
- `models(id, name, version, algorithm, status)`
- `model_versions(id, model_id, trained_at, train_range, val_range, test_range, hyperparams_json, feature_set_version)`
- `forecasts(id, model_version_id, store_id, product_id, forecast_date, horizon, point, lower, upper)`
- `forecast_metrics(id, model_version_id, mae, rmse, mape, smape, wape, bias)`
- `inventory_parameters(id, store_id, product_id, lead_time, service_level, ordering_cost, holding_cost, current_stock, moq, max_capacity)`
- `inventory_recommendations(id, store_id, product_id, generated_at, safety_stock, rop, eoq, suggested_order, stockout_risk, overstock_risk, reason)`
- `alerts(id, type, severity, entity_ref, message, created_at, resolved)`
- `scenarios(id, name, params_json)`
- `simulation_runs(id, scenario_id, run_at, results_json)`
- `experiments(id, model_version_id, notes, metrics_json)`
- `audit_logs(id, user_id, action, entity, timestamp, metadata_json)`

Indexes: `(store_id, product_id, date)` on `sales`, `(forecast_date)` on `forecasts`.

## 3. API Specification (v1, summarized)

| Method | Path | Purpose |
|---|---|---|
| POST | /api/auth/login | Authenticate, issue JWT |
| POST | /api/datasets/upload | Upload CSV/XLSX, create dataset_version |
| GET | /api/datasets | List dataset versions |
| GET | /api/datasets/{id} | Profiling report for a dataset version |
| GET | /api/datasets/{id}/transformations | Data cleaning/transformation log |
| POST | /api/models/train | Kick off training job (async) |
| GET | /api/models | List models/versions |
| GET | /api/models/{id} | Model detail incl. metrics |
| POST | /api/forecast | Request forecast (store, sku, horizon) |
| GET | /api/forecast | Retrieve forecasts |
| POST | /api/inventory/optimize | Recompute inventory parameters |
| GET | /api/inventory/recommendations | Reorder recommendations |
| GET | /api/alerts | List alerts |
| POST | /api/scenarios | Create what-if scenario |
| POST | /api/simulation/run | Run scenario simulation |
| GET | /api/reports | List/generate downloadable reports |
| GET | /api/analytics/summary | Executive KPI summary |

Full OpenAPI schema is generated automatically by FastAPI at `/docs`.

## 4. Frontend Page Map

Dashboard · Data Hub (Upload / Quality / Explorer) · Forecasting (Dashboard /
Model Comparison / Explorer) · Inventory (Overview / Reorder / ABC-XYZ /
Stockout / Overstock) · Simulation (What-If / Scenario Planning / Digital
Twin) · AI Insights (Demand / Inventory / Anomaly) · Models (Registry /
Experiments / Monitoring) · Reports · Settings.

## 5. ML Pipeline Architecture

```
Raw CSV/XLSX
  -> Ingestion & schema detection
  -> Data Quality Profiling (score + issue log)
  -> Cleaning (logged, non-destructive - flags kept alongside cleaned rows)
  -> Feature Engineering (calendar, lag, rolling, demand-behavior)
  -> Time-based train/val/test split (walk-forward)
  -> Baselines (naive, seasonal naive, moving avg, exp. smoothing)
  -> LightGBM (primary) [+ optional XGBoost/RF for comparison]
  -> Evaluation (MAE/RMSE/MAPE/sMAPE/WAPE, residuals, bias)
  -> SHAP explanation (global + local)
  -> Forecast storage with uncertainty bounds
```

Leakage safeguards: all lag/rolling features are computed strictly from data
available at or before the feature's timestamp per (store, item) group;
splits are chronological, never random.

## 6. Inventory Optimization Architecture

```
Forecast (point + uncertainty) + demand history
  -> Demand variability (std dev of forecast errors or historical demand)
  -> Safety Stock = z * sigma_D * sqrt(L)
  -> Reorder Point = LeadTimeDemand + SafetyStock
  -> EOQ = sqrt(2 * D * S / H)
  -> Suggested Order = max(0, ROP + EOQ - CurrentStock) [policy-configurable]
  -> Stockout / Overstock risk classification
  -> Recommendation with explanation
```

## 7. Folder Structure

See `retail-intelligence/` root — `frontend/`, `backend/`, `ml/`, `data/`,
`docs/`, `scripts/` as scaffolded.

## 8. Development Roadmap / Implementation Order

1. **Module 1 — Data Ingestion & Quality** (this pass): synthetic demo
   dataset, upload endpoint, profiling, data-quality score, cleaning log.
2. **Module 2 — Feature Engineering**: calendar/lag/rolling/demand-behavior
   features, leakage-safe pipeline.
3. **Module 3 — Forecasting Engine**: baselines + LightGBM, walk-forward CV,
   metrics, uncertainty bounds.
4. **Module 4 — Explainability**: SHAP global/local, business-friendly text.
5. **Module 5 — Inventory Optimization**: Safety Stock / ROP / EOQ / order
   recommendation engine.
6. **Module 6 — Risk & Segmentation**: stockout/overstock detection,
   ABC-XYZ, SKU priority matrix.
7. **Module 7 — Simulation**: what-if simulator, scenario planning.
8. **Module 8 — Dashboards & API wiring**: Executive/Forecast/Inventory
   dashboards on real backend data.
9. **Module 9 — Alerts, Monitoring, Experiments, Model Registry**.
10. **Module 10 — Reports, Auth/RBAC, Audit Logging, Deployment config**.

Each module ships with working backend logic connected to real computation
(no hardcoded metrics), plus the minimal frontend needed to demonstrate it.

## 9. Honest Limitations (carried through every module)

- Metrics are computed from the actual dataset loaded (demo data unless a
  real dataset is uploaded) — never fabricated.
- "Real-time" features are simulation-based unless a live data source is
  connected; the UI must label this clearly.
- Business-impact figures (cost savings, etc.) are only shown if derivable
  from configured formulas — never asserted as guarantees.
