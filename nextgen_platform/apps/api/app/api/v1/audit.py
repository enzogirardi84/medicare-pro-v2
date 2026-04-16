from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.infrastructure.db import get_db
from app.infrastructure.models import AuditLog

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("")
def list_audit_logs(claims: dict = Depends(require_roles("admin", "auditor")), db: Session = Depends(get_db)):
    rows = db.scalars(
        select(AuditLog)
        .where(AuditLog.tenant_id == UUID(claims["tenant_id"]))
        .order_by(AuditLog.created_at.desc())
        .limit(200)
    ).all()
    return [
        {
            "id": str(r.id),
            "tenant_id": str(r.tenant_id),
            "actor_user_id": str(r.actor_user_id),
            "action": r.action,
            "entity": r.entity,
            "entity_id": r.entity_id,
            "details_json": r.details_json,
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]
