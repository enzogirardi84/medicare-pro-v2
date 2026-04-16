import asyncio
import ipaddress
import time
from datetime import datetime, timezone
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
import redis
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1 import api_v1_router
from app.core.config import settings
from app.infrastructure.cache import redis_client
from app.infrastructure.db import SessionLocal
from app.infrastructure.metrics import (
    api_build_info,
    api_error_responses_total,
    api_inflight_requests_gauge,
    api_payload_too_large_total,
    api_request_rejections_total,
)
from app.services.outbox_scheduler import start_outbox_scheduler
from app.services.self_heal import start_self_heal_autopilot

app = FastAPI(title="MediCare NextGen API", version="0.2.0")
_request_semaphore = asyncio.Semaphore(max(settings.api_max_inflight_requests, 1))
_priority_slots = max(settings.api_reserved_inflight_for_priority, 0)
_inflight_requests = 0
_payload_guard_allowlist_raw = ""
_payload_guard_allowlist_ips: set[str] = set()
_payload_guard_allowlist_networks: list[object] = []

app.include_router(api_v1_router)

if settings.enable_metrics:
    Instrumentator().instrument(app).expose(app)

start_outbox_scheduler()
start_self_heal_autopilot()
_api_version_header = app.version
api_build_info.labels(
    version=_api_version_header,
    deploy_id=settings.deploy_id,
    git_sha=settings.git_sha,
    environment=settings.environment,
    region=settings.region,
    node_id=settings.node_id,
).set(1)


def _build_metadata() -> dict:
    return {
        "version": _api_version_header,
        "deploy_id": settings.deploy_id,
        "git_sha": settings.git_sha,
        "region": settings.region,
        "node_id": settings.node_id,
    }


def _error_payload(
    code: str,
    message: str,
    request_id: str,
    status_code: int,
    details: dict | None = None,
) -> dict:
    payload = {
        "error": {
            "code": code,
            "message": message,
            "request_id": request_id,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
    }
    if details:
        payload["error"]["details"] = details
    api_error_responses_total.labels(code=code, status=str(status_code)).inc()
    return payload


def _priority_path_prefixes() -> tuple[str, ...]:
    raw = settings.api_priority_paths.strip()
    if not raw:
        return tuple()
    return tuple(item.strip() for item in raw.split(",") if item.strip())


def _is_priority_request(path: str) -> bool:
    for prefix in _priority_path_prefixes():
        if path.startswith(prefix):
            return True
    return False


def _payload_guard_keys(ip: str) -> tuple[str, str]:
    return (f"payload_guard:strikes:{ip}", f"payload_guard:blocked:{ip}")


def _payload_guard_allowlist() -> set[str]:
    global _payload_guard_allowlist_raw, _payload_guard_allowlist_ips, _payload_guard_allowlist_networks
    raw = settings.api_payload_guard_ip_allowlist.strip()
    if raw == _payload_guard_allowlist_raw:
        return _payload_guard_allowlist_ips
    ips: set[str] = set()
    networks: list[object] = []
    for item in (part.strip() for part in raw.split(",") if part.strip()):
        try:
            if "/" in item:
                networks.append(ipaddress.ip_network(item, strict=False))
            else:
                ips.add(str(ipaddress.ip_address(item)))
        except ValueError:
            # Ignore invalid allowlist entries to keep middleware fail-open.
            continue
    _payload_guard_allowlist_raw = raw
    _payload_guard_allowlist_ips = ips
    _payload_guard_allowlist_networks = networks
    return _payload_guard_allowlist_ips


def _is_payload_guard_allowlisted(ip: str) -> bool:
    allowed_ips = _payload_guard_allowlist()
    if ip in allowed_ips:
        return True
    try:
        parsed_ip = ipaddress.ip_address(ip)
    except ValueError:
        return False
    return any(parsed_ip in network for network in _payload_guard_allowlist_networks)


def _client_ip(request: Request) -> str:
    forwarded_for = request.headers.get("x-forwarded-for", "").strip()
    if forwarded_for:
        return forwarded_for.split(",")[0].strip() or "unknown"
    return request.client.host if request.client else "unknown"


def _inflight_inc() -> int:
    global _inflight_requests
    _inflight_requests += 1
    api_inflight_requests_gauge.set(_inflight_requests)
    return _inflight_requests


def _inflight_dec() -> int:
    global _inflight_requests
    _inflight_requests = max(_inflight_requests - 1, 0)
    api_inflight_requests_gauge.set(_inflight_requests)
    return _inflight_requests


def _set_standard_response_headers(response: JSONResponse) -> None:
    response.headers["x-api-version"] = _api_version_header
    response.headers["x-environment"] = settings.environment
    response.headers["x-deploy-id"] = settings.deploy_id
    response.headers["x-git-sha"] = settings.git_sha
    response.headers["x-region"] = settings.region
    response.headers["x-node-id"] = settings.node_id
    response.headers["x-content-type-options"] = "nosniff"
    response.headers["x-frame-options"] = "DENY"
    response.headers["referrer-policy"] = "no-referrer"


@app.middleware("http")
async def request_guardrails_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    request.state.request_id = request_id
    start = time.perf_counter()
    ip = _client_ip(request)
    max_body = max(settings.api_max_request_body_bytes, 1024)
    payload_methods = {"POST", "PUT", "PATCH"}
    should_check_payload_size = request.method in payload_methods
    is_payload_allowlisted = _is_payload_guard_allowlisted(ip)
    should_track_payload_abuse = should_check_payload_size and not is_payload_allowlisted
    strikes_key, blocked_key = _payload_guard_keys(ip)
    if should_track_payload_abuse:
        try:
            if redis_client.get(blocked_key) == "1":
                api_request_rejections_total.labels(reason="payload_too_large_blocked").inc()
                retry_after_seconds = max(settings.api_payload_reject_block_seconds, 1)
                response = JSONResponse(
                    status_code=429,
                    content=_error_payload(
                        code="payload_abuse_blocked",
                        message="Client temporarily blocked due to repeated oversized payloads.",
                        request_id=request_id,
                        status_code=429,
                        details={"retry_after_seconds": retry_after_seconds},
                    ),
                )
                response.headers["x-request-id"] = request_id
                response.headers["retry-after"] = str(retry_after_seconds)
                response.headers["x-error-code"] = "payload_abuse_blocked"
                _set_standard_response_headers(response)
                return response
        except redis.RedisError:
            # Fail-open: no bloquear tráfico por incidencia puntual en Redis.
            pass
    content_length = request.headers.get("content-length")
    if should_check_payload_size and content_length:
        try:
            if int(content_length) > max_body:
                api_request_rejections_total.labels(reason="payload_too_large").inc()
                api_payload_too_large_total.labels(allowlisted="true" if is_payload_allowlisted else "false").inc()
                if should_track_payload_abuse:
                    try:
                        strikes = redis_client.incr(strikes_key)
                        if strikes == 1:
                            redis_client.expire(strikes_key, max(settings.api_payload_reject_window_seconds, 5))
                        if strikes >= max(settings.api_payload_reject_threshold, 1):
                            redis_client.setex(blocked_key, max(settings.api_payload_reject_block_seconds, 5), "1")
                    except redis.RedisError:
                        pass
                response = JSONResponse(
                    status_code=413,
                    content=_error_payload(
                        code="payload_too_large",
                        message=f"Payload exceeds limit ({max_body} bytes)",
                        request_id=request_id,
                        status_code=413,
                    ),
                )
                response.headers["x-request-id"] = request_id
                response.headers["x-error-code"] = "payload_too_large"
                _set_standard_response_headers(response)
                return response
        except ValueError:
            pass
    max_inflight = max(settings.api_max_inflight_requests, 1)
    regular_capacity = max(max_inflight - _priority_slots, 1)
    is_priority = _is_priority_request(request.url.path)
    # Preserve reserved slots for critical endpoints during saturation.
    current_inflight = _inflight_requests
    if (not is_priority) and current_inflight >= regular_capacity:
        api_request_rejections_total.labels(reason="priority_lane_reserved").inc()
        retry_after_seconds = max(settings.api_retry_after_busy_seconds, 1)
        response = JSONResponse(
            status_code=503,
            content=_error_payload(
                code="server_busy",
                message="Server is handling high concurrency, please retry.",
                request_id=request_id,
                status_code=503,
                details={"retry_after_seconds": retry_after_seconds},
            ),
        )
        response.headers["x-request-id"] = request_id
        response.headers["retry-after"] = str(retry_after_seconds)
        response.headers["x-error-code"] = "server_busy"
        _set_standard_response_headers(response)
        return response
    acquire_timeout_seconds = max(settings.api_inflight_acquire_timeout_ms, 1) / 1000
    acquired = False
    try:
        await asyncio.wait_for(_request_semaphore.acquire(), timeout=acquire_timeout_seconds)
        acquired = True
    except TimeoutError:
        api_request_rejections_total.labels(reason="inflight_limit_exceeded").inc()
        retry_after_seconds = max(settings.api_retry_after_busy_seconds, 1)
        response = JSONResponse(
            status_code=503,
            content=_error_payload(
                code="server_busy",
                message="Server is handling high concurrency, please retry.",
                request_id=request_id,
                status_code=503,
                details={"retry_after_seconds": retry_after_seconds},
            ),
        )
        response.headers["x-request-id"] = request_id
        response.headers["retry-after"] = str(retry_after_seconds)
        response.headers["x-error-code"] = "server_busy"
        _set_standard_response_headers(response)
        return response
    _inflight_inc()
    try:
        timeout_ms = settings.api_priority_request_timeout_ms if is_priority else settings.api_request_timeout_ms
        timeout_seconds = max(timeout_ms, 100) / 1000
        try:
            response = await asyncio.wait_for(call_next(request), timeout=timeout_seconds)
        except TimeoutError:
            api_request_rejections_total.labels(reason="request_timeout").inc()
            retry_after_seconds = max(settings.api_retry_after_timeout_seconds, 1)
            response = JSONResponse(
                status_code=504,
                content=_error_payload(
                    code="request_timeout",
                    message="Request timed out while processing.",
                    request_id=request_id,
                    status_code=504,
                    details={"retry_after_seconds": retry_after_seconds},
                ),
            )
            response.headers["retry-after"] = str(retry_after_seconds)
            response.headers["x-error-code"] = "request_timeout"
        response.headers["x-request-id"] = request_id
        response.headers["x-process-time-ms"] = f"{(time.perf_counter() - start) * 1000:.2f}"
        _set_standard_response_headers(response)
        return response
    finally:
        _inflight_dec()
        if acquired:
            _request_semaphore.release()


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    response = JSONResponse(
        status_code=exc.status_code,
        content=_error_payload(
            code=f"http_{exc.status_code}",
            message=str(exc.detail),
            request_id=request_id,
            status_code=exc.status_code,
        ),
        headers={"x-request-id": request_id, "x-error-code": f"http_{exc.status_code}"},
    )
    _set_standard_response_headers(response)
    return response


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, _: Exception):
    request_id = getattr(request.state, "request_id", str(uuid4()))
    response = JSONResponse(
        status_code=500,
        content=_error_payload(
            code="internal_error",
            message="Unexpected server error",
            request_id=request_id,
            status_code=500,
        ),
        headers={"x-request-id": request_id, "x-error-code": "internal_error"},
    )
    _set_standard_response_headers(response)
    return response


@app.get("/health")
def health():
    return {
        "status": "ok",
        "service": settings.app_name,
        "environment": settings.environment,
        "build": _build_metadata(),
    }


@app.get("/live")
def liveness():
    return {"status": "alive", "build": _build_metadata()}


@app.get("/ready")
def readiness():
    db_ok = False
    redis_ok = False
    db = None
    try:
        db = SessionLocal()
        db.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        db_ok = False
    finally:
        try:
            if db is not None:
                db.close()
        except Exception:
            pass
    try:
        redis_ok = bool(redis_client.ping())
    except Exception:
        redis_ok = False
    status = "ready" if db_ok and redis_ok else "not_ready"
    code = 200 if status == "ready" else 503
    return JSONResponse(
        status_code=code,
        content={"status": status, "db": db_ok, "redis": redis_ok, "build": _build_metadata()},
    )
