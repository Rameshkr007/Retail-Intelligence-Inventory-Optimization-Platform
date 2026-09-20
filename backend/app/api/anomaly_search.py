from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.analytics.anomaly_detection import detect_anomalies
from app.api.forecast_inventory import _dataset_schema, _get_features, _sanitize
from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.orm import DatasetVersion, ModelVersion, User

router = APIRouter(prefix="/api", tags=["anomaly_search"])


@router.get("/analytics/anomalies")
async def get_anomalies(
    dataset_id: int, z_threshold: float = 3.0, limit: int = 50,
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    """Detects unusual sales behavior (spikes/collapses) using a rolling
    z-score against each SKU's own trailing history — never claims a cause,
    only reports the statistical deviation and its magnitude."""
    schema = _dataset_schema(db, dataset_id)
    store_col, item_col, date_col, sales_col = (
        schema["store_col"], schema["item_col"], schema["date_col"], schema["sales_col"],
    )
    features = _get_features(db, dataset_id, schema)

    anomalies = detect_anomalies(features, store_col, item_col, date_col, sales_col, z_threshold=z_threshold)
    anomalies = anomalies.head(limit).copy()
    anomalies[date_col] = anomalies[date_col].astype(str)

    return _sanitize({
        "dataset_id": dataset_id,
        "z_threshold": z_threshold,
        "anomaly_count": len(anomalies),
        "anomalies": anomalies.round(2).to_dict(orient="records"),
        "note": "Anomaly = observed sales deviating from the SKU's own trailing 28-day mean by "
        "more than the z-score threshold. This flags statistical deviation only; it does not "
        "assert a cause (promotion, stockout, data error, etc.) unless investigated separately.",
    })


@router.get("/search")
async def global_search(q: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Search across datasets and trained models by filename/id/algorithm.
    Store/Item search is scoped within a dataset's feature table (see
    /api/analytics/abc-xyz and /api/alerts for per-SKU lookups), since
    stores/items aren't a standalone entity table in this schema yet."""
    q_like = f"%{q}%"
    results = []

    datasets = db.query(DatasetVersion).filter(
        or_(DatasetVersion.filename.ilike(q_like))
    ).limit(10).all()
    for d in datasets:
        results.append({"type": "dataset", "id": d.id, "label": d.filename, "detail": f"{d.record_count:,} records"})

    models = db.query(ModelVersion).filter(
        or_(ModelVersion.algorithm.ilike(q_like), ModelVersion.status.ilike(q_like))
    ).limit(10).all()
    for m in models:
        results.append({"type": "model_version", "id": m.id, "label": f"{m.algorithm} v{m.id}", "detail": m.status})

    # Numeric query -> also try matching a store_id/item_id/dataset_id directly
    if q.strip().isdigit():
        n = int(q.strip())
        by_id = db.query(DatasetVersion).filter(DatasetVersion.id == n).first()
        if by_id and not any(r["type"] == "dataset" and r["id"] == n for r in results):
            results.append({"type": "dataset", "id": by_id.id, "label": by_id.filename, "detail": f"{by_id.record_count:,} records"})

    return {"query": q, "results": results}
