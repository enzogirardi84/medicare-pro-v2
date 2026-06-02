from __future__ import annotations

"""Logging de aplicacion sin datos clinicos.
Con soporte para logging estructurado JSON y correlation IDs.
"""

import logging
from collections import deque
from typing import Any

JSON_LOGGING_AVAILABLE = False
try:
    from core.observability import (
        StructuredLogFormatter,
        get_correlation_id,
    )
    JSON_LOGGING_AVAILABLE = True
except ImportError:
    JSON_LOGGING_AVAILABLE = False

_LOGGER = logging.getLogger("medicare.app")
_log_buffer: deque = deque(maxlen=100)


class MemoryLogHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry: dict[str, Any] = {
                "timestamp": (
                    self.formatter.formatTime(record)
                    if self.formatter
                    else getattr(record, "asctime", "")
                ),
                "level": record.levelname,
                "message": (
                    self.format(record) if self.formatter else record.getMessage()
                ),
                "name": record.name,
            }
            _log_buffer.append(entry)
        except Exception:
            pass


def _setup_memory_handler() -> None:
    global _log_buffer
    for h in _LOGGER.handlers:
        if isinstance(h, MemoryLogHandler):
            return
    h = MemoryLogHandler()
    h.setLevel(logging.WARNING)
    _LOGGER.addHandler(h)


_setup_memory_handler()


def log_event(kind: str, message: str) -> None:
    _LOGGER.info("[%s] %s", kind, message)


def get_recent_errors(limit: int = 20) -> list[dict[str, Any]]:
    return [
        e for e in _log_buffer if e.get("level") in ("ERROR", "CRITICAL")
    ][-limit:]
