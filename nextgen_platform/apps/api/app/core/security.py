from datetime import datetime, timedelta, timezone
from typing import Any, Dict
from uuid import uuid4

from jose import jwt
from passlib.context import CryptContext

from app.core.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return pwd_context.verify(password, hashed_password)


def create_access_token(subject: str, tenant_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload: Dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "type": "access",
        "jti": str(uuid4()),
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_refresh_token(subject: str, tenant_id: str, role: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days)
    payload: Dict[str, Any] = {
        "sub": subject,
        "tenant_id": tenant_id,
        "role": role,
        "type": "refresh",
        "jti": str(uuid4()),
        "exp": expire,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)
