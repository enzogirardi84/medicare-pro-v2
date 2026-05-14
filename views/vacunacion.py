"""Vacunacion - Calendario, registro y control de dosis."""
from __future__ import annotations

from datetime import datetime, timedelta

import streamlit as st

from core.alert_toasts import queue_toast
from core.app_logging import log_event
from core.database import guardar_datos
from core.utils import ahora
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio

VACUNAS_CALENDARIO = [
    "BCG", "Hepatitis B",
    "Pentavalente (DTP-Hib-HepB)", "IPV (Salk) - Antipolio",
    "Neumococo conjugada", "Rotavirus",
    "Triple viral (SPR)", "Varicela",
    "Fiebre amarilla", "Antigripal",
    "COVID-19", "Doble adultos (dT)",
    "Triple bacteriana acelular (dTpa)", "VPH",
    "Hepatitis A", "Meningococo",
    "Antiamarilica", "Fiebre tifoidea",
    "-- Otra (especificar manualmente) --",
]

DOSIS_OPCIONES = [
    "Unica", "1ra dosis", "2da dosis", "3ra dosis",
    "Refuerzo 1", "Refuerzo 2", "Refuerzo 3",
    "Dosis unica anual", "Dosis pediatrica",
]

# Intervalos estandar entre dosis (en dias) por vacuna
_INTERVALOS = {
    "Hepatitis B": [0, 30, 180],
    "Pentavalente (DTP-Hib-HepB)": [60, 60, 60],
    "IPV (Salk) - Antipolio": [60, 60, 60],
    "Neumococo conjugada": [60, 60],
    "Rotavirus": [60, 60],
    "Triple viral (SPR)": [365, 365],
    "COVID-19": [21, 180],
}


def render_vacunacion(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Vacunacion</h2>
            <p class="mc-hero-text">Calendario, control de dosis y registro de vacunas aplicadas.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Registrar dosis</span>
                <span class="mc-chip">Esquema completo</span>
                <span class="mc-chip">Proximas dosis</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if "vacunacion_db" not in st.session_state:
        st.session_state["vacunacion_db"] = []
    vac_db = st.session_state["vacunacion_db"]
    vac_paciente = [r for r in vac_db if r.get("paciente") == paciente_sel]

    tabs = st.tabs(["Registrar dosis", "Esquema de vacunacion", "Proximas dosis"])

    # ============ TAB: REGISTRAR ============
    with tabs[0]:
        with st.form("vac_form", clear_on_submit=True):
            st.markdown("##### Datos de la dosis")
            c1, c2 = st.columns(2)
            vacuna = c1.selectbox("Vacuna", VACUNAS_CALENDARIO)
            vacuna_manual = c1.text_input("Nombre de la vacuna (si seleccionaste 'Otra')", placeholder="Ej: Vacuna experimental X") if vacuna == "-- Otra (especificar manualmente) --" else ""
            dosis = c2.selectbox("Dosis", DOSIS_OPCIONES)

            c3, c4 = st.columns(2)
            fecha_aplicacion = c3.date_input("Fecha de aplicacion", value=ahora().date())
            edad_paciente = c4.text_input("Edad del paciente al aplicar", placeholder="Ej: 2 meses, 5 anios...")

            c5, c6 = st.columns(2)
            lote = c5.text_input("Numero de lote")
            laboratorio = c6.text_input("Laboratorio / Marca", placeholder="Ej: Pfizer, Sinopharm, MSD...")

            aplicador = st.text_input("Aplicador / Profesional", value=user.get("nombre", ""))
            observaciones = st.text_area("Observaciones", placeholder="Reacciones adversas, contraindicaciones, etc...")

            if st.form_submit_button("Guardar dosis", width="stretch", type="primary"):
                nombre_final = vacuna_manual.strip() if vacuna == "-- Otra (especificar manualmente) --" else vacuna
                if not nombre_final:
                    st.error("Debe especificar la vacuna.")
                elif not lote.strip():
                    st.error("El numero de lote es obligatorio.")
                elif not aplicador.strip():
                    st.error("El nombre del aplicador es obligatorio.")
                else:
                    registro = {
                        "paciente": paciente_sel,
                        "vacuna": nombre_final,
                        "dosis": dosis,
                        "fecha_aplicacion": fecha_aplicacion.strftime("%d/%m/%Y"),
                        "edad_aplicacion": edad_paciente.strip(),
                        "lote": lote.strip(),
                        "laboratorio": laboratorio.strip(),
                        "aplicador": aplicador.strip(),
                        "observaciones": observaciones.strip(),
                        "empresa": mi_empresa,
                        "fecha_registro": ahora().isoformat(),
                    }
                    vac_db.append(registro)
                    guardar_datos(spinner=True)
                    queue_toast(f"{vacuna} - {dosis} registrada.")
                    log_event("vac_guardar", f"{vacuna} {dosis} - {paciente_sel}")
                    st.rerun()

    # ============ TAB: ESQUEMA ============
    with tabs[1]:
        if vac_paciente:
            st.caption(f"Esquema de vacunacion de **{paciente_sel}** — {len(vac_paciente)} dosis registradas")

            # Agrupar por vacuna
            por_vacuna = {}
            for r in vac_paciente:
                v = r["vacuna"]
                if v not in por_vacuna:
                    por_vacuna[v] = []
                por_vacuna[v].append(r)

            for vacuna, dosis_list in sorted(por_vacuna.items()):
                with st.container(border=True):
                    total_necesarias = 0
                    for v, intervalos in _INTERVALOS.items():
                        if v.lower() in vacuna.lower():
                            total_necesarias = len(intervalos) + 1
                            break
                    completas = len(dosis_list)
                    dosis_ordenadas = sorted(dosis_list, key=lambda x: x.get("fecha_aplicacion", ""), reverse=True)
                    ultima = dosis_ordenadas[0] if dosis_ordenadas else {}

                    cols = st.columns([2, 1, 1, 1])
                    cols[0].markdown(f"**{vacuna}**")
                    cols[1].markdown(f"{completas} dosis")

                    if total_necesarias > 0:
                        if completas >= total_necesarias:
                            cols[2].markdown("✅ **Completo**")
                        else:
                            cols[2].markdown(f"⏳ {completas}/{total_necesarias}")

                    cols[3].markdown(f"Ultima: {ultima.get('fecha_aplicacion','?')}")

                    with st.expander(f"Ver detalle ({completas} dosis)", expanded=False):
                        for d in dosis_ordenadas:
                            st.caption(
                                f"{d['dosis']} — {d['fecha_aplicacion']} | "
                                f"Lote: {d.get('lote','?')} | "
                                f"Lab: {d.get('laboratorio','?')} | "
                                f"Aplico: {d.get('aplicador','?')}"
                            )
                            if d.get("observaciones"):
                                st.caption(f"  Nota: {d['observaciones']}")
        else:
            bloque_estado_vacio(
                "Sin vacunas registradas",
                "No se encontraron dosis aplicadas para este paciente.",
                sugerencia="Registra la primera dosis en la pestana Registrar dosis.",
            )

    # ============ TAB: PROXIMAS ============
    with tabs[2]:
        if vac_paciente:
            st.caption("Proximas dosis estimadas segun calendario:")

            ultimas = {}
            for r in vac_paciente:
                v = r["vacuna"]
                if v not in ultimas or r["fecha_aplicacion"] > ultimas[v]["fecha_aplicacion"]:
                    ultimas[v] = r

            ahora_dt = ahora()
            hay_proximas = False
            for vacuna, reg in sorted(ultimas.items()):
                try:
                    fecha_ult = datetime.strptime(reg["fecha_aplicacion"], "%d/%m/%Y")
                except Exception:
                    continue

                # Calcular proxima dosis usando intervalo estandar o default 1 anio
                intervalo_dias = 365
                for v, intervalos in _INTERVALOS.items():
                    if v.lower() in vacuna.lower():
                        idx_dosis = DOSIS_OPCIONES.index(reg["dosis"]) if reg["dosis"] in DOSIS_OPCIONES else 0
                        if idx_dosis < len(intervalos):
                            intervalo_dias = intervalos[idx_dosis]
                        break

                prox = fecha_ult + timedelta(days=intervalo_dias)
                estado = "🔴 Vencida" if prox < ahora_dt else "🟡 Proxima" if prox < ahora_dt + timedelta(days=30) else "🟢 Al dia"

                if estado != "🟢 Al dia":
                    hay_proximas = True

                with st.container(border=True):
                    cols = st.columns([2, 1, 1])
                    cols[0].markdown(f"**{vacuna}**")
                    cols[1].markdown(f"Ultima: {reg['fecha_aplicacion']} ({reg['dosis']})")
                    cols[2].markdown(f"{estado}")
                    st.caption(f"Proxima estimada: {prox.strftime('%d/%m/%Y')} ({intervalo_dias} dias de intervalo)")

            if not hay_proximas:
                st.success("Todas las vacunas estan al dia segun el calendario.")
        else:
            bloque_estado_vacio(
                "Sin datos de vacunacion",
                "No hay dosis registradas para estimar proximas.",
                sugerencia="Registra la primera dosis en la pestana Registrar dosis.",
            )
