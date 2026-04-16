import json
from uuid import UUID

from sqlalchemy.orm import Session

from app.domain.outbox import (
    get_outbox_status_counts,
    get_pending_outbox_events,
    mark_outbox_event_failed,
    mark_outbox_event_published,
)
from app.infrastructure.metrics import outbox_failed_total, outbox_published_total, outbox_status_gauge
from app.infrastructure.queue import publish_domain_event


def flush_outbox_for_tenant(db: Session, tenant_id: UUID, limit: int = 100) -> dict[str, int]:
    events = get_pending_outbox_events(db, tenant_id=tenant_id, limit=max(1, min(limit, 500)))
    published = 0
    failed = 0
    for event in events:
        try:
            payload = json.loads(event.payload_json or "{}")
            publish_domain_event(event.event_type, payload)
            mark_outbox_event_published(db, event)
            outbox_published_total.inc()
            published += 1
        except Exception as exc:
            mark_outbox_event_failed(db, event, str(exc))
            outbox_failed_total.inc()
            failed += 1
    db.commit()
    return {"published": published, "failed": failed}


def outbox_status_for_tenant(db: Session, tenant_id: UUID) -> dict[str, int]:
    counts = get_outbox_status_counts(db, tenant_id=tenant_id)
    for status, value in counts.items():
        outbox_status_gauge.labels(status=status).set(value)
    return counts
