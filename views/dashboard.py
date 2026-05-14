from datetime import datetime, timedelta
from html import escape

import pandas as pd
import streamlit as st

from core.clinicas_control import sincronizar_clinicas_desde_datos
from core.view_helpers import bloque_estado_vacio, bloque_mc_grid_tarjetas, lista_plegable
from core.utils import (
    ahora,
    calcular_estado_agenda,
    filtrar_registros_empresa,
    mapa_detalles_pacientes,
    mostrar_dataframe_con_scroll,
    parse_agenda_datetime,
    parse_fecha_hora,
    seleccionar_limite_registros,
)
from views._dashboard_utils import (
    _estado_vital_dash,
    _estado_ta_dash,
    _evaluar_ultimo_vital,
    _sumar_importe,
)
from views._dashboard_bloques import (
    render_notificaciones_turno,
    render_vitales_alertas,
    render_vista_operativa,
    render_listados_ejecutivos,
)
from core.app_logging import log_event


def render_dashboard(mi_empresa, rol):
    from core.ui_liviano import headers_sugieren_equipo_liviano
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"

    if es_movil:
        st.markdown(
            f'<div class="mc-hero"><h2 class="mc-hero-title">Dashboard</h2>'
            f'<p class="mc-hero-text" style="font-size:0.82rem;margin:0">{escape(str(mi_empresa))}</p></div>',
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            f"""
            <div class="mc-hero">
                <h2 class="mc-hero-title">Dashboard ejecutivo</h2>
                <p class="mc-hero-text">Lectura rapida para {escape(str(mi_empresa))}: pacientes, agenda, visitas del dia, urgencias recientes y cambios de medicacion. Abajo, graficos y listados para priorizar acciones.</p>
                <div class="mc-chip-row">
                    <span class="mc-chip">Pacientes activos</span>
                    <span class="mc-chip">Agenda y urgencias</span>
                    <span class="mc-chip">Productividad por profesional</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        bloque_mc_grid_tarjetas(
            [
                ("Agenda", "Turnos por estado y lista prioritaria: quien viene y cuando."),
                ("Operacion", "Conteo de activos, altas y visitas fichadas hoy."),
                ("Alertas", "Urgencias ultimos 30 dias, medicacion suspendida/modificada y balance."),
            ]
        )
        st.caption(
            "Las metricas de la primera fila son conteos del momento; la segunda fila mezcla ventana de 48 h, 30 dias y senales clinicas. Los listados al final se pueden acotar con el selector de cantidad."
        )

    rol_n = str(rol or "").strip().lower()
    if rol_n in {"superadmin", "admin"}:
        sincronizar_clinicas_desde_datos(st.session_state)
        db_cl = st.session_state.get("clinicas_db") or {}
        if not isinstance(db_cl, dict):
            db_cl = {}
        n_clin = 0
        n_susp = 0
        for _k, reg in db_cl.items():
            if not isinstance(reg, dict):
                continue
            n_clin += 1
            if str(reg.get("estado", "Activa")).strip().lower() == "suspendida":
                n_susp += 1
        n_act = n_clin - n_susp
        st.markdown("##### Red de clinicas (panel global)")
        dc1, dc2, dc3, dc4 = st.columns(4)
        dc1.metric("Clinicas registradas", n_clin)
        dc2.metric("Activas", n_act)
        dc3.metric("Suspendidas", n_susp)
        with dc4:
            st.caption("Gestion detallada, suspension logica y CSV en el modulo **Clinicas (panel global)**.")
        st.divider()

    _dm_dash = mapa_detalles_pacientes(st.session_state)
    pacientes = filtrar_registros_empresa(
        [
            {
                "paciente": p,
                **_dm_dash.get(p, {}),
            }
            for p in st.session_state.get("pacientes_db", [])
        ],
        mi_empresa,
        rol,
    )
    if not pacientes:
        bloque_estado_vacio(
            "Sin pacientes visibles",
            "No hay pacientes que coincidan con tu empresa y rol en este momento.",
            sugerencia="Revisá Admisión para altas o pedí a un coordinador que confirme la clínica del paciente.",
        )
        return

    agenda = filtrar_registros_empresa(st.session_state.get("agenda_db", []), mi_empresa, rol)
    checkins = filtrar_registros_empresa(st.session_state.get("checkin_db", []), mi_empresa, rol)
    
    # 1. Intentar leer emergencias desde PostgreSQL (Hybrid Read)
    emergencias = []
    try:
        from core.db_sql import get_emergencias_by_empresa
        from core.nextgen_sync import _obtener_uuid_empresa
        empresa_uuid = _obtener_uuid_empresa(mi_empresa)
        if empresa_uuid:
            emg_sql = get_emergencias_by_empresa(empresa_uuid, limit=100)
            if emg_sql:
                for e in emg_sql:
                    dt = pd.to_datetime(e.get("fecha_llamado", ""), errors="coerce")
                    emergencias.append({
                        "fecha_evento": dt.strftime("%d/%m/%Y") if pd.notnull(dt) else "",
                        "hora_evento": dt.strftime("%H:%M") if pd.notnull(dt) else "",
                        "triage_grado": "Grado 1 - Rojo" if e.get("prioridad") == "Critica" else "Grado 2 - Amarillo" if e.get("prioridad") == "Alta" else "Grado 3 - Verde",
                    })
    except Exception as e:
        log_event('dashboard_error', f'Error: {e}')
        
    if not emergencias:
        emergencias = filtrar_registros_empresa(st.session_state.get("emergencias_db", []), mi_empresa, rol)
        
    facturacion = filtrar_registros_empresa(st.session_state.get("facturacion_db", []), mi_empresa, rol)
    balance = filtrar_registros_empresa(st.session_state.get("balance_db", []), mi_empresa, rol)
    _pac_ids = {p["paciente"] for p in pacientes}
    indicaciones = [
        x
        for x in st.session_state.get("indicaciones_db", [])
        if x.get("paciente") in _pac_ids
    ]

    ahora_local = ahora().replace(tzinfo=None)
    hoy = ahora_local.date()
    proximas_48h_limite = ahora_local + timedelta(hours=48)
    hace_30_dias = ahora_local - timedelta(days=30)

    activos = sum(1 for x in pacientes if x.get("estado", "Activo") == "Activo")
    altas = sum(1 for x in pacientes if x.get("estado") == "De Alta")

    agenda_enriquecida = []
    for item in agenda:
        enriched = dict(item)
        enriched["_fecha_dt"] = parse_agenda_datetime(item)
        enriched["estado_calc"] = calcular_estado_agenda(item, now=ahora_local)
        agenda_enriquecida.append(enriched)

    visitas_hoy = [
        x
        for x in checkins
        if "LLEGADA" in str(x.get("tipo", "")).upper()
        and parse_fecha_hora(x.get("fecha_hora", "")).date() == hoy
    ]
    pendientes_hoy = [x for x in agenda_enriquecida if x["_fecha_dt"].date() == hoy and x["estado_calc"] in {"Pendiente", "En curso", "Vencida"}]
    proximas_48 = [x for x in agenda_enriquecida if x["_fecha_dt"] != datetime.min and ahora_local <= x["_fecha_dt"] <= proximas_48h_limite]
    _fe_urg = lambda x: parse_fecha_hora(f"{x.get('fecha_evento', '')} {x.get('hora_evento', '')}")
    urgencias_30 = [x for x in emergencias if _fe_urg(x) not in (None, datetime.min) and _fe_urg(x) >= hace_30_dias]
    meds_suspendidas = [x for x in indicaciones if str(x.get("estado_receta", "Activa")) in {"Suspendida", "Modificada"}]
    fact_mes = _sumar_importe(facturacion)
    balance_actual = sum(float(x.get("balance", 0) or 0) for x in balance[-30:])

    render_notificaciones_turno(pacientes, indicaciones, ahora_local, hoy, proximas_48h_limite, _pac_ids)

    if es_movil:
        fila_1 = st.columns(2)
        fila_1[0].metric("Activos", activos)
        fila_1[1].metric("De alta", altas)
        fila_2 = st.columns(2)
        fila_2[0].metric("Visitas hoy", len(visitas_hoy))
        fila_2[1].metric("Pendientes", len(pendientes_hoy))
        fila_3 = st.columns(2)
        fila_3[0].metric("48h", len(proximas_48))
        fila_3[1].metric("Urgencias", len(urgencias_30))
        if meds_suspendidas or balance_actual:
            fila_4 = st.columns(2)
            fila_4[0].metric("Cambios med.", len(meds_suspendidas))
            fila_4[1].metric("Balance", f"{balance_actual:.0f}")
    else:
        fila_1 = st.columns(2)
        fila_1[0].metric("Pacientes activos", activos)
        fila_1[1].metric("Pacientes de alta", altas)

        fila_2 = st.columns(2)
        fila_2[0].metric("Visitas hoy", len(visitas_hoy))
        fila_2[1].metric("Pendientes hoy", len(pendientes_hoy))

        fila_3 = st.columns(2)
        fila_3[0].metric("Proximas 48h", len(proximas_48))
        fila_3[1].metric("Urgencias 30 dias", len(urgencias_30))

        fila_4 = st.columns(2)
        fila_4[0].metric("Cambios de medicacion", len(meds_suspendidas))
        fila_4[1].metric("Balance registrado", f"{balance_actual:.0f}")

    if fact_mes:
        st.caption(f"Facturacion cargada en el sistema: ${fact_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    render_vitales_alertas(st.session_state.get("vitales_db", []), _pac_ids)

    st.divider()
    st.markdown("#### Vista operativa")
    render_vista_operativa(agenda_enriquecida, visitas_hoy, urgencias_30, _pac_ids, hoy, es_movil)

    st.divider()
    if not es_movil:
        st.markdown("#### Listados ejecutivos")
    render_listados_ejecutivos(agenda_enriquecida, meds_suspendidas, mi_empresa, rol, es_movil)

    # Reporte Ejecutivo PDF
    st.divider()
    try:
        from core.reporte_ejecutivo import render_reporte_ejecutivo
        render_reporte_ejecutivo(mi_empresa)
    except Exception:
        pass
