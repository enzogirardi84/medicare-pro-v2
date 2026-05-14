"""Portal del Paciente - Vista resumen con datos reales."""
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
            <p class="mc-hero-text">Resumen completo de historia clinica para compartir con el paciente.</p>
        </div>
    """, unsafe_allow_html=True)

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    partes = paciente_sel.split(" - ", 1)
    nombre = partes[0] if partes else paciente_sel
    dni = partes[1] if len(partes) > 1 else (detalles.get("dni") or "S/D")

    # ============ DATOS DEL PACIENTE ============
    with st.container(border=True):
        st.markdown(f"### Datos del paciente")
        c1, c2 = st.columns(2)
        c1.markdown(f"**Nombre:** {nombre}")
        c2.markdown(f"**DNI:** {dni}")
        c1.markdown(f"**Obra social:** {detalles.get('obra_social', 'S/D')}")
        c2.markdown(f"**Estado:** {detalles.get('estado', 'Activo')}")
        if detalles.get("direccion"):
            st.markdown(f"**Direccion:** {detalles['direccion']}")
        if detalles.get("telefono"):
            st.markdown(f"**Telefono:** {detalles['telefono']}")
        if detalles.get("alergias"):
            st.error(f"🚨 Alergias: {detalles['alergias']}")
        if detalles.get("patologias"):
            st.warning(f"Patologias: {detalles['patologias']}")

    # ============ EVOLUCIONES ============
    st.markdown("### Evoluciones clinicas")
    evols = [r for r in st.session_state.get("evoluciones_db", []) if r.get("paciente") == paciente_sel]
    if evols:
        for ev in reversed(evols[-20:]):
            fecha = ev.get("fecha") or ev.get("fecha_evolucion") or ev.get("created_at") or "?"
            profesional = ev.get("firma") or ev.get("profesional") or ev.get("usuario") or "S/D"
            contenido = ev.get("nota") or ev.get("evolucion") or ev.get("contenido") or ev.get("descripcion") or ""
            with st.container(border=True):
                st.markdown(f"**{fecha}** — {profesional}")
                if contenido:
                    st.write(contenido[:500])
                else:
                    st.caption("(Sin detalle)")
    else:
        st.info("Sin evoluciones registradas.")

    # ============ INDICACIONES ============
    st.markdown("### Indicaciones")
    inds = [r for r in st.session_state.get("indicaciones_db", []) if r.get("paciente") == paciente_sel]
    if inds:
        for ind in reversed(inds[-20:]):
            med = ind.get("med") or ind.get("medicacion") or ind.get("descripcion") or "?"
            dosis = ind.get("dosis") or ""
            frecuencia = ind.get("frecuencia") or ""
            via = ind.get("via") or ""
            fecha = ind.get("fecha") or ind.get("fecha_indicacion") or "?"
            estado = ind.get("estado_receta") or ind.get("estado") or "Activa"
            with st.container(border=True):
                st.markdown(f"**{med}** {dosis} {frecuencia} {via}")
                st.caption(f"{fecha} | Estado: {estado}")
    else:
        st.info("Sin indicaciones registradas.")

    # ============ ESTUDIOS ============
    st.markdown("### Estudios")
    ests = [r for r in st.session_state.get("estudios_db", []) if r.get("paciente") == paciente_sel]
    if ests:
        for est in reversed(ests[-20:]):
            tipo = est.get("tipo") or est.get("estudio") or est.get("nombre") or "?"
            fecha = est.get("fecha") or est.get("fecha_realizacion") or "?"
            resultado = est.get("resultado") or est.get("observaciones") or est.get("informe") or ""
            with st.container(border=True):
                st.markdown(f"**{tipo}** — {fecha}")
                if resultado:
                    st.caption(resultado[:300])
    else:
        st.info("Sin estudios registrados.")

    st.caption(f"Documento generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | Medicare Pro")
