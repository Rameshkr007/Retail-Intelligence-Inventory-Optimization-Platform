from __future__ import annotations

import io
from pathlib import Path

import pandas as pd
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.orm import AuditLog, DatasetVersion, User
from app.services.ingestion import clean_dataset, detect_schema, profile_dataset

router = APIRouter(prefix="/api/datasets", tags=["datasets"])

MAX_UPLOAD_BYTES = 200 * 1024 * 1024
DATA_DIR = Path(__file__).resolve().parents[3] / "data" / "processed"
DATA_DIR.mkdir(parents=True, exist_ok=True)


def _read_upload(file_bytes: bytes, filename: str) -> pd.DataFrame:
    if filename.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(file_bytes))
    if filename.lower().endswith(".csv"):
        return pd.read_csv(io.BytesIO(file_bytes))
    raise HTTPException(status_code=400, detail="Unsupported file type. Upload a .csv or .xlsx file.")


@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    is_demo: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    content = await file.read()
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="File exceeds maximum upload size (200MB).")
    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    try:
        df = _read_upload(content, file.filename)
    except HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Could not parse file: {exc}") from exc

    if df.empty:
        raise HTTPException(status_code=400, detail="Uploaded dataset has no rows.")

    schema = detect_schema(df)
    if not schema.is_complete:
        missing = [
            name
            for name, val in [
                ("date", schema.date_col), ("store", schema.store_col),
                ("item", schema.item_col), ("sales", schema.sales_col),
            ]
            if val is None
        ]
        raise HTTPException(
            status_code=422,
            detail=f"Could not detect required column(s): {', '.join(missing)}. Found columns: {list(df.columns)}",
        )

    profiling_report = profile_dataset(df, schema)
    cleaning_result = clean_dataset(df, schema)

    schema_dict = {
        "date_col": schema.date_col, "store_col": schema.store_col,
        "item_col": schema.item_col, "sales_col": schema.sales_col,
    }

    # Persist metadata row first to get an id, then write files named by that id.
    version = DatasetVersion(
        filename=file.filename,
        is_demo=is_demo,
        record_count=len(df),
        quality_score=profiling_report["data_quality_score"],
        schema_json=schema_dict,
        profiling_json=profiling_report,
        transformation_log_json=cleaning_result.transformation_log,
        cleaned_data_path="",
        flagged_data_path=None,
    )
    db.add(version)
    db.commit()
    db.refresh(version)

    cleaned_path = DATA_DIR / f"dataset_{version.id}_cleaned.parquet"
    cleaning_result.cleaned_df.to_parquet(cleaned_path, index=False)
    version.cleaned_data_path = str(cleaned_path)

    if not cleaning_result.flagged_rows.empty:
        flagged_path = DATA_DIR / f"dataset_{version.id}_flagged.parquet"
        flagged_to_save = cleaning_result.flagged_rows.copy()
        for col in flagged_to_save.columns:
            if flagged_to_save[col].dtype == "object":
                flagged_to_save[col] = flagged_to_save[col].astype(str)
        flagged_to_save.to_parquet(flagged_path, index=False)
        version.flagged_data_path = str(flagged_path)

    db.add(AuditLog(user_email=user.email, action="dataset_upload", entity=f"dataset_version:{version.id}",
                     metadata_json={"filename": file.filename, "record_count": len(df)}))
    db.commit()

    return {
        "dataset_id": version.id,
        "filename": version.filename,
        "is_demo": version.is_demo,
        "record_count": version.record_count,
        "detected_schema": schema_dict,
        "profiling_report": profiling_report,
        "cleaned_record_count": len(cleaning_result.cleaned_df),
        "flagged_record_count": len(cleaning_result.flagged_rows),
    }


@router.get("")
async def list_datasets(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    versions = db.query(DatasetVersion).order_by(DatasetVersion.uploaded_at.desc()).all()
    return [
        {
            "dataset_id": d.id, "filename": d.filename, "is_demo": d.is_demo,
            "uploaded_at": d.uploaded_at.isoformat(), "record_count": d.record_count,
            "data_quality_score": d.quality_score,
        }
        for d in versions
    ]


def _get_version_or_404(db: Session, dataset_id: int) -> DatasetVersion:
    version = db.query(DatasetVersion).filter(DatasetVersion.id == dataset_id).first()
    if version is None:
        raise HTTPException(status_code=404, detail="Dataset version not found.")
    return version


@router.get("/{dataset_id}")
async def get_dataset(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    version = _get_version_or_404(db, dataset_id)
    return {
        "dataset_id": version.id, "filename": version.filename, "is_demo": version.is_demo,
        "uploaded_at": version.uploaded_at.isoformat(), "record_count": version.record_count,
        "detected_schema": version.schema_json, "profiling_report": version.profiling_json,
    }


@router.get("/{dataset_id}/transformations")
async def get_transformation_log(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    version = _get_version_or_404(db, dataset_id)
    flagged_count = 0
    if version.flagged_data_path and Path(version.flagged_data_path).exists():
        flagged_count = len(pd.read_parquet(version.flagged_data_path))
    return {"dataset_id": version.id, "transformation_log": version.transformation_log_json, "flagged_record_count": flagged_count}


@router.get("/{dataset_id}/flagged")
async def get_flagged_rows(dataset_id: int, limit: int = 100, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    version = _get_version_or_404(db, dataset_id)
    if not version.flagged_data_path or not Path(version.flagged_data_path).exists():
        return {"dataset_id": dataset_id, "flagged_rows": []}
    sample = pd.read_parquet(version.flagged_data_path).head(limit)
    for col in sample.columns:
        if pd.api.types.is_datetime64_any_dtype(sample[col]):
            sample[col] = sample[col].astype(str)
    return {"dataset_id": dataset_id, "flagged_rows": sample.to_dict(orient="records")}


def load_cleaned_df(db: Session, dataset_id: int) -> tuple[pd.DataFrame, dict]:
    """Used by the ML/forecast/inventory routers to load a dataset's cleaned
    data + schema from persisted storage (DB metadata + parquet on disk)."""
    version = _get_version_or_404(db, dataset_id)
    if not Path(version.cleaned_data_path).exists():
        raise HTTPException(status_code=410, detail="Cleaned dataset file is missing from disk.")
    df = pd.read_parquet(version.cleaned_data_path)
    return df, version.schema_json
