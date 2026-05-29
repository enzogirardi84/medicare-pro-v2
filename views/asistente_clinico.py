"""Asistente Clinico 360° — Vista principal del modulo.

Motor de reglas determinista que analiza datos reales del paciente y presenta
un resumen ejecutivo con alertas, metricas y tendencias.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime
from html import escape
from typing import Optional

import streamlit as st

from components.clinical_cards import (
    _html_alerta_caja,
    _html_card_clinica,
    _html_timeline_event,
    alerta_caja,
    card_clinica,
    inyectar_css,
    metrica_clinica,
)
from core.clinical_assistant_service import (
    compilar_dashboard_ejecutivo,
    generar_html_informe_profesional,
    generar_pdf_informe_profesional,
    recopilar_datos_paciente,
)


def _inyectar_css_asistente_mobile() -> None:
    """Ajustes propios del Asistente Clínico para teléfono.

    Streamlit tabs se cortan en iPhone cuando hay 4 pestañas largas. Por eso
    esta vista usa un selector vertical/segmentado en lugar de tabs nativos.
    """
    st.markdown(
        """
        <style>
        @media (max-width: 768px) {
            div[data-testid="stHorizontalBlock"] { gap: .55rem !important; }
            .mc-assistant-nav-title {
                font-size: .82rem !important;
                color: #94a3b8 !important;
                margin: .2rem 0 .35rem 0 !important;
            }
            div[data-testid="stRadio"] label,
            div[data-testid="stRadio"] p {
                font-size: .92rem !important;
                line-height: 1.25 !important;
            }
            div[data-testid="stRadio"] [role="radiogroup"] {
                gap: .45rem !important;
            }
            div[data-testid="stRadio"] [role="radio"] {
                border: 1px solid rgba(148,163,184,.25) !important;
                border-radius: 12px !important;
                padding: .55rem .7rem !important;
                background: rgba(15,23,42,.35) !important;
            }
            .card-text { overflow-wrap: anywhere !important; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def _render_selector_secciones(dashboard: dict) -> str:
    opciones = [
        f"Alertas ({len(dashboard['alertas'])})",
        "Resumen clínico",
        "Farmacología y pendientes",
        "Auditoría y pase de guardia",
    ]
    st.markdown("<div class='mc-assistant-nav-title'>Secciones del asistente</div>", unsafe_allow_html=True)
    return st.radio(
        "Secciones del asistente",
        opciones,
        index=0,
        horizontal=False,
        label_visibility="collapsed",
        key="mc_asistente_clinico_seccion",
    )


def render_asistente_clinico(paciente_sel: Optional[str], mi_empresa: str, user: dict, rol: Optional[str] = None):
    from core.ui_liviano import headers_sugieren_equipo_liviano
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    inyectar_css()
    _inyectar_css_asistente_mobile()

    if not paciente_sel:
        st.info("Seleccioná un paciente en el menú lateral.")
        return

    nombre_usuario = escape(str(user.get("nombre", "Profesional")))
    paciente_visible = escape(str(paciente_sel))
    st.markdown("<div class='main-title'>Asistente Clínico 360°</div>", unsafe_allow_html=True)
    st.markdown(
        f"<div class='subtitle'>Paciente: <b>{paciente_visible}</b> | Usuario: <b>{nombre_usuario}</b></div>",
        unsafe_allow_html=True,
    )

    with st.spinner("Analizando datos del paciente..."):
        datos = recopilar_datos_paciente(paciente_sel)
        dashboard = compilar_dashboard_ejecutivo(datos)

    if dashboard["semaforo"] == "rojo":
        alerta_caja(
            "Estado: CRÍTICO",
            f"Se detectaron {dashboard['alertas_criticas']} alertas críticas y {dashboard['alertas_warning']} advertencias. Requiere intervención inmediata.",
            nivel="danger",
        )
    elif dashboard["semaforo"] == "amarillo":
        alerta_caja(
            "Estado: ATENCIÓN",
            f"Se detectaron {dashboard['alertas_warning']} alertas de atención. Revisar detalle.",
            nivel="warning",
        )
    else:
        alerta_caja("Estado: ESTABLE", "Sin alertas críticas detectadas. Continuar seguimiento.", nivel="ok")

    edad = dashboard.get("edad_paciente")
    edad_str = escape(f"{edad} años") if edad else "S/D"
    diag_str = escape("; ".join(dashboard.get("diagnosticos_list", [])) or "Sin diagnóstico registrado")
    ult_act = dashboard.get("ultima_actualizacion_hs")
    if ult_act is not None:
        if ult_act < 1:
            act_str = "< 1h"
        elif ult_act < 24:
            act_str = f"{int(ult_act)}h"
        else:
            act_str = f"{int(ult_act/24)}d"
    else:
        act_str = "Sin datos"
    act_str = escape(act_str)

    if es_movil:
        c_info1 = st.container()
        c_info2 = st.container()
    else:
        c_info1, c_info2 = st.columns(2)
    with c_info1:
        st.markdown(f"<div class='card-text'><strong>Edad:</strong> {edad_str} &nbsp;|&nbsp; <strong>Actualización:</strong> {act_str}</div>", unsafe_allow_html=True)
    with c_info2:
        st.markdown(f"<div class='card-text'><strong>Diagnóstico:</strong> {diag_str}</div>", unsafe_allow_html=True)

    delta_str = f"({act_str})" if ult_act is not None else None
    if es_movil:
        c1 = st.container()
        c2 = st.container()
        c3 = st.container()
    else:
        c1, c2, c3 = st.columns(3)
    with c1:
        metrica_clinica("TA (mmHg)", dashboard["ultima_ta"], delta=delta_str)
        metrica_clinica("FC (lat/min)", dashboard["ultima_fc"], delta=delta_str)
    with c2:
        metrica_clinica("Temp (°C)", dashboard["ultima_temp"], delta=delta_str)
        metrica_clinica("Glu (mg/dL)", dashboard["ultima_glu"], delta=delta_str)
    with c3:
        metrica_clinica("SatO2 (%)", dashboard["ultima_spo2"], delta=delta_str)

    st.divider()

    seccion = _render_selector_secciones(dashboard)

    if seccion.startswith("Alertas"):
        _tab_alertas(dashboard)
    elif seccion.startswith("Resumen"):
        _tab_resumen_clinico(dashboard, datos)
    elif seccion.startswith("Farmacología"):
        _tab_farmacologia(dashboard, datos)
    else:
        _tab_auditoria(paciente_sel, dashboard, datos)


SCROLL = 'style="max-height:380px;overflow-y:auto;border:1px solid #E2E8F0;border-radius:8px;padding:8px 12px;"'


def _tab_alertas(dashboard: dict):
    if not dashboard["alertas"]:
        alerta_caja("Sin alertas", "No se detectaron inconsistencias ni riesgos en este momento.", nivel="ok")
        return

    crit = [a for a in dashboard["alertas"] if a["nivel"] == "danger"]
    warn = [a for a in dashboard["alertas"] if a["nivel"] == "warning"]
    info = [a for a in dashboard["alertas"] if a["nivel"] == "info"]

    if crit:
        st.markdown("### Críticas")
        st.markdown(f'<div {SCROLL}>{"".join(_html_alerta_caja(a["titulo"], a["detalle"], nivel="danger") for a in crit)}</div>', unsafe_allow_html=True)
    if warn:
        st.markdown("### Advertencias")
        st.markdown(f'<div {SCROLL}>{"".join(_html_alerta_caja(a["titulo"], a["detalle"], nivel="warning") for a in warn)}</div>', unsafe_allow_html=True)
    if info:
        st.markdown("### Informativas")
        st.markdown(f'<div {SCROLL}>{"".join(_html_alerta_caja(a["titulo"], a["detalle"], nivel="info") for a in info)}</div>', unsafe_allow_html=True)


def _tab_resumen_clinico(dashboard: dict, datos: dict):
    from core.ui_liviano import headers_sugieren_equipo_liviano
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    if es_movil:
        col1 = st.container()
        col2 = st.container()
    else:
        col1, col2 = st.columns(2)
    with col1:
        card_clinica(
            "Evoluciones recientes",
            f"Últimas 24h: <b>{dashboard['evoluciones_24h']}</b> registros<br>Total histórico: {dashboard['total_evoluciones']}",
            badge_text="OK" if dashboard["evoluciones_24h"] > 0 else "PENDIENTE",
            badge_type="ok" if dashboard["evoluciones_24h"] > 0 else "warning",
        )
        card_clinica(
            "Cuidados de enfermería",
            f"Últimas 24h: <b>{dashboard['cuidados_24h']}</b> registros<br>Total histórico: {dashboard['total_cuidados']}",
            badge_text="OK" if dashboard["cuidados_24h"] > 0 else "PENDIENTE",
            badge_type="ok" if dashboard["cuidados_24h"] > 0 else "warning",
        )
    with col2:
        card_clinica(
            "Estudios complementarios",
            f"Total cargados: <b>{dashboard['total_estudios']}</b><br>Pendientes de resultado: {dashboard['estudios_pendientes']}",
            badge_text=f"{dashboard['estudios_pendientes']} pendientes" if dashboard["estudios_pendientes"] else "Al día",
            badge_type="warning" if dashboard["estudios_pendientes"] else "ok",
        )
        card_clinica(
            "Escalas y diagnósticos",
            f"Escalas: <b>{dashboard['total_escalas']}</b> | Diagnósticos: <b>{dashboard['total_diagnosticos']}</b>",
            badge_text="OK",
            badge_type="ok",
        )

    diag_list = dashboard.get("diagnosticos_list", [])
    if diag_list:
        st.markdown("### Diagnósticos")
        diag_html = "<br>".join(f"<span class='badge-info' style='display:inline-block;margin:2px 4px 2px 0'>{escape(d)}</span>" for d in diag_list)
        st.markdown(f"<div>{diag_html}</div>", unsafe_allow_html=True)
    else:
        st.caption("Sin diagnósticos registrados.")

    if es_movil:
        col_chart1 = st.container()
        col_chart2 = st.container()
    else:
        col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown("### Tendencia TA")
        ta_data = dashboard.get("ta_tendencia", [])
        if ta_data:
            st.line_chart({
                "Sistólica": {d["fecha"]: d["sistolica"] for d in ta_data},
                "Diastólica": {d["fecha"]: d["diastolica"] for d in ta_data},
            })
        else:
            st.caption("No hay datos de presión arterial para graficar.")
    with col_chart2:
        st.markdown("### Tendencia glucemia")
        glu_data = dashboard.get("glu_tendencia", [])
        if glu_data:
            st.line_chart({"Glucemia": {d["fecha"]: d["glucemia"] for d in glu_data}})
        else:
            st.caption("No hay datos de glucemia para graficar.")

    if es_movil:
        col_b1 = st.container()
        col_b2 = st.container()
    else:
        col_b1, col_b2 = st.columns(2)
    with col_b1:
        st.markdown("### Balance hídrico")
        bal_data = dashboard.get("balance_tendencia", [])
        if bal_data:
            st.line_chart({
                "Ingresos": {d["fecha"]: d["ingresos"] for d in bal_data},
                "Egresos": {d["fecha"]: d["egresos"] for d in bal_data},
            })
        else:
            st.caption("No hay datos de balance hídrico para graficar.")
    with col_b2:
        st.markdown("### Consumos / insumos")
        consumos = datos.get("consumos", [])
        if consumos:
            conteo = Counter(str(c.get("insumo", c.get("material", "Otro"))) for c in consumos)
            df_consumos = {"Insumo": list(conteo.keys()), "Cantidad": list(conteo.values())}
            if es_movil and len(conteo) > 25:
                st.caption(f"Mostrando 25 de {len(conteo)} registros. Usá escritorio para ver todos.")
                st.dataframe(
                    {k: v[:25] for k, v in df_consumos.items()},
                    width='stretch',
                    hide_index=True,
                )
            else:
                st.dataframe(
                    df_consumos,
                    width='stretch',
                    hide_index=True,
                )
        else:
            st.caption("No hay registros de consumos de insumos.")


def _html_tarjeta_indicacion(ind: dict) -> str:
    estado = ind.get("estado_receta", ind.get("estado_clinico", "Desconocido"))
    badge_type = "ok" if "activa" in str(estado).lower() else "warning"
    med = str(ind.get("med", "Medicación"))
    fecha = escape(str(ind.get("fecha", "-")))
    via = escape(str(ind.get("via", "-")))
    frecuencia = escape(str(ind.get("frecuencia", "-")))
    contenido_html = f"<b>Fecha:</b> {fecha}<br><b>Vía:</b> {via}<br><b>Frecuencia:</b> {frecuencia}"
    return _html_card_clinica(titulo=med, contenido=contenido_html, badge_text=estado, badge_type=badge_type)


def renderizar_tarjeta_indicacion(ind: dict):
    st.markdown(_html_tarjeta_indicacion(ind), unsafe_allow_html=True)


def _tab_farmacologia(dashboard: dict, datos: dict):
    from core.ui_liviano import headers_sugieren_equipo_liviano
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    indicaciones = datos.get("indicaciones", [])
    administracion = datos.get("administracion_med", [])

    if es_movil:
        col1 = st.container()
        col2 = st.container()
    else:
        col1, col2 = st.columns(2)
    with col1:
        card_clinica(
            "Indicaciones activas",
            f"Total activas: <b>{dashboard['indicaciones_activas']}</b>",
            badge_text="Activas",
            badge_type="info",
        )
    with col2:
        card_clinica(
            "Administraciones pendientes",
            f"Sin registrar: <b>{dashboard['administraciones_pendientes']}</b>",
            badge_text="Pendientes" if dashboard["administraciones_pendientes"] else "Al día",
            badge_type="warning" if dashboard["administraciones_pendientes"] else "ok",
        )

    if indicaciones:
        indicaciones_activas = []
        indicaciones_suspendidas = []
        for ind in indicaciones:
            estado = str(ind.get("estado_receta", ind.get("estado_clinico", "Desconocido"))).lower()
            if "activa" in estado or "vigente" in estado:
                indicaciones_activas.append(ind)
            else:
                indicaciones_suspendidas.append(ind)

        if indicaciones_activas:
            st.markdown("### Indicaciones activas")
            st.markdown(f'<div {SCROLL}>{"".join(_html_tarjeta_indicacion(ind) for ind in indicaciones_activas)}</div>', unsafe_allow_html=True)
        else:
            st.info("No hay indicaciones farmacológicas activas en este momento.")

        if indicaciones_suspendidas:
            st.markdown("### Historial: indicaciones suspendidas")
            st.markdown(f'<div {SCROLL}>{"".join(_html_tarjeta_indicacion(ind) for ind in indicaciones_suspendidas[-30:])}</div>', unsafe_allow_html=True)
    else:
        st.info("No hay indicaciones registradas para este paciente.")

    if administracion:
        st.markdown("### Administraciones registradas")
        adm_html = "".join(
            _html_timeline_event(
                adm.get("fecha", "-"),
                adm.get("med", "Administración"),
                f"Profesional: {adm.get('profesional', '-')} | Dosis: {adm.get('dosis', '-')} | Vía: {adm.get('via', '-')}",
                color_dot="#10B981",
            )
            for adm in administracion[-50:]
        )
        st.markdown(f'<div {SCROLL}>{adm_html}</div>', unsafe_allow_html=True)
    else:
        st.caption("No hay registros de administración médica.")


def _tab_auditoria(paciente_sel: str, dashboard: dict, datos: dict):
    from core.ui_liviano import headers_sugieren_equipo_liviano
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    if es_movil:
        col1 = st.container()
        col2 = st.container()
    else:
        col1, col2 = st.columns(2)
    with col1:
        card_clinica(
            "Balance hídrico",
            f"Registros totales: <b>{dashboard['total_balance']}</b>",
            badge_text="OK" if dashboard["total_balance"] > 0 else "Pendiente",
            badge_type="ok" if dashboard["total_balance"] > 0 else "warning",
        )
    with col2:
        card_clinica(
            "Consumos / insumos",
            f"Registros totales: <b>{dashboard['total_consumos']}</b>",
            badge_text="OK" if dashboard["total_consumos"] > 0 else "Pendiente",
            badge_type="ok" if dashboard["total_consumos"] > 0 else "warning",
        )

    st.markdown("### Timeline de eventos clínicos")
    eventos = []
    for ev in datos.get("evoluciones", []):
        eventos.append(("Evolución", ev.get("fecha", "-"), "Evolución", ev.get("texto", ev.get("evolucion", "-")), "#3B82F6"))
    for cu in datos.get("cuidados", []):
        eventos.append(("Cuidado", cu.get("fecha", "-"), "Cuidado", cu.get("detalle", cu.get("cuidado_tipo", "-")), "#8B5CF6"))
    for es in datos.get("estudios", []):
        eventos.append(("Estudio", es.get("fecha", es.get("fecha_solicitud", "-")), "Estudio", f"{es.get('tipo', 'Estudio')}: {es.get('nombre', es.get('detalle', '-'))}", "#F59E0B"))
    for em in datos.get("emergencias", []):
        eventos.append(("Emergencia", em.get("fecha", "-"), "Emergencia", em.get("motivo", em.get("tipo", "-")), "#EF4444"))

    tipos_disponibles = sorted(set(e[0] for e in eventos))
    filtros = {}
    if tipos_disponibles:
        st.caption("Filtrar timeline")
        for t in tipos_disponibles:
            filtros[t] = st.checkbox(t, value=True, key=f"tl_filtro_{t}")

    from core.clinical_assistant_service import _parse_fecha
    eventos_filtrados = [e for e in eventos if filtros.get(e[0], True)]
    eventos_filtrados.sort(key=lambda x: _parse_fecha(str(x[1])) or datetime.min, reverse=True)

    if eventos_filtrados:
        tl_html = "".join(_html_timeline_event(fecha, titulo, detalle, color_dot=color) for _, fecha, titulo, detalle, color in eventos_filtrados[:50])
        st.markdown(f'<div {SCROLL}>{tl_html}</div>', unsafe_allow_html=True)
    else:
        st.caption("No hay eventos que coincidan con los filtros seleccionados.")

    st.divider()
    st.markdown("### Pase de guardia / Auditoría")

    semaforo = dashboard.get("semaforo", "desconocido")
    badge_pase = {"rojo": "danger", "amarillo": "warning", "verde": "ok"}.get(semaforo, "info")
    texto_estado = {"rojo": "CRÍTICO - Requiere intervención", "amarillo": "ATENCIÓN - Monitoreo necesario", "verde": "ESTABLE"}.get(semaforo, "Desconocido")

    card_clinica(
        "Resumen del informe",
        f"<b>Estado:</b> {texto_estado}<br>"
        f"<b>Alertas:</b> {dashboard['alertas_criticas']} críticas, {dashboard['alertas_warning']} advertencias, {dashboard['alertas_info']} informativas<br>"
        f"<b>Indicaciones activas:</b> {dashboard['indicaciones_activas']} | <b>Estudios pendientes:</b> {dashboard['estudios_pendientes']}",
        badge_text=semaforo.upper(),
        badge_type=badge_pase,
    )

    html_informe = generar_html_informe_profesional(paciente_sel, datos, dashboard)

    st.caption("Vista previa del informe")
    with st.expander("Ver informe completo", expanded=False):
        st.html(html_informe)

    if es_movil:
        col_d1 = st.container()
        col_d2 = st.container()
    else:
        col_d1, col_d2 = st.columns(2)
    with col_d1:
        pdf_bytes = generar_pdf_informe_profesional(paciente_sel, datos, dashboard)
        st.download_button(
            label="Descargar PDF",
            data=pdf_bytes,
            file_name=f"pase_guardia_{paciente_sel.replace(' ', '_').replace('/', '-')}.pdf",
            mime="application/pdf",
            width='stretch',
        )
    with col_d2:
        st.download_button(
            label="Descargar HTML",
            data=html_informe.encode("utf-8"),
            file_name=f"pase_guardia_{paciente_sel.replace(' ', '_').replace('/', '-')}.html",
            mime="text/html",
            width='stretch',
        )
