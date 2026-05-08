import time
from typing import Dict

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
import jwt
from jwt import PyJWTError
import redis

from app.core.config import settings
from app.core.resilience import get_resilience_policy
from app.infrastructure.cache import redis_client
from app.infrastructure.metrics import rate_limit_events_total, token_revocation_events_total

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/v1/auth/login")


def get_current_claims(token: str = Depends(oauth2_scheme)) -> Dict[str, str]:
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except PyJWTError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token") from exc

    required = ("sub", "tenant_id", "role")
    if any(k not in payload for k in required):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Malformed token")
    jti = payload.get("jti")
    if jti:
        try:
            if redis_client.get(f"revoked_token:{jti}") == "1":
                token_revocation_events_total.labels(operation="access_check", result="revoked").inc()
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")
        except redis.RedisError as exc:
            token_revocation_events_total.labels(operation="access_check", result="redis_error").inc()
            if not get_resilience_policy("token_revocation_fail_open"):
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Token revocation store unavailable"
                ) from exc
            token_revocation_events_total.labels(operation="access_check", result="allowed_fail_open").inc()
    if payload.get("type") != "access":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token type")
    return payload


def require_roles(*allowed_roles: str):
    allowed = set(allowed_roles)

    def _check(claims: Dict[str, str] = Depends(get_current_claims)) -> Dict[str, str]:
        if claims.get("role") not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
        return claims

    return _check


def enforce_rate_limit(request: Request, claims: Dict[str, str], limit_per_minute: int = 120) -> None:
    user_id = str(claims.get("sub", "unknown"))
    tenant_id = str(claims.get("tenant_id", "unknown"))
    ip = request.client.host if request.client else "unknown"
    minute_bucket = int(time.time() // 60)
    key = f"rate_limit:{tenant_id}:{user_id}:{ip}:{minute_bucket}"
    burst_window = max(settings.rate_limit_burst_window_seconds, 1)
    burst_bucket = int(time.time() // burst_window)
    burst_limit = max(
        int(limit_per_minute * max(settings.rate_limit_burst_multiplier, 0.0)),
        settings.rate_limit_burst_min_requests,
    )
    burst_key = f"rate_burst:{tenant_id}:{user_id}:{ip}:{burst_window}:{burst_bucket}"
    try:
        current = redis_client.incr(key)
        if current == 1:
            redis_client.expire(key, 70)
        burst_current = redis_client.incr(burst_key)
        if burst_current == 1:
            redis_client.expire(burst_key, burst_window + 2)
        if current > limit_per_minute:
            rate_limit_events_total.labels(decision="blocked_limit_exceeded").inc()
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Rate limit exceeded")
        if burst_current > burst_limit:
            rate_limit_events_total.labels(decision="blocked_burst_exceeded").inc()
            raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Burst rate limit exceeded")
        rate_limit_events_total.labels(decision="allowed").inc()
    except redis.RedisError as exc:
        if get_resilience_policy("rate_limit_fail_open"):
            rate_limit_events_total.labels(decision="allowed_fail_open").inc()
            return
        rate_limit_events_total.labels(decision="blocked_fail_closed").inc()
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Rate limiter unavailable") from exc
