from __future__ import annotations

import io

import pandas as pd
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from reportlab.lib.pagesizes import A4
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from sqlalchemy.orm import Session

from app.core.auth import get_current_user
from app.core.database import get_db
from app.models.orm import DatasetVersion, InventoryRecommendation, ModelVersion, User

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.get("/forecast.csv")
async def forecast_csv(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    mv = db.query(ModelVersion).filter(ModelVersion.dataset_version_id == dataset_id).order_by(ModelVersion.trained_at.desc()).first()
    if mv is None:
        raise HTTPException(status_code=400, detail="No trained model for this dataset.")
    df = pd.DataFrame([{
        "model_version_id": mv.id, "algorithm": mv.algorithm, "trained_at": mv.trained_at,
        "train_range": str(mv.train_range), "val_range": str(mv.val_range), "test_range": str(mv.test_range),
        **{f"val_{k}": v for k, v in mv.val_metrics_json.items()},
        **{f"test_{k}": v for k, v in mv.test_metrics_json.items()},
    }])
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(iter([buf.getvalue()]), media_type="text/csv",
                              headers={"Content-Disposition": f"attachment; filename=forecast_metrics_{dataset_id}.csv"})


@router.get("/inventory.xlsx")
async def inventory_excel(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    recs = db.query(InventoryRecommendation).filter(InventoryRecommendation.dataset_version_id == dataset_id).all()
    if not recs:
        raise HTTPException(status_code=400, detail="No inventory recommendations generated yet for this dataset. Call /api/inventory/optimize first.")
    df = pd.DataFrame([{
        "store_id": r.store_id, "item_id": r.item_id, "generated_at": r.generated_at,
        "safety_stock": r.safety_stock, "reorder_point": r.reorder_point, "eoq": r.eoq,
        "suggested_order": r.suggested_order, "stockout_risk": r.stockout_risk,
        "overstock_risk": r.overstock_risk, "reason": r.reason,
    } for r in recs])
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Inventory Recommendations")
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                              headers={"Content-Disposition": f"attachment; filename=inventory_recommendations_{dataset_id}.xlsx"})


@router.get("/executive.pdf")
async def executive_pdf(dataset_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    dataset = db.query(DatasetVersion).filter(DatasetVersion.id == dataset_id).first()
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found.")
    mv = db.query(ModelVersion).filter(ModelVersion.dataset_version_id == dataset_id).order_by(ModelVersion.trained_at.desc()).first()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph("Retail Intelligence — Executive Report", styles["Title"]),
        Spacer(1, 12),
        Paragraph(f"Dataset: {dataset.filename} ({'Demo Data' if dataset.is_demo else 'Uploaded Data'})", styles["Normal"]),
        Paragraph(f"Records: {dataset.record_count:,} | Data Quality Score: {dataset.quality_score}/100", styles["Normal"]),
        Spacer(1, 12),
    ]

    if mv is not None:
        elements.append(Paragraph("Forecasting Model", styles["Heading2"]))
        metrics_table = Table(
            [["Metric", "Validation", "Test"]] +
            [[k.upper(), round(mv.val_metrics_json.get(k, 0) or 0, 2), round(mv.test_metrics_json.get(k, 0) or 0, 2)]
             for k in ["mae", "rmse", "mape", "smape", "wape", "bias"]],
            hAlign="LEFT",
        )
        metrics_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
        ]))
        elements += [metrics_table, Spacer(1, 12)]
    else:
        elements.append(Paragraph("No trained model yet for this dataset.", styles["Normal"]))

    elements.append(Paragraph(
        "Limitations: metrics are computed from the dataset above only and may not generalize to other periods "
        "or store/item combinations. Inventory figures use configurable business assumptions and standard formulas "
        "(Safety Stock, Reorder Point, EOQ) documented in the project methodology. No real-time integration is implied.",
        styles["Normal"],
    ))

    doc.build(elements)
    buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                              headers={"Content-Disposition": f"attachment; filename=executive_report_{dataset_id}.pdf"})
