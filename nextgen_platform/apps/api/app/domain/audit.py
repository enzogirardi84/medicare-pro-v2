import json
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.infrastructure.models import AuditLog


def write_audit_log(
    db: Session,
    *,
    tenant_id: UUID,
    actor_user_id: UUID,
    action: str,
    entity: str,
    entity_id: str,
    details: dict[str, Any] | None = None,
) -> None:
    row = AuditLog(
        tenant_id=tenant_id,
        actor_user_id=actor_user_id,
        action=action,
        entity=entity,
        entity_id=entity_id,
        details_json=json.dumps(details or {}, ensure_ascii=True),
    )
    db.add(row)
