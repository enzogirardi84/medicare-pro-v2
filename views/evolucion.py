import streamlit as st

from core.utils import puede_accion
from core.view_helpers import aviso_sin_paciente
from views._evolucion_panel import (
    _historial_evoluciones_scroll_interno,
    _render_panel_evolucion_clinica,
    CANVAS_DISPONIBLE,
    get_canvas,
)


def render_evolucion(paciente_sel, user, rol=None):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    rol = rol or user.get("rol", "")
    puede_registrar = puede_accion(rol, "evolucion_registrar")
    puede_borrar = puede_accion(rol, "evolucion_borrar")

    st.markdown("## Evolución y cuidados clínicos")
    tab_clinica, tab_enfermeria = st.tabs(["Evolución clínica", "Plan de enfermería"])
    with tab_clinica:
        _render_panel_evolucion_clinica(paciente_sel, user, puede_registrar, puede_borrar)
    with tab_enfermeria:
        from views.enfermeria import render_enfermeria

        mi_empresa = str(user.get("empresa") or "").strip() or "Clinica General"
        render_enfermeria(paciente_sel, mi_empresa, user, compact=True)
