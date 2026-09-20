from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api import (
    ai_insights, analytics_simulation, anomaly_search, audit, auth, datasets,
    events_simulation, forecast_inventory, model_registry, recommendations,
    reports, scenario_planning,
)
from app.api.auth import limiter
from app.core.database import init_db

app = FastAPI(
    title="Retail Intelligence API",
    description="Explainable ML-based retail decision intelligence platform.",
    version="1.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup():
    init_db()


app.include_router(auth.router)
app.include_router(datasets.router)
app.include_router(forecast_inventory.router)
app.include_router(analytics_simulation.router)
app.include_router(model_registry.router)
app.include_router(reports.router)
app.include_router(anomaly_search.router)
app.include_router(scenario_planning.router)
app.include_router(ai_insights.router)
app.include_router(audit.router)
app.include_router(events_simulation.router)
app.include_router(recommendations.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
