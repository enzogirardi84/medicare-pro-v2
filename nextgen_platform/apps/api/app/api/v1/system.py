import re
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.config import settings
from app.core.resilience import (
    RESILIENCE_POLICIES,
    append_resilience_history,
    clear_resilience_policy,
    get_resilience_history,
    get_resilience_policy,
    set_resilience_policy,
)
from app.domain.audit import write_audit_log
from app.domain.schemas import ResilienceSwitchRequest
from app.infrastructure.cache import redis_client
from app.infrastructure.db import get_db
from app.infrastructure.metrics import import_jobs_retried_total, import_jobs_status_gauge, resilience_ops_total
from app.infrastructure.models import ImportJob, ImportJobError, OutboxEvent, Patient, Visit
from app.infrastructure.queue import enqueue_patients_csv_import, get_task_status
from app.services.outbox_service import flush_outbox_for_tenant, outbox_status_for_tenant
from app.services.self_heal import get_self_heal_status, reset_self_heal_cooldown, run_self_heal_cycle

router = APIRouter(prefix="/system", tags=["system"])
CHANGE_TICKET_PATTERN = re.compile(r"^[A-Z]{2,10}-\d{1,8}$")


def _update_import_jobs_metrics(db: Session, tenant_id: UUID) -> dict[str, int]:
    rows = db.scalars(select(ImportJob.status).where(ImportJob.tenant_id == tenant_id)).all()
    counts: dict[str, int] = {}
    for status in rows:
        key = str(status or "unknown")
        counts[key] = counts.get(key, 0) + 1
    for status, value in counts.items():
        import_jobs_status_gauge.labels(status=status).set(value)
    return counts


def _acquire_tenant_lock(lock_key: str, ttl_seconds: int = 30) -> bool:
    return bool(redis_client.set(lock_key, "1", ex=max(5, ttl_seconds), nx=True))


def _release_tenant_lock(lock_key: str) -> None:
    try:
        redis_client.delete(lock_key)
    except Exception:
        pass


def _circuit_open(key: str) -> bool:
    try:
        return redis_client.get(key) == "1"
    except Exception:
        return False


def _open_circuit(key: str, seconds: int = 120) -> None:
    try:
        redis_client.setex(key, max(30, seconds), "1")
    except Exception:
        pass


def _normalize_and_validate_change_ticket(change_ticket: str | None) -> str | None:
    normalized = (change_ticket or "").strip().upper()
    if settings.environment.lower() == "production":
        if not normalized:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="change_ticket is required in production",
            )
        if not CHANGE_TICKET_PATTERN.match(normalized):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="change_ticket must match pattern ABC-1234",
            )
    elif normalized and not CHANGE_TICKET_PATTERN.match(normalized):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="change_ticket must match pattern ABC-1234",
        )
    return normalized or None


def _validate_change_ticket_for_precheck(change_ticket: str | None) -> tuple[bool, str | None, str | None]:
    try:
        normalized = _normalize_and_validate_change_ticket(change_ticket)
        return True, normalized, None
    except HTTPException as exc:
        return False, None, str(exc.detail)


@router.get("/resilience/status")
def resilience_status(claims: dict = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    tenant_id = UUID(claims["tenant_id"])
    db_ok = False
    redis_ok = False
    try:
        db.execute(select(1))
        db_ok = True
    except Exception:
        db_ok = False
    try:
        redis_ok = bool(redis_client.ping())
    except Exception:
        redis_ok = False

    return {
        "tenant_id": str(tenant_id),
        "dependencies": {"db": db_ok, "redis": redis_ok},
        "limits": {
            "resilience_rollback_max_index": settings.resilience_rollback_max_index,
        },
        "requirements": {
            "change_ticket_required": settings.environment.lower() == "production",
            "change_ticket_pattern": "ABC-1234",
            "reason_min_length": 8,
            "manual_ops_use_reason_query": True,
        },
        "policies": {
            "rate_limit_fail_open": {
                "effective": get_resilience_policy("rate_limit_fail_open"),
                "default": settings.rate_limit_fail_open,
            },
            "idempotency_fail_open": {
                "effective": get_resilience_policy("idempotency_fail_open"),
                "default": settings.idempotency_fail_open,
            },
            "token_revocation_fail_open": {
                "effective": get_resilience_policy("token_revocation_fail_open"),
                "default": settings.token_revocation_fail_open,
            },
        },
        "circuits": {
            "outbox_open": _circuit_open(f"cb:outbox:{tenant_id}"),
            "imports_open": _circuit_open(f"cb:imports:{tenant_id}"),
        },
    }


@router.get("/self-heal/status")
def self_heal_status(_: dict = Depends(require_roles("admin"))):
    return get_self_heal_status()


@router.post("/self-heal/run")
def self_heal_run(
    reason: str = Query(min_length=8, max_length=500),
    change_ticket: str | None = Query(default=None),
    claims: dict = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    resilience_ops_total.labels(operation="self_heal_run", outcome="attempt").inc()
    tenant_id = UUID(claims["tenant_id"])
    normalized_change_ticket = _normalize_and_validate_change_ticket(change_ticket)
    result = run_self_heal_cycle()
    write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_user_id=UUID(claims["sub"]),
        action="system.self_heal_run",
        entity="system",
        entity_id=str(tenant_id),
        details={"reason": reason, "change_ticket": normalized_change_ticket, "self_heal": result},
    )
    db.commit()
    resilience_ops_total.labels(operation="self_heal_run", outcome="ok").inc()
    return {
        "status": "ok",
        "reason": reason,
        "change_ticket": normalized_change_ticket,
        "self_heal": result,
    }


@router.post("/self-heal/reset-cooldown")
def self_heal_reset_cooldown(
    reason: str = Query(min_length=8, max_length=500),
    change_ticket: str | None = Query(default=None),
    claims: dict = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    resilience_ops_total.labels(operation="self_heal_reset_cooldown", outcome="attempt").inc()
    tenant_id = UUID(claims["tenant_id"])
    normalized_change_ticket = _normalize_and_validate_change_ticket(change_ticket)
    result = reset_self_heal_cooldown()
    write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_user_id=UUID(claims["sub"]),
        action="system.self_heal_reset_cooldown",
        entity="system",
        entity_id=str(tenant_id),
        details={
            "reason": reason,
            "change_ticket": normalized_change_ticket,
            "result": result.get("cooldown_reset", {}),
        },
    )
    db.commit()
    resilience_ops_total.labels(operation="self_heal_reset_cooldown", outcome="ok").inc()
    return {
        "status": "ok",
        "reason": reason,
        "change_ticket": normalized_change_ticket,
        "self_heal": result,
    }


@router.post("/resilience/switch")
def resilience_switch(
    payload: ResilienceSwitchRequest,
    claims: dict = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    resilience_ops_total.labels(operation="switch", outcome="attempt").inc()
    tenant_id = UUID(claims["tenant_id"])
    change_ticket = _normalize_and_validate_change_ticket(payload.change_ticket)
    updates: dict[str, bool] = {}
    defaults_restored: list[str] = []

    for policy_name in ("rate_limit_fail_open", "idempotency_fail_open", "token_revocation_fail_open"):
        value = getattr(payload, policy_name)
        if value is None:
            clear_resilience_policy(policy_name)
            defaults_restored.append(policy_name)
            continue
        set_resilience_policy(policy_name, enabled=value, ttl_seconds=payload.ttl_seconds)
        updates[policy_name] = bool(value)

    effective = {
        "rate_limit_fail_open": get_resilience_policy("rate_limit_fail_open"),
        "idempotency_fail_open": get_resilience_policy("idempotency_fail_open"),
        "token_revocation_fail_open": get_resilience_policy("token_revocation_fail_open"),
    }
    append_resilience_history(
        tenant_id=str(tenant_id),
        actor_user_id=str(claims["sub"]),
        updates=updates,
        defaults_restored=defaults_restored,
        ttl_seconds=payload.ttl_seconds,
        effective=effective,
        reason=payload.reason,
        change_ticket=change_ticket,
    )
    write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_user_id=UUID(claims["sub"]),
        action="system.resilience_switch",
        entity="system",
        entity_id=str(tenant_id),
        details={
            "updates": updates,
            "defaults_restored": defaults_restored,
            "ttl_seconds": payload.ttl_seconds,
            "reason": payload.reason,
            "change_ticket": change_ticket,
        },
    )
    db.commit()
    resilience_ops_total.labels(operation="switch", outcome="ok").inc()
    return {"status": "ok", "updated": updates, "defaults_restored": defaults_restored, "effective": effective}


@router.get("/resilience/history")
def resilience_history(
    limit: int = Query(default=20, ge=1, le=100),
    claims: dict = Depends(require_roles("admin")),
):
    tenant_id = str(claims["tenant_id"])
    return {"tenant_id": tenant_id, "items": get_resilience_history(tenant_id=tenant_id, limit=limit)}


@router.get("/resilience/precheck")
def resilience_precheck(
    operation: Literal["switch", "rollback_last", "rollback_index"] = Query(...),
    dry_run: bool = Query(default=False),
    confirm: bool = Query(default=False),
    reason: str | None = Query(default=None),
    change_ticket: str | None = Query(default=None),
    index: int | None = Query(default=None),
    ttl_seconds: int | None = Query(default=None),
    rate_limit_fail_open: bool | None = Query(default=None),
    idempotency_fail_open: bool | None = Query(default=None),
    token_revocation_fail_open: bool | None = Query(default=None),
    claims: dict = Depends(require_roles("admin")),
):
    resilience_ops_total.labels(operation=f"precheck_{operation}", outcome="attempt").inc()
    issues: list[str] = []
    normalized_reason = (reason or "").strip()
    if len(normalized_reason) < 8:
        issues.append("reason must have at least 8 characters")
    if len(normalized_reason) > 500:
        issues.append("reason must have at most 500 characters")

    ticket_ok, normalized_ticket, ticket_error = _validate_change_ticket_for_precheck(change_ticket)
    if not ticket_ok and ticket_error:
        issues.append(ticket_error)

    if operation == "switch":
        if ttl_seconds is None:
            ttl_seconds = 1800
        if ttl_seconds < 30 or ttl_seconds > 86400:
            issues.append("ttl_seconds must be between 30 and 86400")
        if (
            rate_limit_fail_open is None
            and idempotency_fail_open is None
            and token_revocation_fail_open is None
        ):
            issues.append("at least one policy value must be provided for switch")
    elif operation == "rollback_last":
        if not dry_run and not confirm:
            issues.append("confirm=true is required when dry_run=false")
    elif operation == "rollback_index":
        if index is None:
            issues.append("index is required for rollback_index")
        else:
            if index < 0:
                issues.append("index must be >= 0")
            if index > settings.resilience_rollback_max_index:
                issues.append("index exceeds resilience_rollback_max_index")
            tenant_id = str(claims["tenant_id"])
            history = get_resilience_history(tenant_id=tenant_id, limit=max(1, index + 1))
            if not history or index >= len(history):
                issues.append("index does not exist in current history window")
        if not dry_run and not confirm:
            issues.append("confirm=true is required when dry_run=false")

    ok = len(issues) == 0
    resilience_ops_total.labels(operation=f"precheck_{operation}", outcome="ok" if ok else "invalid").inc()
    return {
        "ok": ok,
        "operation": operation,
        "issues": issues,
        "normalized": {
            "reason": normalized_reason if normalized_reason else None,
            "change_ticket": normalized_ticket,
            "dry_run": dry_run,
            "confirm": confirm,
            "index": index,
            "ttl_seconds": ttl_seconds,
        },
    }


def _resolve_effective_snapshot_from_history(history_item: dict | None) -> dict[str, bool]:
    snapshot: dict[str, bool] = {}
    if history_item and isinstance(history_item.get("effective"), dict):
        for policy_name in RESILIENCE_POLICIES:
            snapshot[policy_name] = bool(history_item["effective"].get(policy_name, getattr(settings, policy_name)))
        return snapshot
    for policy_name in RESILIENCE_POLICIES:
        snapshot[policy_name] = bool(getattr(settings, policy_name))
    return snapshot


def _apply_resilience_snapshot(snapshot: dict[str, bool], ttl_seconds: int = 3600) -> None:
    for policy_name, enabled in snapshot.items():
        set_resilience_policy(policy_name, enabled=enabled, ttl_seconds=ttl_seconds)


@router.post("/resilience/rollback-last")
def resilience_rollback_last(
    dry_run: bool = Query(default=False),
    confirm: bool = Query(default=False),
    reason: str = Query(min_length=8, max_length=500),
    change_ticket: str | None = Query(default=None),
    claims: dict = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    resilience_ops_total.labels(operation="rollback_last", outcome="attempt").inc()
    tenant_id = UUID(claims["tenant_id"])
    normalized_change_ticket = _normalize_and_validate_change_ticket(change_ticket)
    history = get_resilience_history(tenant_id=str(tenant_id), limit=2)
    if not history:
        resilience_ops_total.labels(operation="rollback_last", outcome="no_history").inc()
        return {"status": "no_history"}

    current_effective = {
        "rate_limit_fail_open": get_resilience_policy("rate_limit_fail_open"),
        "idempotency_fail_open": get_resilience_policy("idempotency_fail_open"),
        "token_revocation_fail_open": get_resilience_policy("token_revocation_fail_open"),
    }
    target_effective = _resolve_effective_snapshot_from_history(history[1] if len(history) >= 2 else None)
    if dry_run:
        resilience_ops_total.labels(operation="rollback_last", outcome="dry_run").inc()
        return {"status": "dry_run", "current": current_effective, "effective": target_effective}
    if not confirm:
        resilience_ops_total.labels(operation="rollback_last", outcome="confirmation_required").inc()
        return {"status": "confirmation_required", "message": "Set confirm=true to apply rollback"}
    _apply_resilience_snapshot(target_effective, ttl_seconds=3600)

    append_resilience_history(
        tenant_id=str(tenant_id),
        actor_user_id=str(claims["sub"]),
        updates=target_effective,
        defaults_restored=[],
        ttl_seconds=3600,
        effective=target_effective,
        reason=reason,
        change_ticket=normalized_change_ticket,
    )
    write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_user_id=UUID(claims["sub"]),
        action="system.resilience_rollback_last",
        entity="system",
        entity_id=str(tenant_id),
        details={"effective": target_effective, "reason": reason, "change_ticket": normalized_change_ticket},
    )
    db.commit()
    resilience_ops_total.labels(operation="rollback_last", outcome="ok").inc()
    return {"status": "ok", "effective": target_effective}


@router.post("/resilience/rollback/{index}")
def resilience_rollback_index(
    index: int,
    dry_run: bool = Query(default=False),
    confirm: bool = Query(default=False),
    reason: str = Query(min_length=8, max_length=500),
    change_ticket: str | None = Query(default=None),
    claims: dict = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    resilience_ops_total.labels(operation="rollback_index", outcome="attempt").inc()
    if index < 0:
        resilience_ops_total.labels(operation="rollback_index", outcome="invalid_index").inc()
        return {"status": "invalid_index"}
    if index > settings.resilience_rollback_max_index:
        resilience_ops_total.labels(operation="rollback_index", outcome="index_too_old").inc()
        return {
            "status": "index_too_old",
            "max_index": settings.resilience_rollback_max_index,
            "message": "Requested index exceeds configured rollback window",
        }
    tenant_id = UUID(claims["tenant_id"])
    normalized_change_ticket = _normalize_and_validate_change_ticket(change_ticket)
    history = get_resilience_history(tenant_id=str(tenant_id), limit=max(1, index + 1))
    if not history or index >= len(history):
        resilience_ops_total.labels(operation="rollback_index", outcome="not_found").inc()
        return {"status": "not_found"}

    current_effective = {
        "rate_limit_fail_open": get_resilience_policy("rate_limit_fail_open"),
        "idempotency_fail_open": get_resilience_policy("idempotency_fail_open"),
        "token_revocation_fail_open": get_resilience_policy("token_revocation_fail_open"),
    }
    target_effective = _resolve_effective_snapshot_from_history(history[index])
    if dry_run:
        resilience_ops_total.labels(operation="rollback_index", outcome="dry_run").inc()
        return {"status": "dry_run", "index": index, "current": current_effective, "effective": target_effective}
    if not confirm:
        resilience_ops_total.labels(operation="rollback_index", outcome="confirmation_required").inc()
        return {"status": "confirmation_required", "message": "Set confirm=true to apply rollback", "index": index}
    _apply_resilience_snapshot(target_effective, ttl_seconds=3600)
    append_resilience_history(
        tenant_id=str(tenant_id),
        actor_user_id=str(claims["sub"]),
        updates=target_effective,
        defaults_restored=[],
        ttl_seconds=3600,
        effective=target_effective,
        reason=reason,
        change_ticket=normalized_change_ticket,
    )
    write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_user_id=UUID(claims["sub"]),
        action="system.resilience_rollback_index",
        entity="system",
        entity_id=str(tenant_id),
        details={
            "index": index,
            "effective": target_effective,
            "reason": reason,
            "change_ticket": normalized_change_ticket,
        },
    )
    db.commit()
    resilience_ops_total.labels(operation="rollback_index", outcome="ok").inc()
    return {"status": "ok", "index": index, "effective": target_effective}


@router.post("/outbox/flush")
def flush_outbox(
    reason: str = Query(min_length=8, max_length=500),
    change_ticket: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=10_000),
    claims: dict = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    tenant_id = UUID(claims["tenant_id"])
    normalized_change_ticket = _normalize_and_validate_change_ticket(change_ticket)
    if _circuit_open(f"cb:outbox:{tenant_id}"):
        return {"status": "circuit_open", "message": "outbox circuit breaker is open for this tenant"}
    lock_key = f"lock:outbox_flush:{tenant_id}"
    if not _acquire_tenant_lock(lock_key, ttl_seconds=30):
        return {"status": "busy", "message": "outbox flush already running for tenant"}
    try:
        result = flush_outbox_for_tenant(db, tenant_id=tenant_id, limit=limit)
        if int(result.get("failed", 0)) >= 25:
            _open_circuit(f"cb:outbox:{tenant_id}", seconds=180)
        write_audit_log(
            db,
            tenant_id=tenant_id,
            actor_user_id=UUID(claims["sub"]),
            action="system.outbox_flush",
            entity="system",
            entity_id=str(tenant_id),
            details={
                "limit": limit,
                "result": result,
                "reason": reason,
                "change_ticket": normalized_change_ticket,
            },
        )
        db.commit()
        return result
    finally:
        _release_tenant_lock(lock_key)


@router.get("/outbox/status")
def outbox_status(claims: dict = Depends(require_roles("admin")), db: Session = Depends(get_db)):
    tenant_id = UUID(claims["tenant_id"])
    return outbox_status_for_tenant(db, tenant_id=tenant_id)


@router.get("/tasks/{task_id}")
def task_status(task_id: str, _: dict = Depends(require_roles("admin", "doctor"))):
    return get_task_status(task_id)


@router.get("/import-jobs/{import_job_id}")
def import_job_status(import_job_id: UUID, claims: dict = Depends(require_roles("admin", "doctor")), db: Session = Depends(get_db)):
    tenant_id = UUID(claims["tenant_id"])
    _update_import_jobs_metrics(db, tenant_id)
    job = db.scalar(select(ImportJob).where(ImportJob.id == import_job_id, ImportJob.tenant_id == tenant_id))
    if job is None:
        return {"status": "not_found"}
    return {
        "id": str(job.id),
        "task_id": job.task_id,
        "kind": job.kind,
        "status": job.status,
        "rows_valid": int(job.rows_valid),
        "rows_inserted": int(job.rows_inserted),
        "errors_json": job.errors_json,
        "created_at": job.created_at.isoformat(),
        "updated_at": job.updated_at.isoformat(),
    }


@router.get("/import-jobs/{import_job_id}/errors")
def import_job_errors(import_job_id: UUID, claims: dict = Depends(require_roles("admin", "doctor")), db: Session = Depends(get_db)):
    tenant_id = UUID(claims["tenant_id"])
    job = db.scalar(select(ImportJob).where(ImportJob.id == import_job_id, ImportJob.tenant_id == tenant_id))
    if job is None:
        return {"status": "not_found", "errors": []}
    rows = db.scalars(
        select(ImportJobError).where(ImportJobError.import_job_id == import_job_id).order_by(ImportJobError.created_at.asc())
    ).all()
    return {
        "status": "ok",
        "errors": [
            {"line_number": int(r.line_number), "code": r.code, "message": r.message, "created_at": r.created_at.isoformat()}
            for r in rows
        ],
    }


@router.get("/import-jobs/{import_job_id}/errors.csv")
def import_job_errors_csv(
    import_job_id: UUID, claims: dict = Depends(require_roles("admin", "doctor")), db: Session = Depends(get_db)
):
    tenant_id = UUID(claims["tenant_id"])
    job = db.scalar(select(ImportJob).where(ImportJob.id == import_job_id, ImportJob.tenant_id == tenant_id))
    if job is None:
        return Response("status,message\nnot_found,import_job_not_found\n", media_type="text/csv")
    rows = db.scalars(
        select(ImportJobError).where(ImportJobError.import_job_id == import_job_id).order_by(ImportJobError.created_at.asc())
    ).all()
    lines = ["line_number,code,message,created_at"]
    for r in rows:
        msg = str(r.message or "").replace('"', '""')
        lines.append(f'{int(r.line_number)},"{r.code}","{msg}","{r.created_at.isoformat()}"')
    return Response("\n".join(lines) + "\n", media_type="text/csv")


@router.post("/import-jobs/{import_job_id}/retry")
def retry_import_job(
    import_job_id: UUID,
    reason: str = Query(min_length=8, max_length=500),
    change_ticket: str | None = Query(default=None),
    claims: dict = Depends(require_roles("admin", "doctor")),
    db: Session = Depends(get_db),
):
    tenant_id = UUID(claims["tenant_id"])
    normalized_change_ticket = _normalize_and_validate_change_ticket(change_ticket)
    job = db.scalar(select(ImportJob).where(ImportJob.id == import_job_id, ImportJob.tenant_id == tenant_id))
    if job is None:
        return {"status": "not_found"}
    if job.kind != "patients_csv":
        return {"status": "unsupported_kind"}
    if not job.source_csv_text:
        return {"status": "missing_source_csv"}
    task_id = enqueue_patients_csv_import(
        tenant_id=str(job.tenant_id),
        actor_user_id=str(job.actor_user_id),
        import_job_id=str(job.id),
        csv_content=job.source_csv_text,
    )
    job.task_id = task_id
    job.status = "queued"
    db.add(job)
    write_audit_log(
        db,
        tenant_id=tenant_id,
        actor_user_id=UUID(claims["sub"]),
        action="system.import_retry_one",
        entity="import_job",
        entity_id=str(job.id),
        details={
            "task_id": task_id,
            "reason": reason,
            "change_ticket": normalized_change_ticket,
        },
    )
    db.commit()
    import_jobs_retried_total.inc()
    _update_import_jobs_metrics(db, tenant_id)
    return {
        "status": "queued",
        "task_id": task_id,
        "import_job_id": str(job.id),
        "reason": reason,
        "change_ticket": normalized_change_ticket,
    }


@router.post("/import-jobs/retry-failed")
def retry_failed_import_jobs(
    reason: str = Query(min_length=8, max_length=500),
    change_ticket: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    claims: dict = Depends(require_roles("admin")),
    db: Session = Depends(get_db),
):
    tenant_id = UUID(claims["tenant_id"])
    normalized_change_ticket = _normalize_and_validate_change_ticket(change_ticket)
    if _circuit_open(f"cb:imports:{tenant_id}"):
        return {"status": "circuit_open", "message": "imports circuit breaker is open for this tenant"}
    lock_key = f"lock:import_retry_failed:{tenant_id}"
    if not _acquire_tenant_lock(lock_key, ttl_seconds=60):
        return {"status": "busy", "message": "retry-failed already running for tenant"}
    jobs = db.scalars(
        select(ImportJob)
        .where(
            ImportJob.tenant_id == tenant_id,
            ImportJob.kind == "patients_csv",
            ImportJob.status.in_(("failed", "completed_with_errors")),
            ImportJob.source_csv_text.is_not(None),
        )
        .order_by(ImportJob.updated_at.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    try:
        retried = 0
        for job in jobs:
            task_id = enqueue_patients_csv_import(
                tenant_id=str(job.tenant_id),
                actor_user_id=str(job.actor_user_id),
                import_job_id=str(job.id),
                csv_content=str(job.source_csv_text or ""),
            )
            job.task_id = task_id
            job.status = "queued"
            db.add(job)
            retried += 1
        if retried > 0:
            write_audit_log(
                db,
                tenant_id=tenant_id,
                actor_user_id=UUID(claims["sub"]),
                action="system.import_retry_failed_batch",
                entity="import_job",
                entity_id=str(tenant_id),
                details={
                    "limit": limit,
                    "retried": retried,
                    "reason": reason,
                    "change_ticket": normalized_change_ticket,
                },
            )
        db.commit()
        if retried > 0:
            import_jobs_retried_total.inc(retried)
        if retried >= 80:
            _open_circuit(f"cb:imports:{tenant_id}", seconds=180)
        _update_import_jobs_metrics(db, tenant_id)
        return {"status": "ok", "retried": retried}
    finally:
        _release_tenant_lock(lock_key)


@router.get("/tenant/metrics")
def tenant_metrics(claims: dict = Depends(require_roles("admin", "doctor")), db: Session = Depends(get_db)):
    tenant_id = UUID(claims["tenant_id"])
    _update_import_jobs_metrics(db, tenant_id)
    patients_count = int(db.scalar(select(func.count()).select_from(Patient).where(Patient.tenant_id == tenant_id)) or 0)
    visits_count = int(db.scalar(select(func.count()).select_from(Visit).where(Visit.tenant_id == tenant_id)) or 0)
    outbox_counts = outbox_status_for_tenant(db, tenant_id=tenant_id)
    import_counts = _update_import_jobs_metrics(db, tenant_id)
    failed_jobs = int(
        db.scalar(
            select(func.count())
            .select_from(ImportJob)
            .where(ImportJob.tenant_id == tenant_id, ImportJob.status.in_(("failed", "completed_with_errors")))
        )
        or 0
    )
    dead_letter_count = int(
        db.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.tenant_id == tenant_id, OutboxEvent.status == "dead_letter"))
        or 0
    )
    return {
        "tenant_id": str(tenant_id),
        "patients_count": patients_count,
        "visits_count": visits_count,
        "outbox": outbox_counts,
        "imports": import_counts,
        "failed_import_jobs": failed_jobs,
        "outbox_dead_letter_count": dead_letter_count,
    }
