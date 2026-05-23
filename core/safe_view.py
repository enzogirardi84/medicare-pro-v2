"""Middleware de manejo global de errores clinicos.

Decora las vistas principales para capturar excepciones, 
generar IDs de incidente y mostrar mensajes institucionales.
"""

from __future__ import annotations

import functools
import secrets
import traceback
from typing import Any, Callable, Optional

import streamlit as st

from core.app_logging import log_event


def safe_clinical_view(view_fn: Optional[Callable] = None, *, module_name: str = ""):
    """Decorador para vistas clinicas. Captura errores, genera ID de incidente y muestra
    mensaje institucional sin exponer tracebacks.
    
    Uso:
        @safe_clinical_view
        def render_evolucion(paciente_sel, user, rol):
            ...
        
        @safe_clinical_view(module_name="recetas")
        def render_recetas(paciente_sel, user, rol):
            ...
    """
    def decorator(func: Callable) -> Callable:
        mod_name = module_name or func.__name__.replace("render_", "")
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                incident_id = f"MED-{secrets.token_hex(4).upper()}"
                error_msg = f"{type(e).__name__}: {e!s}"[:200]
                
                log_event(
                    "safe_view",
                    f"incident:{incident_id}:module:{mod_name}:error:{error_msg}"
                )
                
                st.error(
                    f"Se produjo un inconveniente controlado al cargar este modulo. "
                    f"ID de soporte: #{incident_id}",
                    icon="🔒",
                )
                
                with st.expander("Detalle para soporte tecnico"):
                    st.caption(
                        f"Modulo: {mod_name} | ID: {incident_id} | "
                        f"Tipo: {type(e).__name__}"
                    )
                    st.code(traceback.format_exc(limit=3), language="text")
                
                return None
        return wrapper
    
    return decorator(view_fn) if view_fn else decorator
