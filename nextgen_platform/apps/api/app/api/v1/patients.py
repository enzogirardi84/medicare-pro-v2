import hashlib
import time
from uuid import UUID

from fastapi import APIRouter, Depends, File, Header, HTTPException, Query, Request, UploadFile, status
import redis
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import enforce_rate_limit, get_current_claims, require_roles
from app.domain.audit import write_audit_log
from app.domain.outbox import write_outbox_event
from app.domain.schemas import PatientCreate, PatientOut, PatientsBulkCreate
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
from app.infrastructure.metrics import idempotency_events_total, imports_circuit_open_total, imports_throttled_total
from app.infrastructure.models import ImportJob, Patient
from app.infrastructure.queue import enqueue_patients_csv_import

router = APIRouter(prefix="/patients", tags=["patients"])


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(
    payload: PatientCreate,
    request: Request,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    claims: dict = Depends(require_roles("admin", "doctor", "nurse")),
    db: Session = Depends(get_db),
):
    tenant_id = UUID(claims["tenant_id"])
    enforce_rate_limit(request, claims, limit_per_minute=90)
    if idempotency_key:
        idem_key = f"idem:patients:{tenant_id}:{idempotency_key.strip()}"
        try:
            existing_patient_id = redis_client.get(idem_key)
        except redis.RedisError as exc:
            idempotency_events_total.labels(operation="patients_create", result="redis_error_lookup").inc()
            if not get_resilience_policy("idempotency_fail_open"):
                raise HTTPException(status_code=503, detail="Idempotency store unavailable") from exc
            existing_patient_id = None
        if existing_patient_id:
            existing = db.scalar(select(Patient).where(Patient.id == UUID(existing_patient_id), Patient.tenant_id == tenant_id))
            if existing is not None:
                idempotency_events_total.labels(operation="patients_create", result="hit").inc()
                return existing
    patient = Patient(
        tenant_id=tenant_id,
        full_name=payload.full_name.strip(),
        document_number=payload.document_number.strip(),
    )
    db.add(patient)
    db.flush()
    write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_user_id=UUID(claims["sub"]),
        action="patient.create",
        entity="patient",
        entity_id=str(patient.id),
        details={"document_number": patient.document_number},
    )
    write_outbox_event(
        db,
        tenant_id=tenant_id,
        aggregate_type="patient",
        aggregate_id=str(patient.id),
        event_type="patient.created",
        payload={"patient_id": str(patient.id), "document_number": patient.document_number},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        detail = "Patient document already exists in this tenant"
        if hasattr(exc, 'orig') and exc.orig:
            detail = str(exc.orig).split('\n')[0][:255]
        raise HTTPException(status_code=409, detail=detail) from exc
    db.refresh(patient)
    invalidate_resource_list_cache("patients", str(tenant_id))
    if idempotency_key:
        try:
            redis_client.setex(f"idem:patients:{tenant_id}:{idempotency_key.strip()}", 24 * 3600, str(patient.id))
            idempotency_events_total.labels(operation="patients_create", result="write").inc()
        except redis.RedisError:
            idempotency_events_total.labels(operation="patients_create", result="redis_error_write").inc()
    return patient


@router.get("", response_model=list[PatientOut])
def list_patients(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    search: str | None = Query(default=None, min_length=2, max_length=255),
    claims: dict = Depends(get_current_claims),
    db: Session = Depends(get_db_readonly),
):
    enforce_rate_limit(request, claims, limit_per_minute=240)
    tenant_id = str(claims["tenant_id"])
    params_hash = hashlib.sha256(f"{limit}:{offset}:{search or ''}".encode("utf-8")).hexdigest()
    cache_version = get_resource_list_cache_version("patients", tenant_id)
    cache_key = list_cache_key("patients", tenant_id, params_hash, cache_version)
    cached_rows = get_json_cache(cache_key, resource="patients")
    if cached_rows is not None:
        return [PatientOut.model_validate(item) for item in cached_rows]
    has_build_lock = try_acquire_cache_build_lock(cache_key)
    if not has_build_lock:
        time.sleep(max(settings.list_cache_wait_on_lock_ms, 0) / 1000.0)
        cached_rows = get_json_cache(cache_key, resource="patients")
        if cached_rows is not None:
            return [PatientOut.model_validate(item) for item in cached_rows]

    try:
        stmt = select(Patient).where(Patient.tenant_id == UUID(tenant_id))
        if search:
            term = f"%{search.strip()}%"
            stmt = stmt.where(Patient.full_name.ilike(term))
        rows = db.scalars(
            stmt.order_by(Patient.created_at.desc()).offset(offset).limit(limit)
        ).all()
        if has_build_lock:
            serialized_rows = [PatientOut.model_validate(row).model_dump(mode="json") for row in rows]
            set_json_cache(cache_key, serialized_rows, settings.list_cache_ttl_seconds, resource="patients")
        return rows
    finally:
        if has_build_lock:
            release_cache_build_lock(cache_key)


@router.post("/bulk", response_model=list[PatientOut], status_code=status.HTTP_201_CREATED)
def create_patients_bulk(
    payload: PatientsBulkCreate,
    request: Request,
    claims: dict = Depends(require_roles("admin", "doctor", "nurse")),
    db: Session = Depends(get_db),
):
    tenant_id = UUID(claims["tenant_id"])
    enforce_rate_limit(request, claims, limit_per_minute=40)
    created: list[Patient] = []
    for item in payload.items:
        patient = Patient(
            tenant_id=tenant_id,
            full_name=item.full_name.strip(),
            document_number=item.document_number.strip(),
        )
        db.add(patient)
        db.flush()
        write_audit_log(
            db,
            tenant_id=tenant_id,
            actor_user_id=UUID(claims["sub"]),
            action="patient.bulk_create",
            entity="patient",
            entity_id=str(patient.id),
            details={"document_number": patient.document_number},
        )
        write_outbox_event(
            db,
            tenant_id=tenant_id,
            aggregate_type="patient",
            aggregate_id=str(patient.id),
            event_type="patient.created",
            payload={"patient_id": str(patient.id), "document_number": patient.document_number},
        )
        created.append(patient)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="One or more patient documents already exist") from exc
    for patient in created:
        db.refresh(patient)
    invalidate_resource_list_cache("patients", str(tenant_id))
    return created


@router.post("/import/csv", status_code=status.HTTP_202_ACCEPTED)
async def import_patients_csv(
    request: Request,
    file: UploadFile = File(...),
    claims: dict = Depends(require_roles("admin", "doctor")),
    db: Session = Depends(get_db),
):
    enforce_rate_limit(request, claims, limit_per_minute=20)
    tenant_id = UUID(claims["tenant_id"])
    import_cb_key = f"cb:imports:{tenant_id}"
    import_cb_strikes_key = f"cb:imports:strikes:{tenant_id}"
    try:
        if redis_client.get(import_cb_key) == "1":
            imports_circuit_open_total.inc()
            raise HTTPException(status_code=429, detail="Import circuit breaker is open for tenant")
    except redis.RedisError:
        # Fail-open para no bloquear imports por un incidente aislado de Redis.
        pass
    pending_imports = int(
        db.scalar(
            select(func.count())
            .select_from(ImportJob)
            .where(ImportJob.tenant_id == tenant_id, ImportJob.status.in_(("queued", "running")))
        )
        or 0
    )
    if pending_imports >= settings.import_max_pending_per_tenant:
        imports_throttled_total.inc()
        try:
            strike_count = redis_client.incr(import_cb_strikes_key)
            if strike_count == 1:
                redis_client.expire(import_cb_strikes_key, max(settings.import_circuit_breaker_window_seconds, 5))
            if strike_count >= settings.import_circuit_breaker_threshold:
                redis_client.setex(import_cb_key, max(settings.import_circuit_breaker_open_seconds, 30), "1")
        except redis.RedisError:
            # Si Redis falla, mantenemos solo el guardrail por pending_imports.
            pass
        raise HTTPException(
            status_code=429,
            detail=f"Too many import jobs pending for tenant (max {settings.import_max_pending_per_tenant})",
        )
    if not file.filename.lower().endswith(".csv"):
        raise HTTPException(status_code=400, detail="Only .csv file is accepted")
    content = (await file.read()).decode("utf-8", errors="ignore")
    if len(content) > 2_000_000:
        raise HTTPException(status_code=413, detail="CSV too large (max 2MB)")
    job = ImportJob(
        tenant_id=tenant_id,
        actor_user_id=UUID(claims["sub"]),
        kind="patients_csv",
        status="queued",
        rows_valid=0,
        rows_inserted=0,
        source_csv_text=content,
        errors_json="[]",
    )
    db.add(job)
    db.flush()
    task_id = enqueue_patients_csv_import(
        tenant_id=str(claims["tenant_id"]),
        actor_user_id=str(claims["sub"]),
        import_job_id=str(job.id),
        csv_content=content,
    )
    job.task_id = task_id
    db.add(job)
    db.commit()
    try:
        redis_client.delete(import_cb_strikes_key)
    except redis.RedisError as _exc:
        import logging
        logging.getLogger("api.patients").debug(f"fallo_redis_delete_strikes:{type(_exc).__name__}")
    return {"status": "queued", "task_id": task_id, "import_job_id": str(job.id)}


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: UUID, request: Request, claims: dict = Depends(get_current_claims), db: Session = Depends(get_db_readonly)
):
    enforce_rate_limit(request, claims, limit_per_minute=240)
    patient = db.scalar(
        select(Patient).where(Patient.id == patient_id, Patient.tenant_id == UUID(claims["tenant_id"]))
    )
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found")
    return patient
