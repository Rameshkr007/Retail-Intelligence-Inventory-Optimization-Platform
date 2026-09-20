# Retail Intelligence — Sales Forecasting & Inventory Optimization Platform

An explainable ML-based retail decision intelligence platform: LightGBM
demand forecasting with SHAP explainability, connected end-to-end to
inventory optimization (Safety Stock / Reorder Point / EOQ), ABC-XYZ
segmentation, alerting, a what-if simulator, and a full React dashboard.

## Quick start (Docker — recommended)

```bash
cp .env.example .env   # edit JWT_SECRET
docker compose up --build
```

- Backend API + docs: http://localhost:8000/docs
- Frontend: http://localhost:5173

## Quick start (local dev, no Docker)

**Backend** (SQLite fallback, no Postgres needed for a quick look):

```bash
cd backend
pip install -r requirements.txt
RETAIL_DB_FALLBACK_SQLITE=1 uvicorn app.main:app --reload --port 8000
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

Open http://localhost:5173, register an account, then go to **Data Hub**
and upload `data/demo/retail_sales_demo.csv` (or generate a fresh one with
`python scripts/generate_demo_data.py`).

## Demo flow

1. Register / log in (JWT auth, roles: admin / analyst / manager)
2. **Data Hub** — upload CSV/XLSX → schema auto-detected → profiling report
   + Data Quality Score + transformation log
3. **Forecasting** — train LightGBM (walk-forward split, baseline
   comparison), then request a forecast with uncertainty bounds + SHAP
   explanation
4. **Inventory** — Safety Stock / Reorder Point / EOQ / suggested order,
   with stockout/overstock risk
5. **What-If Simulator** — change demand growth / lead time, see before vs
   after
6. **ABC-XYZ Analytics** — value × variability segmentation, priority
   quadrants
7. **Alert Center** — demand spikes / high volatility, computed live
8. **Model Registry** — every training run versioned, promote to Production
   (admin only), monitoring with a retraining-recommended threshold
9. **Reports** — download CSV / Excel / PDF, generated from real DB data
10. **Alert Center** also shows statistical anomaly detection (rolling
    z-score vs. each SKU's own trailing history) and a global search box
    (top-left of every page) across datasets and model versions
11. **What-If Simulator** also runs **Scenario Planning** — 5 standard
    business scenarios (Baseline/High Demand/Low Demand/Promotional
    Spike/Supply Delay) side by side, same real formulas
12. **AI Insights** — ask a plain-English question ("which products are at
    highest stockout risk?", "explain the forecast for store 1 item 1",
    "top selling products"); answered by a deterministic query engine
    grounded entirely in this app's own computed data — it explicitly
    declines to answer anything outside what it can compute, rather than
    fabricating a plausible-sounding response
13. **Festival/Event scenarios** — declare a custom business event (e.g.
    "Diwali, +45% demand") and apply it to a SKU's inventory calculation.
    Explicitly labeled as a user-declared assumption, never presented as
    historical fact
14. **Digital Twin / Real-Time Simulation** (Inventory page) — record a
    simulated sale and watch stock → stockout risk → reorder recommendation
    update live. Every response is labeled `"status": "SIMULATED"` — this
    is a demo mechanism, not a live POS/ERP feed
15. **Inventory Health Score** — documented composite score (0-100) per SKU
    combining stockout risk, overstock risk, demand volatility, and a
    days-of-inventory imbalance check — shown on the Inventory page
16. **Smart Business Recommendation Engine** — structured
    Action/Reason/Evidence/Priority/Expected-Impact recommendations,
    derived from real risk/anomaly/model-drift signals (never a generic
    "everything is fine" filler, never an invented dollar-savings figure)
17. **Model comparison** (`/api/models/compare?model_version_ids=1,2`) —
    side-by-side metrics for any two training runs
18. **Interview Mode** page — in-app pipeline diagram + "why LightGBM /
    why time-based split / why SHAP / why Safety Stock" Q&A for viva prep
19. **Rate limiting** on login (5/min) and register (10/min) — brute-force
    protection, verified with a test that triggers a 429
20. **Ctrl/Cmd+K** focuses the global search box
13. **Technical Architecture / Interview Mode** — pipeline walkthrough +
    "why LightGBM / why this split / why SHAP" Q&A, for project viva
14. **Audit Log** (admin-only) — every login, upload, training run, and
    status change, tracked with user + timestamp

## What's real vs. what's a documented limitation

Everything above is wired to actual computation — no hardcoded metrics,
no fabricated accuracy or savings numbers. Full test suite in
`backend/tests/`:
- `test_full_e2e_persisted.py` — exercises the entire flow end to end
  (auth → upload → train → forecast → inventory → scenarios → events →
  simulation → recommendations → reports → RBAC → rate limiting)
- `test_formulas_unit.py` — isolated unit tests for the core math
  (Safety Stock, ROP, EOQ, forecast metrics, ABC/XYZ, health score),
  hand-verified against known expected values, no API/DB required

Known, explicitly documented gaps (see `docs/ARCHITECTURE.md` §9):

- **Live POS/ERP integration** is not implemented — the Digital Twin above
  is a deliberate, clearly-labeled simulation of that flow (per spec §27:
  "can initially be simulation-based... clearly label simulated/live
  status"), not a fake claim of real-time connectivity.
- **Global search** currently covers datasets and model versions (not yet
  per-SKU/store, which live inside a dataset's feature table rather than
  a standalone entity table).
- The in-process feature-set cache (`_FEATURE_CACHE`) is a performance
  optimization only — all metadata (datasets, model versions, inventory
  recommendations, users, audit logs) is durably persisted in
  PostgreSQL/SQLite and survives a restart; only the cached in-memory
  feature dataframe would need to be recomputed (automatic, on first
  request after restart).

## Project structure

See `docs/ARCHITECTURE.md` for the full system architecture, ER diagram,
API spec, ML pipeline, and inventory optimization formulas.

## Innovative addition

**AI Insights** (`/api/insights/ask`) is a deliberate design choice over a
generic LLM-chat bolt-on: rather than calling an LLM and hoping it doesn't
hallucinate numbers, it's a small deterministic intent classifier that
routes recognized questions to the same real inventory/anomaly/demand-
behavior computations used elsewhere in the app, and explicitly returns
"not recognized" for anything else (verified in the test suite with
"What is the capital of France?" → correctly refuses rather than guessing).
This satisfies the spec's "AI assistant must never fabricate data"
requirement by construction, not by prompting.


```
retail-intelligence/
├── backend/        FastAPI + SQLAlchemy + LightGBM + SHAP
├── frontend/        React + Vite + TypeScript + Tailwind
├── ml/artifacts/    Trained model files (joblib)
├── data/            raw / processed / demo datasets
├── docs/            architecture & roadmap
├── scripts/         demo data generator
└── docker-compose.yml
```
