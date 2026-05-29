from __future__ import annotations

import streamlit as st

from core.permissions import EVOLUCION_BORRAR, EVOLUCION_CREAR, puede
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
    from core.ui_liviano import headers_sugieren_equipo_liviano
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    if not paciente_sel:
        aviso_sin_paciente()
        return

    rol = rol or user.get("rol", "")

    # Compatibilidad: mantenemos la regla vieja por rol y sumamos la capa nueva
    # de permisos centralizados. Esto permite migrar módulos sin romper perfiles
    # existentes que todavía dependan de core.utils.puede_accion.
    puede_registrar = puede(user, EVOLUCION_CREAR) or puede_accion(rol, "evolucion_registrar")
    puede_borrar = puede(user, EVOLUCION_BORRAR) or puede_accion(rol, "evolucion_borrar")

    st.markdown("## Evolucion y cuidados clinicos")

    sel = st.segmented_control(
        "Seccion",
        _TABS,
        default=_TABS[0],
        key="evolucion_tab",
        label_visibility="collapsed",
        selection_mode="single",
    )

    if sel == "Registro inteligente":
        _render_panel_cuidador(paciente_sel, user, puede_registrar)
    else:
        _render_panel_evolucion_clinica(paciente_sel, user, puede_registrar, puede_borrar)
