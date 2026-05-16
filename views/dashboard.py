from datetime import datetime, timedelta
from html import escape

import altair as alt
import pandas as pd
import pydeck as pdk
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
from core.charts import (
    render_metric_card,
    render_kpi_row,
    chart_barras,
    chart_linea,
    render_chart_card,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_DANGER,
    COLOR_INFO,
    COLORS_CATEGORICAL,
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
    with st.spinner("Cargando emergencias..."):
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

    _kpi_snapshot = {
        "activos": activos,
        "altas": altas,
        "visitas_hoy": len(visitas_hoy),
        "pendientes_hoy": len(pendientes_hoy),
        "proximas_48": len(proximas_48),
        "urgencias_30": len(urgencias_30),
        "meds_suspendidas": len(meds_suspendidas),
        "balance_actual": balance_actual,
    }
    _kpi_history = st.session_state.setdefault("_dash_kpi_history", {})
    _today_key = str(ahora_local.date())
    if _today_key not in _kpi_history:
        _kpi_history[_today_key] = dict(_kpi_snapshot)
    _yesterday_key = str((ahora_local - timedelta(days=1)).date())
    _prev = _kpi_history.get(_yesterday_key, {})
    def _calc_delta(key):
        prev_val = _prev.get(key)
        curr_val = _kpi_snapshot[key]
        if prev_val is not None and isinstance(prev_val, (int, float)) and prev_val > 0:
            return round((curr_val - prev_val) / prev_val * 100, 1)
        return None

    kpi_data = [
        (activos, "Pacientes activos", _calc_delta("activos"), "👤", COLOR_PRIMARY),
        (altas, "De alta", _calc_delta("altas"), "✅", COLOR_SUCCESS),
        (len(visitas_hoy), "Visitas hoy", _calc_delta("visitas_hoy"), "🏥", COLOR_INFO),
        (len(pendientes_hoy), "Pendientes hoy", _calc_delta("pendientes_hoy"), "📋", COLOR_WARNING),
        (len(proximas_48), "Próximas 48h", _calc_delta("proximas_48"), "📅", COLOR_PRIMARY),
        (len(urgencias_30), "Urgencias 30d", _calc_delta("urgencias_30"), "🚨", COLOR_DANGER),
        (len(meds_suspendidas), "Cambios medicación", _calc_delta("meds_suspendidas"), "💊", COLOR_WARNING),
        (f"{balance_actual:.0f}ml", "Balance registrado", _calc_delta("balance_actual"), "⚖️", COLOR_INFO),
    ]
    render_kpi_row(kpi_data, cols=4 if not es_movil else 2)

    if fact_mes:
        st.caption(f"Facturacion cargada en el sistema: ${fact_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # Activity data: compute once, reuse for 7-day chart + 30-day heatmap
    with st.spinner("Calculando actividad..."):
        _actividad_por_dia = {}
        for i in range(29, -1, -1):
            d = hoy - timedelta(days=i)
            ag = sum(1 for x in agenda_enriquecida if x["_fecha_dt"].date() == d)
            ch = sum(1 for x in checkins if parse_fecha_hora(x.get("fecha_hora", "")).date() == d)
            _actividad_por_dia[d] = ag + ch

    if not es_movil:
        st.divider()
        st.markdown("#### Actividad semanal")
        act_cols = st.columns([2, 1])
        with act_cols[0]:
            _dias_7 = [(hoy - timedelta(days=i)) for i in range(6, -1, -1)]
            _df_act = pd.DataFrame({
                "dia": [d.strftime("%a %d/%m") for d in _dias_7],
                "actividad": [_actividad_por_dia.get(d, 0) for d in _dias_7],
            })
            _chart = chart_barras(_df_act, "dia", "actividad", color="actividad", titulo_x="Día", titulo_y="Actividad")
            if _chart:
                render_chart_card("Turnos y visitas por día", _chart)
        with act_cols[1]:
            _prox_count = len(proximas_48)
            _urg_count = len(urgencias_30)
            render_metric_card(_prox_count, "Próximas 48h", icono="📅", color=COLOR_INFO)
            st.write("")
            render_metric_card(_urg_count, "Urgencias 30d", icono="🚨", color=COLOR_DANGER)
            st.write("")
            render_metric_card(activos, "Pacientes activos", icono="👤", color=COLOR_PRIMARY)

    render_vitales_alertas(st.session_state.get("vitales_db", []), _pac_ids)

    if not es_movil:
        st.divider()
        st.markdown("#### Calendario de actividad (30 días)")
        _cal_df = pd.DataFrame([
            {"fecha": d, "actividad": _actividad_por_dia.get(d, 0)}
            for d in [(hoy - timedelta(days=i)) for i in range(29, -1, -1)]
        ])
        if not _cal_df.empty and _cal_df["actividad"].sum() > 0:
            _cal_df["fecha"] = pd.to_datetime(_cal_df["fecha"])
            _cal_df["dia_num"] = _cal_df["fecha"].dt.weekday
            _cal_df["semana"] = _cal_df["fecha"].dt.isocalendar().week.astype(int)
            _cal_df["label"] = _cal_df["fecha"].dt.strftime("%d/%m")
            _heatmap = alt.Chart(_cal_df).mark_rect(stroke="#0f172a", strokeWidth=1).encode(
                x=alt.X("semana:O", title="Semana", axis=alt.Axis(labelAngle=0)),
                y=alt.Y("dia_num:O", title="",
                        sort=alt.EncodingSortField("dia_num", order="ascending"),
                        axis=alt.Axis(tickCount=7, labelExpr="['Lun','Mar','Mié','Jue','Vie','Sáb','Dom'][datum.value]")),
                color=alt.Color("actividad:Q", title="Actividad",
                                scale=alt.Scale(scheme="oranges")),
                tooltip=[alt.Tooltip("label:N", title="Fecha"),
                         alt.Tooltip("actividad:Q", title="Actividad")],
            ).properties(height=200).configure_view(strokeWidth=0).configure_axis(
                labelFontSize=10, titleFontSize=11
            ).configure_legend(
                gradientLength=120, labelFontSize=10
            )
            st.altair_chart(_heatmap, use_container_width=True)
        else:
            st.caption("Sin actividad registrada en los últimos 30 días.")

    st.divider()
    st.markdown("#### Vista operativa")
    render_vista_operativa(agenda_enriquecida, visitas_hoy, urgencias_30, _pac_ids, hoy, es_movil)

    st.divider()
    if not es_movil:
        st.markdown("#### Listados ejecutivos")
    render_listados_ejecutivos(agenda_enriquecida, meds_suspendidas, mi_empresa, rol, es_movil)

    # Mapa geográfico de visitas
    st.divider()
    st.markdown("#### Mapa de visitas (GPS real)")
    _gps_data = []
    with st.spinner("Procesando datos de GPS..."):
        for c in checkins:
            gps_str = c.get("gps", "")
            if gps_str and "," in gps_str:
                try:
                    lat_str, lon_str = gps_str.split(",", 1)
                    lat_v = float(lat_str)
                    lon_v = float(lon_str)
                    if lat_v != 0.0 or lon_v != 0.0:
                        _gps_data.append({
                            "lat": lat_v,
                            "lon": lon_v,
                            "paciente": c.get("paciente", ""),
                            "tipo": c.get("tipo", ""),
                            "fecha": c.get("fecha_hora", ""),
                        })
                except (ValueError, TypeError):
                    continue
    if _gps_data:
        _df_gps = pd.DataFrame(_gps_data)
        _lat_center = _df_gps["lat"].mean()
        _lon_center = _df_gps["lon"].mean()
        _view = pdk.ViewState(latitude=_lat_center, longitude=_lon_center, zoom=12, pitch=0)
        _layer = pdk.Layer(
            "ScatterplotLayer",
            data=_df_gps,
            get_position='[lon, lat]',
            get_radius=120,
            get_fill_color=[59, 130, 246, 180],
            pickable=True,
            auto_highlight=True,
            tooltip={
                "html": "<b>{paciente}</b><br/>{tipo}<br/>{fecha}",
                "style": {"backgroundColor": "#1e293b", "color": "#e2e8f0"},
            },
        )
        _deck = pdk.Deck(
            layers=[_layer],
            initial_view_state=_view,
            map_style="https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json",
            tooltip={"text": "{paciente}"},
        )
        col_map_1, col_map_2 = st.columns([2, 1])
        with col_map_1:
            st.pydeck_chart(_deck, use_container_width=True)
        with col_map_2:
            st.caption(f"{len(_gps_data)} visitas con GPS")
            _df_gps_show = _df_gps[["paciente", "tipo", "fecha"]].copy()
            _df_gps_show.columns = ["Paciente", "Tipo", "Fecha"]
            st.dataframe(_df_gps_show.tail(10), use_container_width=True, height=300, hide_index=True)
    else:
        st.caption("Sin datos de GPS disponibles. Las visitas fichadas con GPS aparecerán aquí.")

    # Reporte Ejecutivo PDF
    st.divider()
    try:
        from core.reporte_ejecutivo import render_reporte_ejecutivo
        render_reporte_ejecutivo(mi_empresa)
    except Exception as _e:
        log_event("dashboard", f"reporte_ejecutivo:{type(_e).__name__}")
