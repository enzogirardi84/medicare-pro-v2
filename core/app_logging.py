"""Logging de aplicación sin datos clínicos ni identificadores de paciente."""

import logging

_LOGGER = logging.getLogger("medicare.app")


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
