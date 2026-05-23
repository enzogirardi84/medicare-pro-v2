"""Panel diario APS — metricas y sala de espera."""

from __future__ import annotations

from datetime import date

import streamlit as st

from views.dispensario.components._helpers import metricas_aps_del_dia, header_paciente, input_paciente_volatil
from core.app_logging import log_event


def render_tab_panel_diario(paciente_sel, user):
    st.subheader("Panel del dia")
    st.caption("Resumen de actividad del dia y acceso rapido a funcionalidades.")
    metricas = metricas_aps_del_dia()
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Atenciones hoy", metricas["atenciones_hoy"])
    col2.metric("Entregas hoy", metricas["entregas_hoy"])
    col3.metric("Epi hoy", metricas["epidemiologia_hoy"])
    col4.metric("Visitas hoy", metricas["visitas_hoy"])
    c_total = st.columns(4)
    c_total[0].metric("Total atenciones", metricas["total_atenciones"])
    c_total[1].metric("Total entregas", metricas["total_entregas"])
    c_total[2].metric("Total epi", metricas["total_epidemiologia"])
    c_total[3].metric("Total visitas", metricas["total_visitas"])

    with st.expander("Acceso rapido a pacientes", expanded=True):
        if paciente_sel:
            header_paciente(paciente_sel, user)
        else:
            input_paciente_volatil(paciente_sel)
