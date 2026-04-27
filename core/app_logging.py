"""Logging de aplicación sin datos clínicos ni identificadores de paciente.

Ahora con soporte para logging estructurado JSON y correlation IDs.
"""

import logging
import sys
from collections import deque
from typing import Dict, List, Any

# Intentar importar observabilidad
JSON_LOGGING_AVAILABLE = False
try:
    from core.observability import (
        StructuredLogFormatter,
        get_correlation_id,
        set_correlation_id,
        init_observability_for_session,
    )
    JSON_LOGGING_AVAILABLE = True
except ImportError:
    pass

_LOGGER = logging.getLogger("medicare.app")

# Buffer circular de logs para diagnóstico (últimos 100 entries)
_log_buffer: deque = deque(maxlen=100)


class MemoryLogHandler(logging.Handler):
    """Handler que guarda logs en memoria para diagnóstico."""
    
    def emit(self, record: logging.LogRecord) -> None:
        try:
            entry: Dict[str, Any] = {
                "timestamp": self.formatter.formatTime(record) if self.formatter else getattr(record, 'asctime', ''),
                "level": record.levelname,
                "message": self.format(record) if self.formatter else record.getMessage(),
                "name": record.name,
            }
            # Agregar correlation_id si está disponible
            if JSON_LOGGING_AVAILABLE:
                try:
                    entry["correlation_id"] = get_correlation_id()
                except Exception:
                    entry["correlation_id"] = "none"
            _log_buffer.append(entry)
        except Exception as _exc:
            # Silencioso por diseño: el logging no debe fallar la app
            import logging as _logging
            _logging.getLogger("app_logging").debug(f"fallo_emit:{type(_exc).__name__}")


def _setup_memory_handler() -> None:
    """Configura el handler de memoria si no está ya configurado."""
    global _log_buffer
    for handler in _LOGGER.handlers:
        if isinstance(handler, MemoryLogHandler):
            return
    
    handler = MemoryLogHandler()
    handler.setLevel(logging.WARNING)  # Solo WARNING y superior
    
    # Usar formatter JSON si está disponible
    if JSON_LOGGING_AVAILABLE:
        handler.setFormatter(StructuredLogFormatter())
    else:
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
    
    _LOGGER.addHandler(handler)
    _log_buffer = deque(maxlen=100)


# Setup automático al importar
_setup_memory_handler()


def configurar_logging_basico() -> None:
    if logging.getLogger().handlers:
        return
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    # Evita una linea INFO por cada request HTTP (p. ej. 404 a tablas Supabase aun no migradas).
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def log_event(kind: str, message: str) -> None:
    """Registra un evento operativo (solo texto agregado; no uses PHI acá)."""
    _LOGGER.info("[%s] %s", kind, message)


def get_recent_errors(limit: int = 20) -> List[Dict[str, Any]]:
    """Retorna los últimos errores del buffer de logs."""
    global _log_buffer
    errors = [log for log in _log_buffer if log.get("level") in ["ERROR", "CRITICAL"]]
    return errors[-limit:] if errors else []
