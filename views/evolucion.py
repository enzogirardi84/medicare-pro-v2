import streamlit as st

from core.utils import puede_accion
from core.view_helpers import aviso_sin_paciente
from views._evolucion_panel import (
    _render_panel_evolucion_clinica,
    CANVAS_DISPONIBLE,
    get_canvas,
)
from views._evolucion_cuidador import _render_panel_cuidador

_TABS = ["Evolucion clinica", "Registro inteligente"]


def render_evolucion(paciente_sel, user, rol=None):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    rol = rol or user.get("rol", "")
    puede_registrar = puede_accion(rol, "evolucion_registrar")
    puede_borrar = puede_accion(rol, "evolucion_borrar")

    st.markdown("## Evolucion y cuidados clinicos")

    if "evolucion_tab" not in st.session_state:
        st.session_state["evolucion_tab"] = _TABS[0]

    sel = st.segmented_control(
        "Seccion",
        _TABS,
        default=st.session_state["evolucion_tab"],
        key="evolucion_tab",
        label_visibility="collapsed",
        selection_mode="single",
    )

    if sel == "Registro inteligente":
        _render_panel_cuidador(paciente_sel, user, puede_registrar)
    else:
        _render_panel_evolucion_clinica(paciente_sel, user, puede_registrar, puede_borrar)
