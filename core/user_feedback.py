"""Mensajes de error y soporte coherentes en toda la app (Streamlit).
NUNCA expone tracebacks al usuario (PHI leak prevention).
"""

from __future__ import annotations

from html import escape

import streamlit as st

from core.app_logging import log_event


def render_modulo_fallo_ui(tab_name: str, exc: BaseException) -> None:
    """Error al renderizar un módulo: mensaje claro sin exponer traceback.
    Reporta automáticamente al Vigía de Errores."""
    msg = f"{type(exc).__name__}: {exc!s}"[:200]
    log_event("user_feedback", f"error: modulo:{tab_name}:{msg}")
    st.error(f"Fallo al abrir el modulo **{escape(tab_name)}**. El resto del sistema puede seguir en uso.")
    st.markdown(
        "**Sugerencias:** volver a elegir el modulo en la barra superior, recargar la pagina (**F5**), "
        "o cambiar de paciente si el error solo ocurre con uno. Si reaparece, contacte a soporte."
    )

    # Reportar al Vigía de Errores
    try:
        from core.error_tracker import report_exception
        report_exception(
            module=f"vista.{tab_name}",
            exc_info=exc,
            context=f"render_modulo_fallo_ui({tab_name})",
            severity="error",
        )
    except Exception as e:
        log_event("user_feedback", f"report_exception_fallo:{type(e).__name__}")


def render_carga_modulo_fallo(tab_name: str, exc: BaseException) -> None:
    """Error al importar/cargar el modulo (antes de ejecutar la vista).
    Reporta automáticamente al Vigía de Errores. Sin exponer traceback."""
    log_event("user_feedback", f"error: carga_modulo:{tab_name}:{type(exc).__name__}")
    st.error(f"No se pudo cargar el modulo **{escape(tab_name)}**. Contacte a soporte.")

    # Reportar al Vigía de Errores
    try:
        from core.error_tracker import report_exception
        report_exception(
            module=f"carga.{tab_name}",
            exc_info=exc,
            context=f"render_carga_modulo_fallo({tab_name})",
            severity="critical",
        )
    except Exception as e:
        log_event("user_feedback", f"report_exception_fallo:{type(e).__name__}")


