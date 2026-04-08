from datetime import datetime

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.utils import ahora


def _parse_fecha_hora(fecha_str):
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S")
    except Exception:
        return datetime.min


def render_pediatria(paciente_sel, user):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
        return

    st.subheader("Control Pediatrico y Curvas de Crecimiento")
    det = st.session_state["detalles_pacientes_db"].get(paciente_sel, {})
    se = det.get("sexo", "F")
    f_n_str = det.get("fnac", "01/01/2000")
    f_n = pd.to_datetime(f_n_str, format="%d/%m/%Y", errors="coerce")
    if pd.isna(f_n):
        f_n = datetime(2000, 1, 1)

    ped = [x for x in st.session_state.get("pediatria_db", []) if x["paciente"] == paciente_sel]
    if ped:
        ultimo_ped = sorted(ped, key=lambda x: _parse_fecha_hora(x.get("fecha", "")), reverse=True)[0]
        st.markdown("##### Resumen Actual")
        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Peso", f"{ultimo_ped.get('peso', '-')} kg")
        c2.metric("Talla", f"{ultimo_ped.get('talla', '-')} cm")
        c3.metric("IMC", f"{ultimo_ped.get('imc', '-')}")
        c4.metric("Percentil", ultimo_ped.get("percentil_sug", "-"))

    st.divider()
    with st.form("pedia", clear_on_submit=True):
        st.markdown("##### Nuevo Control Pediatrico")
        col_time1, col_time2 = st.columns(2)
        fecha_toma = col_time1.date_input("Fecha", value=ahora().date(), key="fecha_ped")
        hora_toma_str = col_time2.text_input("Hora (HH:MM)", value=ahora().strftime("%H:%M"), key="hora_ped")
        col_a, col_b = st.columns(2)
        pes = col_a.number_input("Peso Actual (kg)", min_value=0.0, format="%.2f")
        tal = col_b.number_input("Talla Actual (cm)", min_value=0.0, format="%.2f")
        pc = col_a.number_input("Perimetro Cefalico (cm)", min_value=0.0, format="%.2f")
        desc = col_b.text_input("Descripcion / Nota (opcional)")
        if st.form_submit_button("Guardar Control", use_container_width=True, type="primary"):
            hora_limpia = hora_toma_str.strip() if ":" in hora_toma_str else ahora().strftime("%H:%M")
            fecha_str_toma = f"{fecha_toma.strftime('%d/%m/%Y')} {hora_limpia}"
            dt_toma = _parse_fecha_hora(fecha_str_toma)
            eda_meses = round((dt_toma - f_n).days / 30.4375, 1) if f_n else 0.0
            if eda_meses < 0:
                eda_meses = 0.0
            imc = round(pes / ((tal / 100) ** 2), 2) if tal > 0 else 0.0
            if se == "F":
                percentil_sug = "P3 - Bajo peso" if imc < 14 else "P50 - Normal" if imc < 18 else "P97 - Sobrepeso"
            else:
                percentil_sug = "P3 - Bajo peso" if imc < 14.5 else "P50 - Normal" if imc < 18.5 else "P97 - Sobrepeso"
            st.session_state["pediatria_db"].append({
                "paciente": paciente_sel,
                "fecha": fecha_str_toma,
                "edad_meses": eda_meses,
                "peso": pes,
                "talla": tal,
                "pc": pc,
                "imc": imc,
                "percentil_sug": percentil_sug,
                "nota": desc,
                "firma": user["nombre"],
            })
            guardar_datos()
            st.success("Guardado correctamente.")
            st.rerun()

    if ped:
        st.divider()
        if st.checkbox("Mostrar curvas de crecimiento", value=False):
            df_g = pd.DataFrame(ped)
            df_g["fecha_dt"] = df_g["fecha"].apply(_parse_fecha_hora)
            df_g = df_g.sort_values(by="fecha_dt")
            col_g1, col_g2 = st.columns(2)
            with col_g1:
                st.caption("Peso (kg)")
                st.line_chart(df_g.set_index("fecha")["peso"], use_container_width=True)
            with col_g2:
                st.caption("Talla (cm)")
                st.line_chart(df_g.set_index("fecha")["talla"], use_container_width=True)
        st.divider()
        col_tit, col_btn = st.columns([3, 1])
        col_tit.markdown("#### Historial")
        if col_btn.button("Borrar ultimo", use_container_width=True):
            if st.checkbox("Confirmar borrado", key="conf_del_ped"):
                st.session_state["pediatria_db"].remove(ped[-1])
                guardar_datos()
                st.rerun()
        max_controles = min(200, len(ped))
        if max_controles <= 10:
            limite = max_controles
            st.caption(f"Mostrando {limite} control(es) pediatricos.")
        else:
            limite = st.slider("Controles pediatricos a mostrar", min_value=10, max_value=max_controles, value=min(50, len(ped)), step=10)
        with st.container(height=360):
            df_ped = pd.DataFrame(ped[-limite:]).drop(columns=["paciente"], errors='ignore')
            df_ped["fecha_dt"] = df_ped["fecha"].apply(_parse_fecha_hora)
            df_ped = df_ped.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"])
            st.dataframe(df_ped, use_container_width=True, hide_index=True)
