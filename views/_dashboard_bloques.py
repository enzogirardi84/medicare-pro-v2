"""Bloques de UI del dashboard. Extraído de views/dashboard.py."""
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from core.utils import (
    parse_fecha_hora,
    mostrar_dataframe_con_scroll,
    seleccionar_limite_registros,
)
from core.view_helpers import bloque_estado_vacio, lista_plegable
from views._dashboard_utils import _evaluar_ultimo_vital, _sumar_importe


# Mapeo de colores semánticos para estados de agenda
_COLOR_ESTADO_AGENDA = {
    "Vencida": "#ef4444",
    "Pendiente": "#f59e0b",
    "Confirmada": "#10b981",
    "Completada": "#3b82f6",
    "Cancelada": "#9ca3af",
}


def _chart_barras_altair(df: pd.DataFrame, x: str, y: str, color_map: dict | None = None, titulo_eje_x: str = "", titulo_eje_y: str = "") -> alt.Chart:
    """Crea un gráfico de barras horizontal con Altair para evitar rotación de etiquetas."""
    base = alt.Chart(df).encode(
        x=alt.X(f"{y}:Q", title=titulo_eje_y),
        y=alt.Y(f"{x}:O", sort="-x", title=titulo_eje_x),
        tooltip=[alt.Tooltip(f"{x}:N", title=titulo_eje_x or x), alt.Tooltip(f"{y}:Q", title=titulo_eje_y or y)],
    )
    if color_map:
        base = base.encode(
            color=alt.Color(
                f"{x}:N",
                scale=alt.Scale(domain=list(color_map.keys()), range=list(color_map.values())),
                legend=None,
            )
        )
    return base.mark_bar(cornerRadiusEnd=4).configure_axis(labelFontSize=12, titleFontSize=13).configure_view(strokeWidth=0)


def render_notificaciones_turno(pacientes, indicaciones, ahora_local, hoy, proximas_48h_limite, pac_ids):
    """Bloque de notificaciones clínicas de turno (sin evolución, meds por vencer, estudios, balance)."""
    _notifs = []

    evoluciones = st.session_state.get("evoluciones_db", [])
    _pacs_con_ev_hoy = {
        e.get("paciente") for e in evoluciones
        if parse_fecha_hora(e.get("fecha", "")).date() == hoy
    }
    _pacs_activos_ids = {p["paciente"] for p in pacientes if p.get("estado", "Activo") == "Activo"}
    _sin_ev_hoy = _pacs_activos_ids - _pacs_con_ev_hoy
    if _sin_ev_hoy:
        _notifs.append(("⚠️", "warning", f"**{len(_sin_ev_hoy)} paciente(s) activo(s) sin evolución hoy.** Verificar antes del cierre de turno."))

    _meds_por_vencer = []
    for ind in indicaciones:
        if str(ind.get("estado_receta", "Activa")).strip().lower() not in ("activa", ""):
            continue
        _fv_str = str(ind.get("fecha_vencimiento", "") or ind.get("hasta", "") or "").strip()
        if not _fv_str:
            continue
        try:
            _fv = parse_fecha_hora(_fv_str)
            if _fv != datetime.min and ahora_local <= _fv <= proximas_48h_limite:
                _meds_por_vencer.append(ind)
        except Exception as _exc:
            from core.app_logging import log_event
            log_event("dashboard_alert", f"med_vencer_parse_error:{type(_exc).__name__}:{_fv_str}")
    if _meds_por_vencer:
        _notifs.append(("💊", "warning", f"**{len(_meds_por_vencer)} medicación/es** vencen en las próximas 48hs. Revisar prescripciones."))

    _CRITICOS = {"Tomografia (TAC)", "Resonancia Magnetica (RMN)", "Electrocardiograma (ECG)"}
    estudios_db = st.session_state.get("estudios_db", [])
    _estudios_pac = [e for e in estudios_db if e.get("paciente") in pac_ids]
    _estudios_crit_sin_res = []
    for e in _estudios_pac:
        if e.get("tipo") not in _CRITICOS:
            continue
        if str(e.get("detalle", "")).strip().lower() not in ("", "sin resultado", "-", "s/d"):
            continue
        try:
            _fe = parse_fecha_hora(e.get("fecha", ""))
            if _fe != datetime.min and (ahora_local - _fe).days > 7:
                _estudios_crit_sin_res.append(e)
        except Exception as _exc:
            from core.app_logging import log_event
            log_event("dashboard_alert", f"estudio_critico_parse_error:{type(_exc).__name__}:{e.get('fecha','')}")
    if _estudios_crit_sin_res:
        _notifs.append(("🔬", "error", f"**{len(_estudios_crit_sin_res)} estudio(s) crítico(s)** sin resultado en más de 7 días (TAC/RMN/ECG)."))

    balance_db = st.session_state.get("balance_db", [])
    _pacs_activos_ids2 = {p["paciente"] for p in pacientes if p.get("estado", "Activo") == "Activo"}
    _bal_severos = []
    for _pac_id in _pacs_activos_ids2:
        _bal_pac = [b for b in balance_db if b.get("paciente") == _pac_id]
        if len(_bal_pac) >= 3:
            _neto3 = sum(float(b.get("balance", 0) or 0) for b in _bal_pac[-3:])
            if _neto3 < -1500:
                _bal_severos.append((_pac_id, _neto3))
    if _bal_severos:
        _notifs.append(("🔴", "error", f"**{len(_bal_severos)} paciente(s)** con balance hídrico negativo severo (>-1500ml en últimos 3 turnos)."))

    if _notifs:
        with st.expander(f"🔔 Notificaciones de turno ({len(_notifs)})", expanded=True):
            for icono, nivel, msg in _notifs:
                if nivel == "error":
                    st.error(f"{icono} {msg}")
                else:
                    st.warning(f"{icono} {msg}")
        st.divider()


def render_vitales_alertas(vitales_db, pac_ids):
    """Bloque de alertas de signos vitales críticos o alterados."""
    vitales_alertas = []
    vitales_por_pac = {}
    for v in vitales_db:
        pac = v.get("paciente", "")
        if pac not in pac_ids:
            continue
        ts = parse_fecha_hora(v.get("fecha", ""))
        if pac not in vitales_por_pac or ts > vitales_por_pac[pac]["_ts"]:
            vitales_por_pac[pac] = {**v, "_ts": ts}
    for pac, reg in vitales_por_pac.items():
        est, problemas = _evaluar_ultimo_vital(reg)
        if est in ("critico", "alerta"):
            vitales_alertas.append({
                "paciente": pac,
                "estado": est,
                "fecha": reg.get("fecha", "S/D"),
                "detalle": ", ".join(problemas),
            })
    vitales_alertas.sort(key=lambda x: (0 if x["estado"] == "critico" else 1))
    n_crit_vit = sum(1 for a in vitales_alertas if a["estado"] == "critico")
    n_alert_vit = sum(1 for a in vitales_alertas if a["estado"] == "alerta")

    if vitales_alertas:
        with st.container():
            if n_crit_vit:
                st.error(f"🔴 **{n_crit_vit} paciente(s) con signos vitales CRÍTICOS** en su último control")
            if n_alert_vit:
                st.warning(f"🟡 **{n_alert_vit} paciente(s) con signos vitales alterados** en su último control")
            with st.expander(f"🚨 Detalle — signos vitales fuera de rango ({len(vitales_alertas)} pacientes)", expanded=bool(n_crit_vit)):
                for item in vitales_alertas:
                    icono = "🔴" if item["estado"] == "critico" else "🟡"
                    nombre_corto = item["paciente"].split(" (")[0]
                    st.markdown(f"{icono} **{nombre_corto}** — {item['detalle']} — `{item['fecha']}`")


def render_vista_operativa(agenda_enriquecida, visitas_hoy, urgencias_30, pac_ids, hoy, es_movil):
    """Bloque de gráficos de agenda, visitas y urgencias + evoluciones de hoy."""
    if agenda_enriquecida:
        agenda_estado = (
            pd.DataFrame(agenda_enriquecida)
            .groupby("estado_calc")
            .size()
            .reset_index(name="Cantidad")
            .rename(columns={"estado_calc": "Estado"})
        )
    else:
        agenda_estado = pd.DataFrame(columns=["Estado", "Cantidad"])

    if visitas_hoy:
        df_visitas_hoy = pd.DataFrame(visitas_hoy)
        df_visitas_hoy["fecha_dt"] = df_visitas_hoy["fecha_hora"].apply(parse_fecha_hora)
        visitas_prof = (
            df_visitas_hoy.groupby("profesional")
            .size()
            .reset_index(name="Visitas")
            .rename(columns={"profesional": "Profesional"})
            .sort_values("Visitas", ascending=False)
        )
    else:
        visitas_prof = pd.DataFrame(columns=["Profesional", "Visitas"])

    if urgencias_30:
        df_urg = pd.DataFrame(urgencias_30)
        urg_chart = (
            df_urg.groupby("triage_grado")
            .size()
            .reset_index(name="Eventos")
            .rename(columns={"triage_grado": "Triage"})
        )
    else:
        urg_chart = pd.DataFrame(columns=["Triage", "Eventos"])

    if es_movil:
        with st.expander("📊 Gráficos", expanded=False):
            st.caption("Agenda por estado")
            if not agenda_estado.empty:
                st.altair_chart(
                    _chart_barras_altair(agenda_estado, "Estado", "Cantidad", _COLOR_ESTADO_AGENDA, "Estado", "Cantidad"),
                    use_container_width=True,
                )
            st.caption("Visitas del dia por profesional")
            if not visitas_prof.empty:
                st.altair_chart(
                    _chart_barras_altair(visitas_prof, "Profesional", "Visitas", titulo_eje_x="Profesional", titulo_eje_y="Visitas"),
                    use_container_width=True,
                )
    else:
        col_g1, col_g2 = st.columns(2)
        with col_g1:
            st.caption("Agenda por estado")
            if not agenda_estado.empty:
                st.altair_chart(
                    _chart_barras_altair(agenda_estado, "Estado", "Cantidad", _COLOR_ESTADO_AGENDA, "Estado", "Cantidad"),
                    use_container_width=True,
                )
            else:
                bloque_estado_vacio(
                    "Gráfico sin datos",
                    "Todavía no hay turnos en agenda para armar el gráfico por estado.",
                    sugerencia="Agendá visitas en Visitas y Agenda o revisá filtros de empresa/rol.",
                )
        with col_g2:
            st.caption("Visitas del dia por profesional")
            if not visitas_prof.empty:
                st.altair_chart(
                    _chart_barras_altair(visitas_prof, "Profesional", "Visitas", titulo_eje_x="Profesional", titulo_eje_y="Visitas"),
                    use_container_width=True,
                )
            else:
                bloque_estado_vacio(
                    "Sin visitas hoy",
                    "No hay fichadas o visitas del día con profesional asignado.",
                    sugerencia="El equipo puede registrar llegada/salida en Visitas para ver barras acá.",
                )

    if not urg_chart.empty:
        st.caption("Urgencias por triage (ultimos 30 dias)")
        st.altair_chart(
            _chart_barras_altair(urg_chart, "Triage", "Eventos", titulo_eje_x="Grado de triage", titulo_eje_y="Eventos"),
            use_container_width=True,
        )

    evoluciones_hoy = [
        x for x in st.session_state.get("evoluciones_db", [])
        if x.get("paciente") in pac_ids
        and parse_fecha_hora(x.get("fecha", "")).date() == hoy
    ]
    if evoluciones_hoy:
        evol_label = f"📝 Evoluciones de hoy ({len(evoluciones_hoy)})"
        with st.expander(evol_label, expanded=not es_movil):
            for ev in sorted(evoluciones_hoy, key=lambda x: parse_fecha_hora(x.get("fecha", "")), reverse=True)[:15]:
                nombre_pac = ev.get("paciente", "?").split(" (")[0]
                prof = ev.get("firma") or ev.get("profesional") or ev.get("firmado_por") or "S/D"
                nota = str(ev.get("nota", "") or ev.get("texto", "") or ev.get("detalle", "")).strip()
                hora_ev = parse_fecha_hora(ev.get("fecha", "")).strftime("%H:%M")
                resumen = (nota[:120] + "…") if len(nota) > 120 else nota
                st.markdown(f"**{hora_ev}** — **{nombre_pac}** — `{prof}`: {resumen or '(sin texto)'}")


def render_listados_ejecutivos(agenda_enriquecida, meds_suspendidas, mi_empresa, rol, es_movil):
    """Bloque de listados ejecutivos: agenda prioritaria y cambios de medicación."""
    _listados_label = "📋 Agenda y medicación" if es_movil else "Tablas — agenda prioritaria y medicación"
    with lista_plegable(_listados_label, expanded=False, height=None):
        col_l1, col_l2 = st.columns(1 if es_movil else 2)
        with col_l1:
            st.caption("Agenda prioritaria")
            if agenda_enriquecida:
                df_ag = pd.DataFrame(agenda_enriquecida)
                df_ag["Fecha y Hora"] = df_ag["_fecha_dt"].apply(
                    lambda x: x.strftime("%d/%m/%Y %H:%M") if x != datetime.min else "Sin fecha"
                )
                df_ag = df_ag.rename(columns={"paciente": "Paciente", "profesional": "Profesional", "estado_calc": "Estado"})
                df_ag = df_ag[["Fecha y Hora", "Paciente", "Profesional", "Estado"]].sort_values("Fecha y Hora")
                limite_ag = seleccionar_limite_registros(
                    "Agenda a mostrar",
                    len(df_ag),
                    key=f"dash_agenda_limit_{mi_empresa}_{rol}",
                    default=12,
                    opciones=(6, 12, 20, 30, 50),
                )
                mostrar_dataframe_con_scroll(df_ag.head(limite_ag), height=340)
            else:
                bloque_estado_vacio(
                    "Lista de agenda vacía",
                    "No hay turnos próximos para mostrar en la agenda prioritaria.",
                    sugerencia="Revisá pacientes activos y la carga de agenda en el módulo de visitas.",
                )

        with col_l2:
            st.caption("Cambios recientes de medicacion")
            if meds_suspendidas:
                df_med = pd.DataFrame(meds_suspendidas)
                estado_base = (
                    df_med["estado_receta"] if "estado_receta" in df_med.columns else pd.Series(["Activa"] * len(df_med))
                )
                df_med["Estado"] = estado_base.fillna("Activa")
                profesional_estado = (
                    df_med["profesional_estado"]
                    if "profesional_estado" in df_med.columns
                    else pd.Series([""] * len(df_med))
                )
                medico_nombre = (
                    df_med["medico_nombre"] if "medico_nombre" in df_med.columns else pd.Series([""] * len(df_med))
                )
                df_med["Profesional"] = (
                    profesional_estado.fillna("").replace("", pd.NA).fillna(medico_nombre.fillna("")).replace("", "Sin profesional")
                )
                df_med = df_med.rename(columns={"fecha_estado": "Fecha", "med": "Indicacion"})
                if "Fecha" not in df_med.columns:
                    df_med["Fecha"] = df_med.get("fecha", "S/D")
                if "Indicacion" not in df_med.columns:
                    df_med["Indicacion"] = df_med.get("med", "Sin detalle")
                df_med = df_med[["Fecha", "Indicacion", "Estado", "Profesional"]].sort_values("Fecha", ascending=False)
                limite_med = seleccionar_limite_registros(
                    "Cambios a mostrar",
                    len(df_med),
                    key=f"dash_med_limit_{mi_empresa}_{rol}",
                    default=10,
                    opciones=(5, 10, 20, 30),
                )
                mostrar_dataframe_con_scroll(df_med.head(limite_med), height=340)
            else:
                st.success("No hay suspensiones o modificaciones de medicacion registradas.")
