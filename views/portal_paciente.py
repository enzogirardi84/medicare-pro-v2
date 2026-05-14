"""Portal del Paciente - Vista resumen para compartir con el paciente."""
from __future__ import annotations

from datetime import datetime

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
            <p class="mc-hero-text">Resumen completo del paciente para compartir: datos personales, evoluciones, indicaciones y estudios.</p>
        </div>
    """, unsafe_allow_html=True)

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    partes = paciente_sel.split(" - ", 1)
    nombre = partes[0] if partes else paciente_sel
    dni = partes[1] if len(partes) > 1 else detalles.get("dni", "S/D")

    # ============ DATOS DEL PACIENTE ============
    with st.container(border=True):
        st.markdown(f"### {nombre}")
        c1, c2, c3 = st.columns(3)
        c1.metric("DNI", dni)
        c2.metric("Obra social", detalles.get("obra_social", "Sin datos"))
        c3.metric("Estado", detalles.get("estado", "Activo"))

        if detalles.get("telefono"):
            st.caption(f"Telefono: {detalles['telefono']}")
        if detalles.get("direccion"):
            st.caption(f"Direccion: {detalles['direccion']}")

        if detalles.get("alergias"):
            st.error(f"Alergias: {detalles['alergias']}", icon="🚨")

    # ============ INDICACIONES ACTIVAS ============
    st.markdown("### Indicaciones activas")
    indicaciones = [r for r in st.session_state.get("indicaciones_db", [])
                    if r.get("paciente") == paciente_sel
                    and str(r.get("estado_receta", "Activa")).strip().lower() not in ("suspendida", "cancelada")]
    if indicaciones:
        for ind in indicaciones[-10:]:
            with st.container(border=True):
                st.markdown(f"**{ind.get('med', ind.get('medicacion', '?'))}**")
                st.caption(f"{ind.get('dosis', '')} {ind.get('frecuencia', '')} {ind.get('via', '')} | {ind.get('fecha', '')}")
    else:
        st.info("Sin indicaciones activas.")

    # ============ EVOLUCIONES ============
    st.markdown("### Ultimas evoluciones")
    evols = [r for r in st.session_state.get("evoluciones_db", []) if r.get("paciente") == paciente_sel]
    if evols:
        for ev in evols[-5:]:
            with st.container(border=True):
                nota = str(ev.get("nota", ev.get("evolucion", "")) or "")[:300]
                st.markdown(f"**{ev.get('fecha', ev.get('fecha_evolucion', '?'))}** — {ev.get('firma', ev.get('profesional', '?'))}")
                if nota:
                    st.caption(nota[:200] + ("..." if len(nota) > 200 else ""))
    else:
        st.info("Sin evoluciones registradas.")

    # ============ ESTUDIOS ============
    st.markdown("### Estudios")
    estudios = [r for r in st.session_state.get("estudios_db", []) if r.get("paciente") == paciente_sel]
    if estudios:
        for est in estudios[-5:]:
            with st.container(border=True):
                st.markdown(f"**{est.get('tipo', est.get('estudio', '?'))}** — {est.get('fecha', '?')}")
                if est.get("resultado", est.get("observaciones", "")):
                    st.caption(str(est.get("resultado", est.get("observaciones", "")))[:150])
    else:
        st.info("Sin estudios registrados.")

    # ============ PROXIMOS TURNOS ============
    st.markdown("### Proximos turnos")
    turnos = [r for r in st.session_state.get("agenda_db", [])
              if r.get("paciente") == paciente_sel
              and r.get("estado", "").lower() in ("pendiente", "programado")]
    if turnos:
        for t in turnos[:5]:
            with st.container(border=True):
                st.markdown(f"**{t.get('fecha', t.get('fecha_hora', '?'))}** — {t.get('profesional', t.get('tipo', '?'))}")
    else:
        st.info("Sin turnos programados.")

    st.caption(f"Documento generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Medicare Pro")
