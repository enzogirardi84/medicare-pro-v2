"""Asistente Clinico 360° — Vista principal del modulo.

Motor de reglas determinista que analiza datos reales del paciente y presenta
un resumen ejecutivo con alertas, metricas y tendencias.
"""

from __future__ import annotations

from datetime import datetime
from html import escape
from typing import Optional

import streamlit as st

from components.clinical_cards import (
    alerta_caja,
    card_clinica,
    inyectar_css,
    metrica_clinica,
    timeline_event,
)
from core.clinical_assistant_service import (
    compilar_dashboard_ejecutivo,
    generar_html_informe_profesional,
    generar_pdf_informe_profesional,
    recopilar_datos_paciente,
)


def render_asistente_clinico(paciente_sel: Optional[str], mi_empresa: str, user: dict, rol: Optional[str] = None):
    inyectar_css()

    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
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

    # Encabezado de semaforo
    if dashboard["semaforo"] == "rojo":
        alerta_caja(
            "Estado: CRITICO",
            f"Se detectaron {dashboard['alertas_criticas']} alertas criticas y {dashboard['alertas_warning']} advertencias. Requiere intervencion inmediata.",
            nivel="danger",
        )
    elif dashboard["semaforo"] == "amarillo":
        alerta_caja(
            "Estado: ATENCION",
            f"Se detectaron {dashboard['alertas_warning']} alertas de atencion. Revisar detalle.",
            nivel="warning",
        )
    else:
        alerta_caja("Estado: ESTABLE", "Sin alertas criticas detectadas. Continuar seguimiento.", nivel="ok")

    # Metricas principales
    c1, c2, c3, c4, c5 = st.columns(5)
    with c1:
        metrica_clinica("TA (mmHg)", dashboard["ultima_ta"])
    with c2:
        metrica_clinica("FC (lat/min)", dashboard["ultima_fc"])
    with c3:
        metrica_clinica("Temp (°C)", dashboard["ultima_temp"])
    with c4:
        metrica_clinica("Glu (mg/dL)", dashboard["ultima_glu"])
    with c5:
        metrica_clinica("SatO2 (%)", dashboard["ultima_spo2"])

    st.divider()

    # Tabs
    tab_alertas, tab_clinico, tab_farma, tab_auditoria = st.tabs([
        f"Alertas ({len(dashboard['alertas'])})",
        "Resumen Clínico",
        "Farmacología y Pendientes",
        "Auditoría y Pase de Guardia",
    ])

    with tab_alertas:
        _tab_alertas(dashboard)

    with tab_clinico:
        _tab_resumen_clinico(dashboard, datos)

    with tab_farma:
        _tab_farmacologia(dashboard, datos)

    with tab_auditoria:
        _tab_auditoria(paciente_sel, dashboard, datos)


def _tab_alertas(dashboard: dict):
    if not dashboard["alertas"]:
        alerta_caja("Sin alertas", "No se detectaron inconsistencias ni riesgos en este momento.", nivel="ok")
        return

    crit = [a for a in dashboard["alertas"] if a["nivel"] == "danger"]
    warn = [a for a in dashboard["alertas"] if a["nivel"] == "warning"]
    info = [a for a in dashboard["alertas"] if a["nivel"] == "info"]

    if crit:
        st.markdown("### Criticas")
        for a in crit:
            alerta_caja(a["titulo"], a["detalle"], nivel="danger")
    if warn:
        st.markdown("### Advertencias")
        for a in warn:
            alerta_caja(a["titulo"], a["detalle"], nivel="warning")
    if info:
        st.markdown("### Informativas")
        for a in info:
            alerta_caja(a["titulo"], a["detalle"], nivel="info")


def _tab_resumen_clinico(dashboard: dict, datos: dict):
    col1, col2 = st.columns(2)
    with col1:
        card_clinica(
            "Evoluciones Recientes",
            f"Ultimas 24h: <b>{dashboard['evoluciones_24h']}</b> registros<br>Total historico: {dashboard['total_evoluciones']}",
            badge_text="OK" if dashboard["evoluciones_24h"] > 0 else "PENDIENTE",
            badge_type="ok" if dashboard["evoluciones_24h"] > 0 else "warning",
        )
        card_clinica(
            "Cuidados de Enfermería",
            f"Ultimas 24h: <b>{dashboard['cuidados_24h']}</b> registros<br>Total historico: {dashboard['total_cuidados']}",
            badge_text="OK" if dashboard["cuidados_24h"] > 0 else "PENDIENTE",
            badge_type="ok" if dashboard["cuidados_24h"] > 0 else "warning",
        )
    with col2:
        card_clinica(
            "Estudios Complementarios",
            f"Total cargados: <b>{dashboard['total_estudios']}</b><br>Pendientes de resultado: {dashboard['estudios_pendientes']}",
            badge_text=f"{dashboard['estudios_pendientes']} pendientes" if dashboard["estudios_pendientes"] else "Al dia",
            badge_type="warning" if dashboard["estudios_pendientes"] else "ok",
        )
        card_clinica(
            "Escalas y Diagnósticos",
            f"Escalas: <b>{dashboard['total_escalas']}</b> | Diagnósticos: <b>{dashboard['total_diagnosticos']}</b>",
            badge_text="OK",
            badge_type="ok",
        )

    st.markdown("### Tendencia TA (últimos registros)")
    ta_data = dashboard.get("ta_tendencia", [])
    if ta_data:
        st.line_chart({"Sistolica": {d["fecha"]: d["sistolica"] for d in ta_data}})
    else:
        st.caption("No hay datos de presion arterial para graficar.")

    st.markdown("### Tendencia Glucemia")
    glu_data = dashboard.get("glu_tendencia", [])
    if glu_data:
        st.line_chart({"Glucemia": {d["fecha"]: d["glucemia"] for d in glu_data}})
    else:
        st.caption("No hay datos de glucemia para graficar.")


def renderizar_tarjeta_indicacion(ind: dict):
    estado = ind.get("estado_receta", ind.get("estado_clinico", "Desconocido"))
    badge_type = "ok" if "activa" in str(estado).lower() else "warning"

    med = str(ind.get("med", "Medicacion"))
    fecha = str(ind.get("fecha", "-"))
    via = escape(str(ind.get("via", "-")))
    frecuencia = escape(str(ind.get("frecuencia", "-")))

    contenido_html = f"<b>Fecha:</b> {fecha}<br><b>Via:</b> {via}<br><b>Frecuencia:</b> {frecuencia}"

    card_clinica(titulo=med, contenido=contenido_html, badge_text=estado, badge_type=badge_type)


def _tab_farmacologia(dashboard: dict, datos: dict):
    indicaciones = datos.get("indicaciones", [])
    administracion = datos.get("administracion_med", [])

    col1, col2 = st.columns(2)
    with col1:
        card_clinica(
            "Indicaciones Activas",
            f"Total activas: <b>{dashboard['indicaciones_activas']}</b>",
            badge_text="Activas",
            badge_type="info",
        )
    with col2:
        card_clinica(
            "Administraciones Pendientes",
            f"Sin registrar: <b>{dashboard['administraciones_pendientes']}</b>",
            badge_text="Pendientes" if dashboard["administraciones_pendientes"] else "Al dia",
            badge_type="warning" if dashboard["administraciones_pendientes"] else "ok",
        )

    if indicaciones:
        # Separar activas y suspendidas/historicas
        indicaciones_activas = []
        indicaciones_suspendidas = []
        for ind in indicaciones:
            estado = str(ind.get("estado_receta", ind.get("estado_clinico", "Desconocido"))).lower()
            if "activa" in estado or "vigente" in estado:
                indicaciones_activas.append(ind)
            else:
                indicaciones_suspendidas.append(ind)

        # 1. Renderizar PRIMERO las Activas
        if indicaciones_activas:
            st.markdown("### Indicaciones Activas")
            for ind in indicaciones_activas:
                renderizar_tarjeta_indicacion(ind)
        else:
            st.info("No hay indicaciones farmacologicas activas en este momento.")

        st.markdown("---")

        # 2. Renderizar DESPUES las Suspendidas / Historicas
        if indicaciones_suspendidas:
            st.markdown("### Historial: Indicaciones Suspendidas")
            for ind in indicaciones_suspendidas[-15:]:
                renderizar_tarjeta_indicacion(ind)
    else:
        st.info("No hay indicaciones registradas para este paciente.")

    if administracion:
        st.markdown("### Administraciones registradas")
        for adm in administracion[-20:]:
            timeline_event(
                adm.get("fecha", "-"),
                adm.get("med", "Administracion"),
                f"Profesional: {adm.get('profesional', '-')} | Dosis: {adm.get('dosis', '-')} | Via: {adm.get('via', '-')}",
                color_dot="#10B981",
            )
    else:
        st.caption("No hay registros de administracion medica.")


def _tab_auditoria(paciente_sel: str, dashboard: dict, datos: dict):
    col1, col2 = st.columns(2)
    with col1:
        card_clinica(
            "Balance Hídrico",
            f"Registros totales: <b>{dashboard['total_balance']}</b>",
            badge_text="OK" if dashboard["total_balance"] > 0 else "Pendiente",
            badge_type="ok" if dashboard["total_balance"] > 0 else "warning",
        )
    with col2:
        card_clinica(
            "Consumos / Insumos",
            f"Registros totales: <b>{dashboard['total_consumos']}</b>",
            badge_text="OK" if dashboard["total_consumos"] > 0 else "Pendiente",
            badge_type="ok" if dashboard["total_consumos"] > 0 else "warning",
        )

    st.markdown("### Timeline de eventos clínicos")
    eventos = []
    for ev in datos.get("evoluciones", []):
        eventos.append((ev.get("fecha", "-"), "Evolucion", ev.get("texto", ev.get("evolucion", "-")), "#3B82F6"))
    for cu in datos.get("cuidados", []):
        eventos.append((cu.get("fecha", "-"), "Cuidado", cu.get("detalle", cu.get("cuidado_tipo", "-")), "#8B5CF6"))
    for es in datos.get("estudios", []):
        eventos.append((es.get("fecha", es.get("fecha_solicitud", "-")), "Estudio", f"{es.get('tipo', 'Estudio')}: {es.get('nombre', es.get('detalle', '-'))}", "#F59E0B"))
    for em in datos.get("emergencias", []):
        eventos.append((em.get("fecha", "-"), "Emergencia", em.get("motivo", em.get("tipo", "-")), "#EF4444"))

    # Ordenar por fecha aproximada (descendente)
    from core.clinical_assistant_service import _parse_fecha
    eventos.sort(key=lambda x: _parse_fecha(str(x[0])) or datetime.min, reverse=True)
    for fecha, titulo, detalle, color in eventos[:30]:
        timeline_event(fecha, titulo, detalle, color_dot=color)

    st.divider()
    st.markdown("### Pase de Guardia / Auditoria")

    html_informe = generar_html_informe_profesional(paciente_sel, datos, dashboard)

    # Vista previa del informe profesional sin scroll interno.
    if hasattr(st, "html"):
        st.html(html_informe)
    else:
        st.components.v1.html(html_informe, height=1200, scrolling=False)

    # Botones de descarga: PDF profesional (principal) y HTML (alternativa)
    pdf_bytes = generar_pdf_informe_profesional(paciente_sel, datos, dashboard)
    col_d1, col_d2 = st.columns(2)
    with col_d1:
        st.download_button(
            label="Descargar informe PDF",
            data=pdf_bytes,
            file_name=f"pase_guardia_{paciente_sel.replace(' ', '_').replace('/', '-')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
    with col_d2:
        st.download_button(
            label="Descargar informe HTML",
            data=html_informe.encode("utf-8"),
            file_name=f"pase_guardia_{paciente_sel.replace(' ', '_').replace('/', '-')}.html",
            mime="text/html",
            use_container_width=True,
        )
