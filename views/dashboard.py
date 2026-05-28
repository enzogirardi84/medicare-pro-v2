from __future__ import annotations

import time
from datetime import datetime, timedelta
from html import escape

import altair as alt
import pandas as pd
import streamlit as st

from core.clinicas_control import sincronizar_clinicas_desde_datos
from core.view_helpers import bloque_estado_vacio, bloque_mc_grid_tarjetas
from core.utils import (
    ahora,
    calcular_estado_agenda,
    filtrar_registros_empresa,
    mapa_detalles_pacientes,
    parse_agenda_datetime,
    parse_fecha_hora,
)
from views._dashboard_utils import (
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
    render_chart_card,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_DANGER,
    COLOR_INFO,
)
from core.app_logging import log_event
from core.computed_cache import cached_computed


def render_dashboard(mi_empresa, rol):
    _widgets = st.session_state.setdefault("_dashboard_widgets", {
        "resumen_turno": True,
        "acciones_rapidas": True,
        "stock_critico": True,
        "pendientes_facturar": True,
        "vitales_alertas": True,
    })
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

    with st.expander("⚙️ Personalizar dashboard", expanded=False):
        _cols = st.columns(3)
        _widget_keys = list(_widgets.keys())
        for i, _wk in enumerate(_widget_keys):
            with _cols[i % 3]:
                _widgets[_wk] = st.toggle(
                    _wk.replace("_", " ").title(),
                    value=_widgets[_wk],
                    key=f"dw_{_wk}",
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
        dc1, dc2 = st.columns(2)
        dc1.metric("Clinicas registradas", n_clin)
        dc1.metric("Activas", n_act)
        dc2.metric("Suspendidas", n_susp)
        with dc2:
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

    if _widgets.get("stock_critico"):
        # ── Alerta de stock crítico ─────────────────────────────────
        try:
            from core._insumos_map import sugerencias_reposicion

            _stock_crit = sugerencias_reposicion(mi_empresa)
            if _stock_crit:
                with st.expander(
                    f"🔴 Stock crítico — {len(_stock_crit)} insumo(s) por debajo del mínimo",
                    expanded=False,
                ):
                    for item in _stock_crit[:10]:
                        st.markdown(
                            f"- **{item['item']}**: {item['stock']} uds. "
                            f"(mínimo {item['stock_minimo']}) → reponer **{item['sugerido']}**"
                        )
        except Exception as exc:
            log_event("dashboard", f"stock_crit fallo: {type(exc).__name__}")

    if _widgets.get("acciones_rapidas"):
        # ── ACCIONES RÁPIDAS ───────────────────────────────────────────
        _pac = st.session_state.get("paciente_actual")
        if _pac:
            st.markdown("### ⚡ Acciones rápidas")
            _cols = st.columns(3)
            _acciones = [
                ("📝", "Evolución", "Evolucion"),
                ("❤️", "Signos vitales", "Clinica"),
                ("💊", "Medicación", "Recetas"),
                ("📋", "Admisión", "Admision"),
            ]
            _rol = str(st.session_state.get("u_actual", {}).get("rol", "")).lower()
            if _rol in ("superadmin", "admin", "administrativo"):
                _acciones.append(("💰", "Caja / Facturar", "Caja"))
            for i, (_ico, _txt, _mod) in enumerate(_acciones):
                with _cols[i % 3]:
                    if st.button(f"{_ico} {_txt}", key=f"da_{_mod}", use_container_width=True):
                        st.session_state["modulo_actual"] = _mod
                        st.session_state["modulo_anterior"] = "Dashboard"
                        st.rerun()
            st.divider()

    # ============================================================
    # BÚSQUEDA GLOBAL EN EVOLUCIONES
    # ============================================================
    st.markdown("### 🔍 Búsqueda global en evoluciones")
    _global_q = st.text_input("Buscar texto en todas las evoluciones", placeholder="Ej: fiebre, caida, dolor...", key="global_search_v2")
    if _global_q.strip():
        _q = _global_q.strip().lower()
        _resultados = {}
        _evos_todas = st.session_state.get("evoluciones_db", [])
        for _evo in _evos_todas:
            _texto = (_evo.get("texto", "") + " " + _evo.get("detalle", "") + " " + _evo.get("nota", "")).lower()
            if _q in _texto:
                _pac = _evo.get("paciente", "Desconocido")
                _resultados.setdefault(_pac, []).append(_evo)
        if _resultados:
            st.success(f"📄 {sum(len(v) for v in _resultados.values())} resultados en {len(_resultados)} pacientes")
            for _pac, _evos in sorted(_resultados.items()):
                with st.expander(f"**{_pac}** ({len(_evos)} resultados)", key=f"dash_evos_{_pac}"):
                    for _evo in _evos[-10:]:  # último 10 por paciente
                        _fecha = (_evo.get("fecha") or "")[:16]
                        _texto_corto = (_evo.get("texto", "") or _evo.get("nota", "") or "")[:200]
                        st.caption(f"📅 {_fecha}")
                        st.markdown(f"_{_texto_corto}_")
                        st.divider()
        else:
            st.info(f"Sin resultados para '{_global_q}'")

    if _widgets.get("resumen_turno"):
        # ── Resumen de turno ─────────────────────────────────────────
        try:
            from core.utils import ahora as _ahora
            _hoy = _ahora().strftime("%d/%m/%Y")
            _emp = mi_empresa
            # Administraciones de hoy (cacheado: solo recalcula cada 2s si datos cambian)
            _adm_db = st.session_state.get("administracion_med_db", [])
            _ads_hoy = cached_computed("dash_adm_hoy", _adm_db, ttl=2.0,
                compute_fn=lambda db=_adm_db, h=_hoy, e=_emp: [
                    a for a in db if a.get("fecha", "").startswith(h) and a.get("empresa") == e and "Realizada" in a.get("estado", "")
                ])
            _evo_db = st.session_state.get("evoluciones_db", [])
            _evos_hoy = cached_computed("dash_evos_hoy", _evo_db, ttl=2.0,
                compute_fn=lambda db=_evo_db, h=_hoy: [
                    e for e in db if e.get("fecha", "").startswith(h) and e.get("paciente")
                ])
            _con_db = st.session_state.get("consumos_db", [])
            _consumos_hoy = cached_computed("dash_cons_hoy", _con_db, ttl=2.0,
                compute_fn=lambda db=_con_db, h=_hoy, e=_emp: [
                    c for c in db if c.get("fecha", "").startswith(h) and c.get("empresa") == e
                ])
            _fac_db = st.session_state.get("facturacion_db", [])
            _pend_fact = cached_computed("dash_fact_pend", _fac_db, ttl=2.0,
                compute_fn=lambda db=_fac_db, e=_emp: [
                    f for f in db if f.get("estado", "").startswith("Pendiente") and f.get("empresa") == e
                ])
            with st.expander("📋 Resumen de turno (hoy)", expanded=False):
                ca, cb = st.columns(2)
                ca.metric("💊 Dosis administradas", len(_ads_hoy))
                ca.metric("📝 Evoluciones registradas", len(_evos_hoy))
                cb.metric("📦 Insumos consumidos", sum(int(c.get("cantidad", 0)) for c in _consumos_hoy))
                cb.metric("⏳ Pendientes facturar", len(_pend_fact))
        except Exception as exc:
            log_event("dashboard", f"resumen_turno fallo: {type(exc).__name__}")

    # Tareas pendientes globales
    _tareas = st.session_state.get("tareas_db", [])
    _pendientes = [t for t in _tareas if not t.get("completada")]
    if _pendientes:
        with st.expander(f"📋 Tareas pendientes ({len(_pendientes)})", expanded=False):
            for t in _pendientes[:10]:
                st.caption(f"**{t.get('paciente', '?')}**: {(t.get('tarea') or '')[:80]}")

    # ── Estado del último backup ─────────────────────────────────
    _ultimo_backup_ts = st.session_state.get("_ultimo_backup_ts", 0)
    if _ultimo_backup_ts:
        _hace = int(time.time() - _ultimo_backup_ts)
        if _hace < 86400:
            st.caption(f"💾 Último backup: hace {_hace//3600}h {(_hace%3600)//60}min")
        else:
            st.caption(f"💾 Último backup: hace {_hace//86400}d")

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
    urgencias_30 = []
    for x in emergencias:
        _dt = parse_fecha_hora(f"{x.get('fecha_evento', '')} {x.get('hora_evento', '')}")
        if _dt not in (None, datetime.min) and _dt >= hace_30_dias:
            urgencias_30.append(x)
    meds_suspendidas = [x for x in indicaciones if str(x.get("estado_receta", "Activa")) in {"Suspendida", "Modificada"}]
    fact_mes = _sumar_importe(facturacion)
    balance_actual = sum(float(x.get("balance", 0) or 0) for x in balance[-30:])

    # ── Alerta de visitas vencidas del profesional en sesión ────
    _user_nombre = st.session_state.get("u_actual", {}).get("nombre", "")
    if _user_nombre:
        _visitas_vencidas = [
            x for x in agenda_enriquecida
            if x.get("profesional") == _user_nombre
            and x.get("estado_calc") == "Vencida"
        ]
        if _visitas_vencidas:
            st.warning(f"⏰ Tenés **{len(_visitas_vencidas)} visita(s) vencida(s)** sin marcar como realizadas o canceladas.")

    # ── Alerta de turnos vencidos en general ────────────────────
    _vencidos_total = [x for x in agenda_enriquecida if x.get("estado_calc") == "Vencida"]
    if _vencidos_total and not _user_nombre:
        st.caption(f"⏰ {len(_vencidos_total)} turno(s) vencido(s) en la agenda general.")

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

    if fact_mes is not None:
        st.caption(f"Facturacion cargada en el sistema: ${fact_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    # Activity data: compute once, reuse for 7-day chart + 30-day heatmap
    with st.spinner("Calculando actividad..."):
        from collections import defaultdict
        _ag_count = defaultdict(int)
        for x in agenda_enriquecida:
            _ag_count[x["_fecha_dt"].date()] += 1
        _ch_count = defaultdict(int)
        for x in checkins:
            _ch_count[parse_fecha_hora(x.get("fecha_hora", "")).date()] += 1
        _actividad_por_dia = {}
        for i in range(29, -1, -1):
            d = hoy - timedelta(days=i)
            _actividad_por_dia[d] = _ag_count.get(d, 0) + _ch_count.get(d, 0)

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

    if _widgets.get("vitales_alertas"):
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
            st.altair_chart(_heatmap, width='stretch')
        else:
            st.caption("Sin actividad registrada en los últimos 30 días.")

    st.divider()
    st.markdown("#### Vista operativa")
    render_vista_operativa(agenda_enriquecida, visitas_hoy, urgencias_30, _pac_ids, hoy, es_movil)

    st.divider()
    if not es_movil:
        st.markdown("#### Listados ejecutivos")
    render_listados_ejecutivos(agenda_enriquecida, meds_suspendidas, mi_empresa, rol, es_movil)

    # Mapa geográfico de visitas + Reporte PDF (solo escritorio)
    if not es_movil:
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
                                "lat": lat_v, "lon": lon_v,
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

            _markers_html = ""
            for _, r in _df_gps.iterrows():
                _name = escape(str(r.get("paciente", "")))
                _type = escape(str(r.get("tipo", "")))
                _date = escape(str(r.get("fecha", "")))
                _popup = f"{_name}<br/>{_type}<br/>{_date}".replace("'", "\\'")
                _markers_html += f"""
L.marker([{r['lat']}, {r['lon']}]).addTo(_map).bindPopup('{_popup}');"""

            _html_map = f"""
<!DOCTYPE html>
<html><head>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>body {{ margin:0; padding:0; }} #map {{ height:100vh; width:100%; }}</style>
</head><body>
<div id="map"></div>
<script>
var _map = L.map('map').setView([{_lat_center}, {_lon_center}], 13);
L.tileLayer('https://{{s}}.tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png', {{
    attribution: '&copy; OpenStreetMap contributors', maxZoom: 19,
}}).addTo(_map);
{_markers_html}
</script></body></html>"""

            col_map_1, col_map_2 = st.columns([2, 1])
            with col_map_1:
                st.html(_html_map)
            with col_map_2:
                st.caption(f"{len(_gps_data)} visitas con GPS")
                _df_gps_show = _df_gps[["paciente", "tipo", "fecha"]].copy()
                _df_gps_show.columns = ["Paciente", "Tipo", "Fecha"]
                st.dataframe(_df_gps_show.tail(10), width='stretch', height=300, hide_index=True)
        else:
            st.caption("Sin datos de GPS disponibles. Las visitas fichadas con GPS aparecerán aquí.")

        st.divider()
