import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.infrastructure.models import OutboxEvent


def write_outbox_event(
    db: Session,
    *,
    tenant_id: UUID,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: dict[str, Any] | None = None,
) -> None:
    db.add(
        OutboxEvent(
            tenant_id=tenant_id,
            aggregate_type=aggregate_type,
            aggregate_id=aggregate_id,
            event_type=event_type,
            payload_json=json.dumps(payload or {}, ensure_ascii=True),
            status="pending",
        )
    )


def mark_outbox_event_published(db: Session, event: OutboxEvent) -> None:
    event.status = "published"
    event.last_error = None
    event.published_at = datetime.now(timezone.utc)
    db.add(event)


def get_pending_outbox_events(db: Session, tenant_id: UUID, limit: int = 100) -> list[OutboxEvent]:
    now = datetime.now(timezone.utc)
    return db.scalars(
        select(OutboxEvent)
        .where(
            OutboxEvent.tenant_id == tenant_id,
            OutboxEvent.status.in_(("pending", "retry")),
            (OutboxEvent.next_attempt_at.is_(None) | (OutboxEvent.next_attempt_at <= now)),
        )
        .order_by(OutboxEvent.created_at.asc())
        .limit(limit)
    ).all()


def mark_outbox_event_failed(db: Session, event: OutboxEvent, error_message: str, max_attempts: int = 5) -> None:
    event.attempts = int(event.attempts or 0) + 1
    event.last_error = (error_message or "unknown_error")[:2000]
    if event.attempts >= max_attempts:
        event.status = "dead_letter"
        event.next_attempt_at = None
    else:
        event.status = "retry"
        delay_seconds = min(300, 2 ** event.attempts)
        event.next_attempt_at = datetime.now(timezone.utc) + timedelta(seconds=delay_seconds)
    db.add(event)


def get_outbox_status_counts(db: Session, tenant_id: UUID) -> dict[str, int]:
    rows = db.scalars(select(OutboxEvent).where(OutboxEvent.tenant_id == tenant_id)).all()
    counts = {"pending": 0, "retry": 0, "published": 0, "dead_letter": 0}
    for row in rows:
        key = row.status if row.status in counts else "pending"
        counts[key] += 1
    return counts
