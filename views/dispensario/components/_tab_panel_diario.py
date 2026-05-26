"""Panel diario APS — metricas y sala de espera."""

from __future__ import annotations

from datetime import date

import streamlit as st

from views.dispensario.components._helpers import metricas_aps_del_dia, header_paciente, input_paciente_volatil


def render_tab_panel_diario(paciente_sel, user):
    st.subheader("Panel del dia")
    st.caption("Resumen de actividad del dia y acceso rapido a funcionalidades.")
    from core.ui_liviano import headers_sugieren_equipo_liviano
    es_movil = headers_sugieren_equipo_liviano()
    metricas = metricas_aps_del_dia()
    ncols = 2 if es_movil else 4
    cols = st.columns(ncols)
    cols[0].metric("Atenciones hoy", metricas["atenciones_hoy"])
    cols[1].metric("Entregas hoy", metricas["entregas_hoy"])
    if not es_movil:
        cols[2].metric("Epi hoy", metricas["epidemiologia_hoy"])
        cols[3].metric("Visitas hoy", metricas["visitas_hoy"])
    c_total = st.columns(ncols)
    c_total[0].metric("Total atenciones", metricas["total_atenciones"])
    c_total[1].metric("Total entregas", metricas["total_entregas"])
    if not es_movil:
        c_total[2].metric("Total epi", metricas["total_epidemiologia"])
        c_total[3].metric("Total visitas", metricas["total_visitas"])

    with st.expander("Acceso rapido a pacientes", expanded=False):
        if paciente_sel:
            header_paciente(paciente_sel, user)
        else:
            input_paciente_volatil(paciente_sel)
