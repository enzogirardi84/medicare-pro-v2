"""Orquestador principal del modulo APS/Dispensario.
Importa componentes visuales desde views/dispensario/components/.
Logica de negocio y datos desde services/ y repositories/.
"""

from __future__ import annotations

import streamlit as st

from core.view_helpers import aviso_sin_paciente
from core.utils import puede_accion
from views.dispensario.components._helpers import header_paciente, input_paciente_volatil
from views.dispensario.components._tabs import (
    tab_panel_diario,
    tab_pacientes_familia,
    tab_ficha_aps,
    tab_turnos,
    tab_historial_aps,
    tab_nueva_atencion,
    tab_control_nino_embarazo,
    tab_farmacia,
    tab_trabajo_social,
    tab_epidemiologia,
    tab_visitas,
    tab_reportes,
)

_TABS = {
    "Panel diario": tab_panel_diario,
    "Pacientes y Familia": tab_pacientes_familia,
    "Ficha APS": tab_ficha_aps,
    "Turnos": tab_turnos,
    "Historial APS": tab_historial_aps,
    "Nueva Atencion": tab_nueva_atencion,
    "Control Ninez/Embarazo": tab_control_nino_embarazo,
    "Farmacia": tab_farmacia,
    "Trabajo Social": tab_trabajo_social,
    "Epidemiologia": tab_epidemiologia,
    "Visitas": tab_visitas,
    "Reportes": tab_reportes,
}


def render_dispensario_aps(paciente_sel, mi_empresa, user, rol):
    """Punto de entrada del modulo APS. Orquesta tabs y estado."""
    from core.ui_liviano import headers_sugieren_equipo_liviano
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    if not st.session_state.get("pacientes_db"):
        aviso_sin_paciente()
        return

    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">🏥 APS / Dispensario</h2>
            <p class="mc-hero-text">Atención Primaria de la Salud</p>
        </div>
    """, unsafe_allow_html=True)

    centro_salud_id = mi_empresa or st.session_state.get("u_actual", {}).get("empresa", "Sin centro")

    if paciente_sel:
        header_paciente(paciente_sel, user)
    else:
        st.info("Seleccione un paciente del selector superior o use los formularios volatiles.")

    tab_names = list(_TABS.keys())
    default_tab = st.session_state.get("_aps_tab", tab_names[0])
    default_idx = tab_names.index(default_tab) if default_tab in tab_names else 0
    tabs = st.tabs(tab_names)

    for i, (name, render_fn) in enumerate(_TABS.items()):
        with tabs[i]:
            try:
                render_fn(paciente_sel, user, centro_salud_id)
            except Exception as e:
                from core.app_logging import log_event
                log_event("aps", f"tab_fallo:{name}:{type(e).__name__}:{e}")
                st.error(f"Error en pestaña «{name}». Contacte a soporte.")

    if st.session_state.get("_aps_tab"):
        st.session_state.pop("_aps_tab", None)
