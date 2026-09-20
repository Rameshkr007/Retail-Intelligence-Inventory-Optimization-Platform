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



    grounded entirely in this app's own computed data — it explicitly
    declines to answer anything outside what it can compute, rather than
    fabricating a plausible-sounding response






## Project structure

See `docs/ARCHITECTURE.md` for the full system architecture, ER diagram,
API spec, ML pipeline, and inventory optimization formulas.




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
