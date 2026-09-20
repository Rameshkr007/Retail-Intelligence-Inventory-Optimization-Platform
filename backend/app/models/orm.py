from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


def _now():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="analyst")  # admin | analyst | manager
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class DatasetVersion(Base):
    __tablename__ = "dataset_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    record_count: Mapped[int] = mapped_column(Integer)
    quality_score: Mapped[int] = mapped_column(Integer)
    schema_json: Mapped[dict] = mapped_column(JSON)
    profiling_json: Mapped[dict] = mapped_column(JSON)
    transformation_log_json: Mapped[list] = mapped_column(JSON)
    cleaned_data_path: Mapped[str] = mapped_column(String(500))  # parquet/csv on disk
    flagged_data_path: Mapped[str] = mapped_column(String(500), nullable=True)


class ModelVersion(Base):
    __tablename__ = "model_versions"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"))
    algorithm: Mapped[str] = mapped_column(String(64), default="LightGBM")
    status: Mapped[str] = mapped_column(String(32), default="Development")  # Development|Validated|Production|Archived
    trained_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    horizon: Mapped[int] = mapped_column(Integer)
    train_range: Mapped[dict] = mapped_column(JSON)
    val_range: Mapped[dict] = mapped_column(JSON)
    test_range: Mapped[dict] = mapped_column(JSON)
    val_metrics_json: Mapped[dict] = mapped_column(JSON)
    test_metrics_json: Mapped[dict] = mapped_column(JSON)
    baseline_metrics_json: Mapped[dict] = mapped_column(JSON)
    model_artifact_path: Mapped[str] = mapped_column(String(500))
    feature_cols_json: Mapped[list] = mapped_column(JSON)
    residual_std: Mapped[float] = mapped_column(Float)


class InventoryRecommendation(Base):
    __tablename__ = "inventory_recommendations"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"))
    store_id: Mapped[int] = mapped_column(Integer)
    item_id: Mapped[int] = mapped_column(Integer)
    generated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
    safety_stock: Mapped[float] = mapped_column(Float)
    reorder_point: Mapped[float] = mapped_column(Float)
    eoq: Mapped[float] = mapped_column(Float)
    suggested_order: Mapped[float] = mapped_column(Float)
    stockout_risk: Mapped[str] = mapped_column(String(16))
    overstock_risk: Mapped[bool] = mapped_column(Boolean)
    reason: Mapped[str] = mapped_column(Text)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_email: Mapped[str] = mapped_column(String(255), nullable=True)
    action: Mapped[str] = mapped_column(String(128))
    entity: Mapped[str] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=_now)


class BusinessEvent(Base):
    """User-defined festival/promotion/custom event — an explicit business
    input (spec §26), never presented as historical fact. Used purely as a
    scenario variable in scenario planning."""
    __tablename__ = "business_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"))
    name: Mapped[str] = mapped_column(String(128))
    start_date: Mapped[str] = mapped_column(String(32))
    end_date: Mapped[str] = mapped_column(String(32))
    expected_demand_impact_pct: Mapped[float] = mapped_column(Float)
    created_by: Mapped[str] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_now)


class SimulatedInventoryState(Base):
    """Real-Time Inventory Simulation (spec §27) — explicitly SIMULATED,
    not a live POS/ERP feed. Tracks a mutable current-stock value per
    (dataset, store, item) that /api/simulation/sale can decrement, so the
    Digital-Twin-style demo can show stock -> risk -> recommendation update
    without needing a real integration."""
    __tablename__ = "simulated_inventory_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    dataset_version_id: Mapped[int] = mapped_column(ForeignKey("dataset_versions.id"))
    store_id: Mapped[int] = mapped_column(Integer)
    item_id: Mapped[int] = mapped_column(Integer)
    current_stock: Mapped[float] = mapped_column(Float)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=_now)
