"""Portal del Paciente - Autogestion, turnos, vacunas, documentos firmados."""
from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st

from core.utils import mapa_detalles_pacientes
from core.view_helpers import aviso_sin_paciente


def render_portal_paciente(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Portal del Paciente</h2>
            <p class="mc-hero-text">Turnos, vacunas, documentos firmados y resumen para descargar. Informacion que el paciente puede ver.</p>
        </div>
    """, unsafe_allow_html=True)

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    partes = paciente_sel.split(" - ", 1)
    nombre = partes[0] if partes else paciente_sel
    dni = partes[1] if len(partes) > 1 else (detalles.get("dni") or "S/D")

    # ============ DATOS BASICOS ============
    with st.container(border=True):
        cols = st.columns(3)
        cols[0].markdown(f"**{nombre}**")
        cols[1].markdown(f"DNI: {dni}")
        cols[2].markdown(f"OS: {detalles.get('obra_social', 'S/D')}")
        if detalles.get("alergias"):
            st.error(f"Alergias: {detalles['alergias']}")

    # ============ PROXIMOS TURNOS ============
    st.markdown("### Proximos turnos")
    ahora_dt = datetime.now()
    turnos = st.session_state.get("agenda_db", [])
    turnos_pac = []
    for t in turnos:
        if t.get("paciente") != paciente_sel:
            continue
        try:
            fecha = t.get("fecha") or t.get("fecha_hora") or ""
            turnos_pac.append((fecha, t))
        except Exception:
            continue
    turnos_pac.sort(key=lambda x: x[0] or "", reverse=True)

    if turnos_pac:
        for _, t in turnos_pac[:5]:
            with st.container(border=True):
                st.markdown(f"**{t.get('fecha', t.get('fecha_hora', '?'))}** — {t.get('profesional', t.get('tipo', '?'))}")
                st.caption(f"Estado: {t.get('estado', 'Pendiente')}")
    else:
        st.info("No hay turnos programados.")

    # ============ VACUNAS ============
    st.markdown("### Vacunas aplicadas")
    vacs = st.session_state.get("vacunacion_db", [])
    vacs_pac = [v for v in vacs if v.get("paciente") == paciente_sel]
    if vacs_pac:
        ultimas = {}
        for v in vacs_pac:
            vac = v["vacuna"]
            if vac not in ultimas or (v.get("fecha_aplicacion") or "") > (ultimas[vac].get("fecha_aplicacion") or ""):
                ultimas[vac] = v
        col1, col2, col3 = st.columns(3)
        for i, (vac, reg) in enumerate(sorted(ultimas.items())):
            (col1 if i % 3 == 0 else col2 if i % 3 == 1 else col3).markdown(
                f"**{vac}**\n{reg.get('dosis','?')}\n{reg.get('fecha_aplicacion','?')}"
            )
    else:
        st.info("Sin vacunas registradas.")

    # ============ CONSENTIMIENTOS FIRMADOS ============
    st.markdown("### Documentos firmados")
    consents = st.session_state.get("consentimientos_db", [])
    cons_pac = [c for c in consents if c.get("paciente") == paciente_sel]
    if cons_pac:
        for c in reversed(cons_pac[-10:]):
            with st.container(border=True):
                st.markdown(f"**{c.get('fecha', '?')}** — {c.get('profesional', 'S/D')}")
                st.caption(c.get("observaciones", "")[:150])
    else:
        st.info("Sin documentos firmados.")

    # ============ ALERTAS Y RECOMENDACIONES ============
    st.markdown("### Alertas y recomendaciones")
    alertas = []
    if detalles.get("alergias"):
        alertas.append(f"Tiene alergias registradas: {detalles['alergias']}")
    if detalles.get("patologias"):
        alertas.append(f"Patologias: {detalles['patologias']}")
    vacs_prox = [v for v in st.session_state.get("vacunacion_db", []) if v.get("paciente") == paciente_sel]
    if not vacs_prox:
        alertas.append("Calendario de vacunacion incompleto.")
    if alertas:
        for a in alertas:
            st.warning(a)
    else:
        st.success("No hay alertas pendientes.")

    # ============ RESUMEN IMPRIMIBLE ============
    with st.expander("Resumen para imprimir / compartir", expanded=False):
        partes = paciente_sel.split(" - ", 1)
        nom = partes[0]
        doc_dni = partes[1] if len(partes) > 1 else ""
        st.markdown(f"""
**RESUMEN DEL PACIENTE**
Paciente: {nom}
DNI: {doc_dni}
Obra social: {detalles.get('obra_social', 'S/D')}
Fecha: {datetime.now().strftime('%d/%m/%Y %H:%M')}

**Alergias:** {detalles.get('alergias', 'No registra')}
**Patologias:** {detalles.get('patologias', 'No registra')}

Ultimos turnos: {len(turnos_pac[:5])} registrados
Vacunas aplicadas: {len(vacs_pac)} dosis
Documentos firmados: {len(cons_pac)} registros
        """)
        if st.button("Generar resumen PDF", key="pdf_resumen"):
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Helvetica", "B", 14)
            pdf.cell(0, 10, f"Resumen - {nom}", align="C")
            pdf.ln(10)
            pdf.set_font("Helvetica", "", 10)
            pdf.cell(0, 6, f"DNI: {doc_dni} | OS: {detalles.get('obra_social', 'S/D')}")
            pdf.ln(6)
            if detalles.get("alergias"):
                pdf.set_text_color(200, 0, 0)
                pdf.cell(0, 6, f"Alergias: {detalles['alergias']}")
                pdf.set_text_color(0, 0, 0)
                pdf.ln(6)
            pdf.cell(0, 6, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}")
            raw = pdf.output(dest="S")
            pdf_bytes = raw.encode("latin-1", errors="replace") if isinstance(raw, str) else bytes(raw)
            st.download_button("Descargar PDF", pdf_bytes, f"resumen_{dni}_{datetime.now().strftime('%Y%m%d')}.pdf", "application/pdf")

    st.caption(f"Documento generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Medicare Pro")
