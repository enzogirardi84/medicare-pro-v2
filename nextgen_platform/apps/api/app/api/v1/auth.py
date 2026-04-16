from fastapi import APIRouter, Depends, HTTPException, status
from jose import JWTError, jwt
import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_claims
from app.core.config import settings
from app.core.resilience import get_resilience_policy
from app.core.security import create_access_token, create_refresh_token, hash_password, verify_password
from app.domain.schemas import LoginRequest, LogoutRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.infrastructure.cache import redis_client
from app.infrastructure.db import get_db
from app.infrastructure.metrics import token_revocation_events_total
from app.infrastructure.models import Tenant, User

router = APIRouter(prefix="/auth", tags=["auth"])


def _is_token_revoked(jti: str | None, operation: str) -> bool:
    if not jti:
        return False
    try:
        return redis_client.get(f"revoked_token:{jti}") == "1"
    except redis.RedisError as exc:
        token_revocation_events_total.labels(operation=operation, result="redis_error_check").inc()
        if not get_resilience_policy("token_revocation_fail_open"):
            raise HTTPException(status_code=503, detail="Token revocation store unavailable") from exc
        token_revocation_events_total.labels(operation=operation, result="allowed_fail_open").inc()
        return False


def _store_revoked_token(jti: str | None, ttl_seconds: int, operation: str) -> None:
    if not jti:
        return
    try:
        redis_client.setex(f"revoked_token:{jti}", ttl_seconds, "1")
        token_revocation_events_total.labels(operation=operation, result="write").inc()
    except redis.RedisError as exc:
        token_revocation_events_total.labels(operation=operation, result="redis_error_write").inc()
        if not get_resilience_policy("token_revocation_fail_open"):
            raise HTTPException(status_code=503, detail="Token revocation store unavailable") from exc


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    tenant = db.scalar(select(Tenant).where(Tenant.name == payload.tenant_name))
    if tenant is None:
        tenant = Tenant(name=payload.tenant_name.strip())
        db.add(tenant)
        db.flush()

    existing = db.scalar(select(User).where(User.tenant_id == tenant.id, User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="User already exists")

    user = User(
        tenant_id=tenant.id,
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=payload.role,
    )
    db.add(user)
    db.commit()
    access_token = create_access_token(subject=str(user.id), tenant_id=str(tenant.id), role=user.role)
    refresh_token = create_refresh_token(subject=str(user.id), tenant_id=str(tenant.id), role=user.role)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    tenant = db.scalar(select(Tenant).where(Tenant.name == payload.tenant_name))
    if tenant is None:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = db.scalar(select(User).where(User.tenant_id == tenant.id, User.email == payload.email.lower()))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    access_token = create_access_token(subject=str(user.id), tenant_id=str(tenant.id), role=user.role)
    refresh_token = create_refresh_token(subject=str(user.id), tenant_id=str(tenant.id), role=user.role)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
def refresh(payload: RefreshRequest):
    try:
        claims = jwt.decode(payload.refresh_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc

    if claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    jti = claims.get("jti")
    if _is_token_revoked(jti, operation="refresh_check"):
        token_revocation_events_total.labels(operation="refresh_check", result="revoked").inc()
        raise HTTPException(status_code=401, detail="Refresh token revoked")

    _store_revoked_token(
        jti,
        settings.refresh_token_expire_days * 24 * 3600,
        operation="refresh_rotate_revoke_old",
    )
    access_token = create_access_token(
        subject=str(claims["sub"]), tenant_id=str(claims["tenant_id"]), role=str(claims["role"])
    )
    refresh_token = create_refresh_token(
        subject=str(claims["sub"]), tenant_id=str(claims["tenant_id"]), role=str(claims["role"])
    )
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/logout")
def logout(payload: LogoutRequest, claims: dict = Depends(get_current_claims)):
    access_jti = claims.get("jti")
    _store_revoked_token(
        access_jti,
        settings.access_token_expire_minutes * 60,
        operation="logout_revoke_access",
    )
    try:
        refresh_claims = jwt.decode(payload.refresh_token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except JWTError as exc:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from exc
    if refresh_claims.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid token type")
    if str(refresh_claims.get("sub")) != str(claims.get("sub")):
        raise HTTPException(status_code=403, detail="Refresh token does not belong to user")
    refresh_jti = refresh_claims.get("jti")
    _store_revoked_token(
        refresh_jti,
        settings.refresh_token_expire_days * 24 * 3600,
        operation="logout_revoke_refresh",
    )
    return {"status": "ok"}
