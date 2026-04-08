from datetime import datetime

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.utils import ahora


def _parse_fecha_hora(fecha_str):
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
        except Exception:
            return datetime.min


def render_clinica(paciente_sel):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
        return

    st.subheader("Signos Vitales - Control Clinico")
    vits = [v for v in st.session_state.get("vitales_db", []) if v.get("paciente") == paciente_sel]

    if vits:
        vits_ordenados = sorted(vits, key=lambda x: _parse_fecha_hora(x.get("fecha", "")))
        ultimo = vits_ordenados[-1]
        st.markdown("##### Ultimo control registrado")
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        c1.metric("T.A.", ultimo.get("TA", "-"))
        c2.metric("F.C.", f"{ultimo.get('FC', '-')} lpm")
        c3.metric("F.R.", f"{ultimo.get('FR', '-')} rpm")
        c4.metric("SatO2", f"{ultimo.get('Sat', '-')} %")
        c5.metric("Temp", f"{ultimo.get('Temp', '-')} C")
        c6.metric("HGT", ultimo.get("HGT", "-"))
        if len(vits_ordenados) >= 2:
            try:
                penultimo = vits_ordenados[-2]
                delta_fc = int(ultimo.get("FC", 0)) - int(penultimo.get("FC", 0))
                st.caption(f"Tendencia FC: {'↑' if delta_fc > 0 else '↓' if delta_fc < 0 else '→'} {abs(delta_fc)} lpm")
            except Exception:
                pass
    else:
        st.info("Aun no hay signos vitales registrados para este paciente.")

    st.divider()
    with st.form("vitales_f", clear_on_submit=True):
        st.markdown("##### Nuevo Control de Signos Vitales")
        col_time1, col_time2 = st.columns(2)
        fecha_toma = col_time1.date_input("Fecha", value=ahora().date(), key="fecha_vits")
        hora_toma_str = col_time2.text_input("Hora (HH:MM)", value=ahora().strftime("%H:%M"), key="hora_vits")
        ta = st.text_input("Tension Arterial (TA)", "120/80")
        col_signos = st.columns(5)
        fc = col_signos[0].number_input("F.C. (lpm)", 30, 220, 75)
        fr = col_signos[1].number_input("F.R. (rpm)", 8, 60, 16)
        sat = col_signos[2].number_input("SatO2 (%)", 70, 100, 96)
        temp = col_signos[3].number_input("Temperatura (C)", 34.0, 42.0, 36.5, step=0.1)
        hgt = col_signos[4].text_input("HGT (mg/dL)", "110")
        if st.form_submit_button("Guardar Signos Vitales", use_container_width=True, type="primary"):
            hora_limpia = hora_toma_str.strip() if ":" in hora_toma_str else ahora().strftime("%H:%M")
            fecha_str = f"{fecha_toma.strftime('%d/%m/%Y')} {hora_limpia}"
            st.session_state["vitales_db"].append({"paciente": paciente_sel, "TA": ta, "FC": fc, "FR": fr, "Sat": sat, "Temp": temp, "HGT": hgt, "fecha": fecha_str})
            guardar_datos()
            alerta = False
            if fc > 110 or fc < 50:
                st.error(f"ALERTA: Frecuencia cardiaca critica -> {fc} lpm")
                alerta = True
            if sat < 92:
                st.error(f"ALERTA: Desaturacion -> SatO2 {sat}%")
                alerta = True
            if temp > 38.0:
                st.warning(f"Fiebre detectada -> {temp}C")
                alerta = True
            if not alerta:
                st.success("Signos vitales guardados correctamente.")
            st.rerun()

    if vits:
        st.divider()
        col_tit, col_btn = st.columns([3, 1])
        col_tit.markdown("#### Historial de Signos Vitales")
        if col_btn.button("Borrar ultimo control", use_container_width=True):
            if st.checkbox("Confirmar borrado", key="conf_borrar_vital"):
                st.session_state["vitales_db"].remove(vits[-1])
                guardar_datos()
                st.success("Registro eliminado.")
                st.rerun()
        max_controles = min(200, len(vits))
        if max_controles <= 10:
            limite = max_controles
            st.caption(f"Mostrando {limite} control(es).")
        else:
            limite = st.slider("Controles a mostrar", min_value=10, max_value=max_controles, value=min(50, len(vits)), step=10)
        with st.container(height=360):
            df_vits = pd.DataFrame(vits[-limite:]).drop(columns=["paciente"], errors='ignore')
            df_vits["fecha_dt"] = df_vits["fecha"].apply(_parse_fecha_hora)
            df_vits = df_vits.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"])
            df_vits = df_vits.rename(columns={"fecha": "Fecha y Hora", "TA": "T.A.", "FC": "F.C.", "FR": "F.R.", "Sat": "SatO2%", "Temp": "Temp C", "HGT": "HGT"})
            st.dataframe(df_vits, use_container_width=True, hide_index=True)
