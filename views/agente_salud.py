"""Vista Streamlit para el Agente de Salud."""

from __future__ import annotations

from html import escape

import streamlit as st

from core.health_agent import (
    HealthAgentAction,
    ejecutar_agente_salud_paciente,
    exportar_plan_texto,
)
from core.view_helpers import aviso_sin_paciente


BADGE_COLORS = {
    "critica": "#dc2626",
    "alta": "#ea580c",
    "media": "#ca8a04",
    "baja": "#16a34a",
}


def _css() -> None:
    if st.session_state.get("_agente_salud_css"):
        return
    st.session_state["_agente_salud_css"] = True
    st.markdown(
        """
        <style>
        .agent-status-row {
            display:grid;
            grid-template-columns:repeat(4,minmax(0,1fr));
            gap:10px;
            margin:12px 0 16px;
        }
        .agent-kpi {
            border:1px solid rgba(148,163,184,.22);
            border-radius:8px;
            padding:10px 12px;
            background:rgba(15,23,42,.32);
            min-width:0;
        }
        .agent-kpi span {
            display:block;
            color:#94a3b8;
            font-size:.72rem;
            text-transform:uppercase;
            font-weight:700;
        }
        .agent-kpi strong {
            display:block;
            color:#e2e8f0;
            font-size:1.05rem;
            overflow-wrap:anywhere;
        }
        .agent-action {
            border:1px solid rgba(148,163,184,.24);
            border-left:5px solid var(--agent-color);
            border-radius:8px;
            padding:12px 14px;
            margin:8px 0;
            background:rgba(15,23,42,.25);
        }
        .agent-action-head {
            display:flex;
            align-items:center;
            justify-content:space-between;
            gap:10px;
            margin-bottom:5px;
        }
        .agent-action-title {
            color:#f8fafc;
            font-weight:700;
            overflow-wrap:anywhere;
        }
        .agent-badge {
            flex:0 0 auto;
            border-radius:999px;
            padding:3px 8px;
            font-size:.7rem;
            font-weight:800;
            color:#fff;
            background:var(--agent-color);
            text-transform:uppercase;
        }
        .agent-action-detail,
        .agent-action-meta {
            color:#cbd5e1;
            font-size:.88rem;
            line-height:1.35;
            overflow-wrap:anywhere;
        }
        .agent-action-meta { color:#94a3b8; margin-top:6px; }
        @media(max-width:768px){
            .agent-status-row{grid-template-columns:repeat(2,minmax(0,1fr));}
            .agent-action-head{align-items:flex-start;flex-direction:column;}
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _estado_label(estado: str) -> str:
    return {
        "critico": "Critico",
        "atencion": "Atencion",
        "estable": "Estable",
    }.get(str(estado), str(estado).title())


def _render_action(accion: HealthAgentAction, index: int) -> None:
    color = BADGE_COLORS.get(accion.prioridad, "#64748b")
    st.markdown(
        f"""
        <div class="agent-action" style="--agent-color:{color}">
            <div class="agent-action-head">
                <div class="agent-action-title">{index}. {escape(accion.titulo)}</div>
                <div class="agent-badge">{escape(accion.prioridad)}</div>
            </div>
            <div class="agent-action-detail">{escape(accion.detalle)}</div>
            <div class="agent-action-meta">
                Responsable: {escape(accion.responsable)} | Modulo: {escape(accion.modulo_sugerido)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns([1, 1])
    with cols[0]:
        if st.button(
            f"Abrir {accion.modulo_sugerido}",
            key=f"agent_nav_{accion.id}_{index}",
            use_container_width=True,
        ):
            from core.app_navigation import set_modulo_actual

            set_modulo_actual(accion.modulo_sugerido, rerun=True)
    with cols[1]:
        with st.expander("Evidencia", expanded=False):
            for item in accion.evidencia or ["S/D"]:
                st.caption(str(item))


def render_agente_salud(paciente_sel, mi_empresa, user, rol):
    _css()
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Agente de Salud</h2>
            <p class="mc-hero-text">Priorizacion operativa del paciente actual con reglas clinicas y trazabilidad.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    objetivo = st.text_input(
        "Objetivo",
        placeholder="Ej: preparar pase de guardia, revisar riesgos, ordenar pendientes",
        key=f"agente_salud_objetivo_{paciente_sel}",
    )

    with st.spinner("Ejecutando agente..."):
        resultado = ejecutar_agente_salud_paciente(
            paciente_sel,
            mi_empresa=mi_empresa,
            objetivo=objetivo.strip() or None,
        )

    dashboard = resultado.dashboard
    st.markdown(
        f"""
        <div class="agent-status-row">
            <div class="agent-kpi"><span>Estado</span><strong>{escape(_estado_label(resultado.estado))}</strong></div>
            <div class="agent-kpi"><span>Criticas</span><strong>{resultado.acciones_criticas}</strong></div>
            <div class="agent-kpi"><span>Altas</span><strong>{resultado.acciones_altas}</strong></div>
            <div class="agent-kpi"><span>Acciones</span><strong>{len(resultado.acciones)}</strong></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(resultado.resumen)

    cols = st.columns(5)
    cols[0].metric("TA", dashboard.get("ultima_ta", "-"))
    cols[1].metric("FC", dashboard.get("ultima_fc", "-"))
    cols[2].metric("Temp", dashboard.get("ultima_temp", "-"))
    cols[3].metric("SatO2", dashboard.get("ultima_spo2", "-"))
    cols[4].metric("Glu", dashboard.get("ultima_glu", "-"))

    filtro = st.segmented_control(
        "Filtro",
        ["Todas", "Critica", "Alta", "Media", "Baja"],
        default="Todas",
        key=f"agente_salud_filtro_{paciente_sel}",
    )
    filtro_norm = str(filtro or "Todas").lower()
    acciones = [
        accion
        for accion in resultado.acciones
        if filtro_norm == "todas" or accion.prioridad == filtro_norm
    ]

    st.subheader("Acciones")
    for idx, accion in enumerate(acciones, start=1):
        _render_action(accion, idx)

    st.download_button(
        "Descargar plan",
        data=exportar_plan_texto(resultado),
        file_name=f"plan_agente_salud_{str(paciente_sel)[:24]}.txt",
        mime="text/plain",
        use_container_width=True,
    )

    with st.expander("Limites clinicos", expanded=False):
        for item in resultado.guardrails:
            st.caption(item)
