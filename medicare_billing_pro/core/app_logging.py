"""Logging estructurado para Medicare Billing Pro."""
from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from contextvars import ContextVar

_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")


class StructuredLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "correlation_id": _correlation_id.get() or "none",
        }
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_data, ensure_ascii=False)


def configurar_logging_basico(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredLogFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


def log_event(modulo: str, mensaje: str, level: str = "info") -> None:
    logger = logging.getLogger(f"billing.{modulo}")
    getattr(logger, level)(mensaje)


def get_correlation_id() -> str:
    cid = _correlation_id.get()
    if not cid:
        import uuid
        cid = uuid.uuid4().hex[:16]
        _correlation_id.set(cid)
    return cid
