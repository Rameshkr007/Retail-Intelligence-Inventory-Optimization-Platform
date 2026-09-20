from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import require_role
from app.core.database import get_db
from app.models.orm import AuditLog, User

router = APIRouter(prefix="/api/audit-logs", tags=["audit"])


@router.get("")
async def list_audit_logs(limit: int = 100, db: Session = Depends(get_db), user: User = Depends(require_role("admin"))):
    logs = db.query(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit).all()
    return [
        {
            "id": l.id, "user_email": l.user_email, "action": l.action,
            "entity": l.entity, "metadata": l.metadata_json, "timestamp": l.timestamp.isoformat(),
        }
        for l in logs
    ]
