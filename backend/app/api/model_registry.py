from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import get_current_user, require_role
from app.core.database import get_db
from app.models.orm import ModelVersion, User

router = APIRouter(prefix="/api/models", tags=["model_registry"])


@router.get("/registry")
async def list_model_versions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    versions = db.query(ModelVersion).order_by(ModelVersion.trained_at.desc()).all()
    return [
        {
            "model_version_id": v.id, "dataset_version_id": v.dataset_version_id,
            "algorithm": v.algorithm, "status": v.status, "trained_at": v.trained_at.isoformat(),
            "horizon": v.horizon,
            "val_mae": v.val_metrics_json.get("mae"), "test_mae": v.test_metrics_json.get("mae"),
            "test_wape": v.test_metrics_json.get("wape"),
        }
        for v in versions
    ]


@router.get("/registry/{model_version_id}")
async def get_model_version(model_version_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    v = db.query(ModelVersion).filter(ModelVersion.id == model_version_id).first()
    if v is None:
        raise HTTPException(status_code=404, detail="Model version not found.")
    return {
        "model_version_id": v.id, "dataset_version_id": v.dataset_version_id, "algorithm": v.algorithm,
        "status": v.status, "trained_at": v.trained_at.isoformat(), "horizon": v.horizon,
        "train_range": v.train_range, "val_range": v.val_range, "test_range": v.test_range,
        "val_metrics": v.val_metrics_json, "test_metrics": v.test_metrics_json,
        "baseline_metrics": v.baseline_metrics_json, "feature_cols": v.feature_cols_json,
    }


@router.patch("/registry/{model_version_id}/status")
async def update_model_status(
    model_version_id: int, status: str,
    db: Session = Depends(get_db), user: User = Depends(require_role("admin")),
):
    valid = {"Development", "Validated", "Production", "Archived"}
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Status must be one of {sorted(valid)}.")
    v = db.query(ModelVersion).filter(ModelVersion.id == model_version_id).first()
    if v is None:
        raise HTTPException(status_code=404, detail="Model version not found.")
    v.status = status
    db.commit()
    return {"model_version_id": v.id, "status": v.status}


MONITORING_MAE_THRESHOLD = 15.0  # documented, configurable retraining trigger


@router.get("/monitoring")
async def monitoring_summary(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    versions = (
        db.query(ModelVersion)
        .filter(ModelVersion.dataset_version_id == dataset_id)
        .order_by(ModelVersion.trained_at.asc())
        .all()
    )
    if not versions:
        raise HTTPException(status_code=404, detail="No model versions found for this dataset.")
    latest = versions[-1]
    retraining_recommended = (latest.test_metrics_json.get("mae") or 0) > MONITORING_MAE_THRESHOLD
    return {
        "dataset_id": dataset_id,
        "model_version_count": len(versions),
        "latest_model_version_id": latest.id,
        "latest_test_mae": latest.test_metrics_json.get("mae"),
        "latest_test_wape": latest.test_metrics_json.get("wape"),
        "mae_history": [{"model_version_id": v.id, "trained_at": v.trained_at.isoformat(), "test_mae": v.test_metrics_json.get("mae")} for v in versions],
        "retraining_recommended": retraining_recommended,
        "retraining_threshold_mae": MONITORING_MAE_THRESHOLD,
    }
