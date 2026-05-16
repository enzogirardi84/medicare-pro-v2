import streamlit as st

from core.utils import puede_accion
from core.view_helpers import aviso_sin_paciente
from views._evolucion_panel import (
    _render_panel_evolucion_clinica,
    CANVAS_DISPONIBLE,
    get_canvas,
)
from views._evolucion_cuidador import _render_panel_cuidador


def render_evolucion(paciente_sel, user, rol=None):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    rol = rol or user.get("rol", "")
    puede_registrar = puede_accion(rol, "evolucion_registrar")
    puede_borrar = puede_accion(rol, "evolucion_borrar")

    st.markdown("## Evolucion y cuidados clinicos")
    tab_clinica, tab_cuidador = st.tabs(["Evolucion clinica", "Registro inteligente"])
    with tab_clinica:
        _render_panel_evolucion_clinica(paciente_sel, user, puede_registrar, puede_borrar)
    with tab_cuidador:
        _render_panel_cuidador(paciente_sel, user, puede_registrar)
