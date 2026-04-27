"""Mensajes de error y soporte coherentes en toda la app (Streamlit)."""

from __future__ import annotations

import traceback

import streamlit as st


def render_modulo_fallo_ui(tab_name: str, exc: BaseException) -> None:
    """Error al renderizar un módulo: mensaje claro + expander con traza para soporte.
    Reporta automáticamente al Vigía de Errores."""
    st.error(f"Fallo al abrir el modulo **{tab_name}**. El resto del sistema puede seguir en uso.")
    st.markdown(
        "**Sugerencias:** volver a elegir el modulo en la barra superior, recargar la pagina (**F5**), "
        "o cambiar de paciente si el error solo ocurre con uno. Si reaparece, envia el detalle tecnico a soporte."
    )
    with st.expander("Detalle tecnico (soporte o desarrollo)", expanded=False):
        st.code(f"{type(exc).__name__}: {exc}", language="text")
        st.code(traceback.format_exc(), language="text")
        st.caption(
            "Si ves **ImportError**, suele faltar instalar una dependencia en el servidor (requirements.txt)."
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
    except Exception:
        pass


def render_carga_modulo_fallo(tab_name: str, exc: BaseException) -> None:
    """Error al importar/cargar el modulo (antes de ejecutar la vista).
    Reporta automáticamente al Vigía de Errores."""
    st.error(f"No se pudo cargar el modulo **{tab_name}**.")
    st.caption(f"Detalle: {type(exc).__name__}: {exc}")
    with st.expander("Traza (soporte)", expanded=False):
        st.code(traceback.format_exc(), language="text")

    # Reportar al Vigía de Errores
    try:
        from core.error_tracker import report_exception
        report_exception(
            module=f"carga.{tab_name}",
            exc_info=exc,
            context=f"render_carga_modulo_fallo({tab_name})",
            severity="critical",
        )
    except Exception:
        pass
