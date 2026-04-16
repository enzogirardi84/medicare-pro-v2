import hashlib
import time
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request, status
import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import enforce_rate_limit, get_current_claims, require_roles
from app.domain.audit import write_audit_log
from app.domain.outbox import write_outbox_event
from app.domain.schemas import VisitCreate, VisitOut, VisitsBulkCreate
from app.core.config import settings
from app.core.resilience import get_resilience_policy
from app.infrastructure.cache import (
    get_json_cache,
    get_resource_list_cache_version,
    invalidate_resource_list_cache,
    list_cache_key,
    release_cache_build_lock,
    redis_client,
    set_json_cache,
    try_acquire_cache_build_lock,
)
from app.infrastructure.db import get_db, get_db_readonly
from app.infrastructure.metrics import idempotency_events_total
from app.infrastructure.models import Patient, Visit

router = APIRouter(prefix="/visits", tags=["visits"])


@router.post("", response_model=VisitOut, status_code=status.HTTP_201_CREATED)
def create_visit(
    payload: VisitCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    claims: dict = Depends(require_roles("admin", "doctor", "nurse")),
    db: Session = Depends(get_db),
):
    tenant_id = UUID(claims["tenant_id"])
    enforce_rate_limit(request, claims, limit_per_minute=120)
    if idempotency_key:
        idem_key = f"idem:visits:{tenant_id}:{idempotency_key.strip()}"
        try:
            existing_visit_id = redis_client.get(idem_key)
        except redis.RedisError as exc:
            idempotency_events_total.labels(operation="visits_create", result="redis_error_lookup").inc()
            if not get_resilience_policy("idempotency_fail_open"):
                raise HTTPException(status_code=503, detail="Idempotency store unavailable") from exc
            existing_visit_id = None
        if existing_visit_id:
            existing = db.scalar(select(Visit).where(Visit.id == UUID(existing_visit_id), Visit.tenant_id == tenant_id))
            if existing is not None:
                idempotency_events_total.labels(operation="visits_create", result="hit").inc()
                return existing
    patient = db.scalar(select(Patient).where(Patient.id == payload.patient_id, Patient.tenant_id == tenant_id))
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    visit = Visit(tenant_id=tenant_id, patient_id=payload.patient_id, notes=payload.notes.strip())
    db.add(visit)
    db.flush()
    write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_user_id=UUID(claims["sub"]),
        action="visit.create",
        entity="visit",
        entity_id=str(visit.id),
        details={"patient_id": str(payload.patient_id)},
    )
    write_outbox_event(
        db,
        tenant_id=tenant_id,
        aggregate_type="visit",
        aggregate_id=str(visit.id),
        event_type="visit.created",
        payload={"visit_id": str(visit.id), "patient_id": str(payload.patient_id)},
    )
    db.commit()
    db.refresh(visit)
    invalidate_resource_list_cache("visits", str(tenant_id))
    if idempotency_key:
        try:
            redis_client.setex(f"idem:visits:{tenant_id}:{idempotency_key.strip()}", 24 * 3600, str(visit.id))
            idempotency_events_total.labels(operation="visits_create", result="write").inc()
        except redis.RedisError:
            idempotency_events_total.labels(operation="visits_create", result="redis_error_write").inc()
    return visit


@router.get("", response_model=list[VisitOut])
def list_visits(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    patient_id: UUID | None = Query(default=None),
    claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db_readonly),
):
    enforce_rate_limit(request, claims, limit_per_minute=240)
    tenant_id = str(claims["tenant_id"])
    params_hash = hashlib.sha256(f"{limit}:{offset}:{patient_id or ''}".encode("utf-8")).hexdigest()
    cache_version = get_resource_list_cache_version("visits", tenant_id)
    cache_key = list_cache_key("visits", tenant_id, params_hash, cache_version)
    cached_rows = get_json_cache(cache_key, resource="visits")
    if cached_rows is not None:
        return [VisitOut.model_validate(item) for item in cached_rows]
    has_build_lock = try_acquire_cache_build_lock(cache_key)
    if not has_build_lock:
        time.sleep(max(settings.list_cache_wait_on_lock_ms, 0) / 1000.0)
        cached_rows = get_json_cache(cache_key, resource="visits")
        if cached_rows is not None:
            return [VisitOut.model_validate(item) for item in cached_rows]

    try:
        stmt = select(Visit).where(Visit.tenant_id == UUID(tenant_id))
        if patient_id is not None:
            stmt = stmt.where(Visit.patient_id == patient_id)
        rows = db.scalars(
            stmt.order_by(Visit.created_at.desc()).offset(offset).limit(limit)
        ).all()
        if has_build_lock:
            serialized_rows = [VisitOut.model_validate(row).model_dump(mode="json") for row in rows]
            set_json_cache(cache_key, serialized_rows, settings.list_cache_ttl_seconds, resource="visits")
        return rows
    finally:
        if has_build_lock:
            release_cache_build_lock(cache_key)


@router.post("/bulk", response_model=list[VisitOut], status_code=status.HTTP_201_CREATED)
def create_visits_bulk(
    payload: VisitsBulkCreate,
    request: Request,
    claims: dict = Depends(require_roles("admin", "doctor", "nurse")),
    db: Session = Depends(get_db),
):
    tenant_id = UUID(claims["tenant_id"])
    enforce_rate_limit(request, claims, limit_per_minute=50)
    patient_ids = {item.patient_id for item in payload.items}
    existing_patient_ids = set(
        db.scalars(select(Patient.id).where(Patient.tenant_id == tenant_id, Patient.id.in_(patient_ids))).all()
    )
    missing = [str(pid) for pid in patient_ids if pid not in existing_patient_ids]
    if missing:
        raise HTTPException(status_code=404, detail=f"Patients not found: {', '.join(missing[:5])}")

    created: list[Visit] = []
    for item in payload.items:
        visit = Visit(tenant_id=tenant_id, patient_id=item.patient_id, notes=item.notes.strip())
        db.add(visit)
        db.flush()
        write_audit_log(
            db,
            tenant_id=tenant_id,
            actor_user_id=UUID(claims["sub"]),
            action="visit.bulk_create",
            entity="visit",
            entity_id=str(visit.id),
            details={"patient_id": str(item.patient_id)},
        )
        write_outbox_event(
            db,
            tenant_id=tenant_id,
            aggregate_type="visit",
            aggregate_id=str(visit.id),
            event_type="visit.created",
            payload={"visit_id": str(visit.id), "patient_id": str(item.patient_id)},
        )
        created.append(visit)
    db.commit()
    for visit in created:
        db.refresh(visit)
    invalidate_resource_list_cache("visits", str(tenant_id))
    return created
