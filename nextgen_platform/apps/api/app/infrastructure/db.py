import time

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings
from app.infrastructure.metrics import (
    read_db_fallback_reason_total,
    read_db_fallback_total,
    read_db_readonly_requests_total,
    read_db_replica_available,
)


class Base(DeclarativeBase):
    pass


def _build_connect_args(url: str) -> dict:
    connect_args = {}
    if url.startswith("postgresql"):
        # Protege al cluster frente a queries colgadas bajo alta concurrencia.
        connect_args["options"] = f"-c statement_timeout={max(settings.db_statement_timeout_ms, 100)}"
    return connect_args


engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,
    pool_size=max(settings.db_pool_size, 1),
    max_overflow=max(settings.db_max_overflow, 0),
    pool_timeout=max(settings.db_pool_timeout_seconds, 1),
    pool_recycle=max(settings.db_pool_recycle_seconds, 30),
    pool_use_lifo=True,
    connect_args=_build_connect_args(settings.database_url),
)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

read_engine = create_engine(
    settings.read_database_url or settings.database_url,
    pool_pre_ping=True,
    pool_size=max(settings.db_pool_size, 1),
    max_overflow=max(settings.db_max_overflow, 0),
    pool_timeout=max(settings.db_pool_timeout_seconds, 1),
    pool_recycle=max(settings.db_pool_recycle_seconds, 30),
    pool_use_lifo=True,
    connect_args=_build_connect_args(settings.read_database_url or settings.database_url),
)
SessionReadOnly = sessionmaker(bind=read_engine, autoflush=False, autocommit=False)

_read_db_last_check_ts = 0.0
_read_db_available = True

# Default metric value at startup before first health probe.
read_db_replica_available.set(1 if settings.read_database_url else 0)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_readonly():
    read_db_readonly_requests_total.inc()
    fallback_reason = _readonly_fallback_reason()
    using_readonly = fallback_reason is None
    if fallback_reason is not None:
        read_db_fallback_total.inc()
        read_db_fallback_reason_total.labels(reason=fallback_reason).inc()
    db = (SessionReadOnly if using_readonly else SessionLocal)()
    try:
        yield db
    finally:
        db.close()


def _readonly_fallback_reason() -> str | None:
    if not settings.read_database_url:
        return "replica_not_configured"
    if not settings.read_db_fail_open:
        return None
    if _is_read_db_available():
        return None
    return "replica_unavailable"


def _is_read_db_available() -> bool:
    global _read_db_last_check_ts, _read_db_available
    now = time.time()
    if now - _read_db_last_check_ts < max(settings.read_db_healthcheck_interval_seconds, 1):
        return _read_db_available
    _read_db_last_check_ts = now
    try:
        with read_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        _read_db_available = True
    except Exception:
        _read_db_available = False
    read_db_replica_available.set(1 if _read_db_available else 0)
    return _read_db_available
