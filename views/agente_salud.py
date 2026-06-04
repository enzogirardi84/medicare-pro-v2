"""Vista Streamlit para el Agente de Salud."""

from __future__ import annotations

from html import escape

import streamlit as st

from core.health_agent import (
    HealthAgentAction,
    ejecutar_agente_salud_paciente,
    exportar_pase_guardia,
    exportar_plan_texto,
    exportar_priorizacion_institucion,
    exportar_resumen_derivacion,
    priorizar_pacientes_institucion,
    registrar_accion_agente,
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


def _actor_label(user: dict) -> str:
    nombre = str((user or {}).get("nombre") or "Usuario").strip()
    rol = str((user or {}).get("rol") or "").strip()
    return f"{nombre} ({rol})" if rol else nombre


def _render_action(accion: HealthAgentAction, index: int, paciente_sel: str, user: dict) -> None:
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
                Responsable: {escape(accion.responsable)} | Modulo: {escape(accion.modulo_sugerido)} | Vence: {escape(accion.vencimiento)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns([1, 1, 1])
    with cols[0]:
        if st.button(
            f"Abrir {accion.modulo_sugerido}",
            key=f"agent_nav_{accion.id}_{index}",
            use_container_width=True,
        ):
            from core.app_navigation import set_modulo_actual

            set_modulo_actual(accion.modulo_sugerido, rerun=True)
    with cols[1]:
        if st.button(
            "Marcar realizada",
            key=f"agent_done_{accion.id}_{index}",
            use_container_width=True,
        ):
            registrar_accion_agente(
                st.session_state,
                paciente_id=paciente_sel,
                accion_id=accion.id,
                accion_titulo=accion.titulo,
                actor=_actor_label(user),
                estado="realizada",
            )
            _guardar_trazabilidad_agente()
            st.toast("Accion registrada.")
            st.rerun()
    with cols[2]:
        with st.expander("Evidencia", expanded=False):
            for item in accion.evidencia or ["S/D"]:
                st.caption(str(item))


def _pacientes_visibles_para_priorizar(mi_empresa: str) -> list[str]:
    pacientes = []
    raw = st.session_state.get("pacientes_db", [])
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                empresa = str(item.get("empresa", "") or "").strip()
                if empresa and mi_empresa and empresa != mi_empresa:
                    continue
                nombre = str(item.get("nombre") or item.get("paciente") or "").strip()
                dni = str(item.get("dni") or "").strip()
                if nombre and dni:
                    pacientes.append(f"{nombre} - {dni}")
                elif nombre:
                    pacientes.append(nombre)
            elif isinstance(item, str):
                pacientes.append(item)
    detalles = st.session_state.get("detalles_pacientes_db", {})
    if isinstance(detalles, dict):
        pacientes.extend(str(k) for k in detalles.keys() if k)
    vistos = set()
    salida = []
    for paciente in pacientes:
        if paciente not in vistos:
            vistos.add(paciente)
            salida.append(paciente)
    return salida


def _render_plan_hoy(resultado, paciente_sel: str, user: dict) -> None:
    if st.button("Preparar plan de hoy", type="primary", use_container_width=True):
        st.session_state[f"agente_plan_hoy_preparado_{paciente_sel}"] = True
        registrar_accion_agente(
            st.session_state,
            paciente_id=paciente_sel,
            accion_id="plan-hoy",
            accion_titulo="Preparar plan de hoy",
            actor=_actor_label(user),
            estado="preparada",
        )
        _guardar_trazabilidad_agente()
        st.rerun()

    if not resultado.plan_hoy:
        st.info("No hay acciones para planificar hoy.")
        return

    for responsable, acciones in resultado.plan_hoy.items():
        st.markdown(f"#### {responsable}")
        for idx, accion in enumerate(acciones, start=1):
            st.write(f"{idx}. [{accion.prioridad.upper()}] {accion.titulo}")
            st.caption(accion.detalle)


def _render_trazabilidad(paciente_sel: str) -> None:
    log = st.session_state.get("agente_salud_acciones_db", [])
    if not isinstance(log, list) or not log:
        st.info("Todavia no hay acciones registradas por el agente.")
        return
    filas = [r for r in log if r.get("paciente") == paciente_sel]
    if not filas:
        st.info("Este paciente no tiene acciones registradas por el agente.")
        return
    st.dataframe(filas, use_container_width=True, hide_index=True)


def _guardar_trazabilidad_agente() -> None:
    try:
        from core.database import guardar_datos

        guardar_datos(spinner=False)
    except Exception as exc:
        try:
            from core.app_logging import log_event

            log_event("agente_salud", f"guardar_trazabilidad_error:{type(exc).__name__}")
        except Exception:
            pass


def render_agente_salud(paciente_sel, mi_empresa, user, rol):
    _css()
    if not paciente_sel:
        aviso_sin_paciente()
        return
    from core.ui_liviano import headers_sugieren_equipo_liviano
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"

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

    if es_movil:
        cols = st.columns(3)
        cols[0].metric("TA", dashboard.get("ultima_ta", "-"))
        cols[1].metric("FC", dashboard.get("ultima_fc", "-"))
        cols[2].metric("Temp", dashboard.get("ultima_temp", "-"))
        cols = st.columns(2)
        cols[0].metric("SatO2", dashboard.get("ultima_spo2", "-"))
        cols[1].metric("Glu", dashboard.get("ultima_glu", "-"))
    else:
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

    tab_acciones, tab_pase, tab_plan, tab_inst, tab_log = st.tabs(
        ["Acciones", "Pase y auditoria", "Plan de hoy", "Institucion", "Trazabilidad"]
    )

    with tab_acciones:
        st.subheader("Acciones")
        if resultado.tareas_urgentes:
            st.warning(f"{len(resultado.tareas_urgentes)} tarea(s) urgente(s) para revisar hoy.")
        for idx, accion in enumerate(acciones, start=1):
            _render_action(accion, idx, paciente_sel, user)

        st.download_button(
            "Descargar plan",
            data=exportar_plan_texto(resultado),
            file_name=f"plan_agente_salud_{str(paciente_sel)[:24]}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with tab_pase:
        st.subheader("Pase de guardia")
        st.text_area("Texto para pase", resultado.pase_guardia, height=220)
        st.download_button(
            "Descargar pase de guardia",
            data=exportar_pase_guardia(resultado),
            file_name=f"pase_guardia_{str(paciente_sel)[:24]}.txt",
            mime="text/plain",
            use_container_width=True,
        )
        st.divider()
        st.subheader("Resumen para derivacion o auditoria")
        st.text_area("Texto para derivacion/auditoria", resultado.resumen_derivacion, height=260)
        st.download_button(
            "Descargar resumen",
            data=exportar_resumen_derivacion(resultado),
            file_name=f"resumen_derivacion_{str(paciente_sel)[:24]}.txt",
            mime="text/plain",
            use_container_width=True,
        )

    with tab_plan:
        _render_plan_hoy(resultado, paciente_sel, user)

    with tab_inst:
        st.subheader("Pacientes criticos primero")
        pacientes = _pacientes_visibles_para_priorizar(mi_empresa)
        limite = st.slider("Pacientes a evaluar", 5, 50, min(20, max(5, len(pacientes) or 5)))
        if st.button("Priorizar institucion", use_container_width=True):
            with st.spinner("Priorizando pacientes..."):
                st.session_state["_agente_priorizacion_institucion"] = [
                    p.__dict__
                    for p in priorizar_pacientes_institucion(
                        pacientes,
                        mi_empresa=mi_empresa,
                        limite=limite,
                    )
                ]
        priorizados = st.session_state.get("_agente_priorizacion_institucion", [])
        if priorizados:
            criticos = sum(1 for p in priorizados if p.get("estado") == "critico")
            urgentes = sum(int(p.get("tareas_urgentes") or 0) for p in priorizados)
            c1, c2, c3 = st.columns(3)
            c1.metric("Pacientes evaluados", len(priorizados))
            c2.metric("Criticos", criticos)
            c3.metric("Tareas urgentes", urgentes)
            st.dataframe(priorizados, use_container_width=True, hide_index=True)
            st.download_button(
                "Descargar priorizacion CSV",
                data=exportar_priorizacion_institucion(priorizados),
                file_name="priorizacion_institucional_agente_salud.csv",
                mime="text/csv",
                use_container_width=True,
            )

            opciones = [str(p.get("paciente_id") or "") for p in priorizados if p.get("paciente_id")]
            if opciones:
                paciente_priorizado = st.selectbox(
                    "Abrir paciente priorizado",
                    opciones,
                    key="agente_salud_paciente_priorizado",
                )
                if st.button("Usar paciente seleccionado", use_container_width=True):
                    from core.utils_pacientes import set_paciente_actual

                    set_paciente_actual(st.session_state, paciente_priorizado)
                    st.toast("Paciente seleccionado para revisar.")
                    st.rerun()
        else:
            st.info("Ejecuta la priorizacion para ordenar los pacientes por criticidad.")

    with tab_log:
        _render_trazabilidad(paciente_sel)

    with st.expander("Limites clinicos", expanded=False):
        for item in resultado.guardrails:
            st.caption(item)
