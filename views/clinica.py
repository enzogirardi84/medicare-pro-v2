from datetime import datetime

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas, lista_plegable
from core.utils import ahora, mapa_detalles_pacientes, mostrar_dataframe_con_scroll, seleccionar_limite_registros


def _parse_fecha_hora(fecha_str):
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y %H:%M:%S")
    except Exception:
        try:
            return datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
        except Exception:
            return datetime.min


def _edad_desde_fnac(fnac_str):
    if not fnac_str:
        return None
    try:
        fnac = datetime.strptime(str(fnac_str).strip(), "%d/%m/%Y").date()
        hoy = ahora().date()
        años = hoy.year - fnac.year - ((hoy.month, hoy.day) < (fnac.month, fnac.day))
        return años if años >= 0 else None
    except Exception:
        return None


def render_clinica(paciente_sel, user=None):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    user = user or {}
    det = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    nombre_corto = paciente_sel.split(" (")[0]
    edad = _edad_desde_fnac(det.get("fnac", ""))

    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Clinica — Signos vitales</h2>
            <p class="mc-hero-text">Control clinico del paciente, alertas automaticas y evolucion en el tiempo. Pensado para uso rapido en domicilio o guardia.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Ultimo control</span>
                <span class="mc-chip">Tendencias</span>
                <span class="mc-chip">Alertas TA / FC / Sat / Temp</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Signos vitales", "Registra TA, FC, FR, saturacion, temperatura y HGT en cada visita."),
            ("Alertas", "Los valores fuera de rango se resaltan para actuar rapido."),
            ("Historial", "El grafico muestra la tendencia de FC en los ultimos controles."),
        ]
    )
    st.caption(
        "Abajo cargas un nuevo control; mas abajo el historial y el grafico. Las alertas se muestran al instante si TA, FC, saturacion o temperatura salen de rango."
    )

    c_inf1, c_inf2, c_inf3 = st.columns(3)
    c_inf1.metric("Paciente", nombre_corto[:28] + ("…" if len(nombre_corto) > 28 else ""))
    c_inf2.metric("Edad", f"{edad} años" if edad is not None else "S/D")
    c_inf3.metric("Obra social", (det.get("obra_social") or "S/D")[:24] or "S/D")

    alergias = str(det.get("alergias", "")).strip()
    if alergias:
        st.error(f"Alergias registradas: {alergias}")

    vits = [v for v in st.session_state.get("vitales_db", []) if v.get("paciente") == paciente_sel]

    if vits:
        vits_ordenados = sorted(vits, key=lambda x: _parse_fecha_hora(x.get("fecha", "")))
        ultimo = vits_ordenados[-1]
        st.markdown("##### Ultimo control registrado")
        r1, r2, r3 = st.columns(3)
        with r1:
            c1, c2 = st.columns(2)
            c1.metric("T.A.", ultimo.get("TA", "-"))
            c2.metric("F.C.", f"{ultimo.get('FC', '-')} lpm")
        with r2:
            c3, c4 = st.columns(2)
            c3.metric("F.R.", f"{ultimo.get('FR', '-')} rpm")
            c4.metric("SatO2", f"{ultimo.get('Sat', '-')} %")
        with r3:
            c5, c6 = st.columns(2)
            c5.metric("Temp", f"{ultimo.get('Temp', '-')} C")
            c6.metric("HGT", ultimo.get("HGT", "-"))
        if len(vits_ordenados) >= 2:
            try:
                penultimo = vits_ordenados[-2]
                delta_fc = int(ultimo.get("FC", 0)) - int(penultimo.get("FC", 0))
                st.caption(f"Tendencia FC respecto al control previo: {'↑' if delta_fc > 0 else '↓' if delta_fc < 0 else '→'} {abs(delta_fc)} lpm")
            except Exception:
                pass

        if len(vits_ordenados) >= 3:
            st.markdown("##### Evolucion reciente (F.C.)")
            df_trend = pd.DataFrame(vits_ordenados[-20:])
            df_trend["_t"] = df_trend["fecha"].apply(_parse_fecha_hora)
            df_trend = df_trend[df_trend["_t"] != datetime.min]
            if len(df_trend) >= 2:
                chart_fc = df_trend.set_index("_t")[["FC"]].rename(columns={"FC": "F.C. (lpm)"})
                st.line_chart(chart_fc, use_container_width=True)
    else:
        bloque_estado_vacio(
            "Sin signos vitales",
            "Todavía no hay controles de signos vitales para este paciente.",
            sugerencia="Completá el formulario superior y guardá para ver el historial acá.",
        )

    st.divider()
    with st.form("vitales_f", clear_on_submit=True):
        st.markdown("##### Nuevo control de signos vitales")
        col_time1, col_time2 = st.columns(2)
        fecha_toma = col_time1.date_input("Fecha", value=ahora().date(), key="fecha_vits")
        hora_toma_str = col_time2.text_input("Hora (HH:MM)", value=ahora().strftime("%H:%M"), key="hora_vits")
        ta = st.text_input("Tension arterial (TA)", "120/80")
        r_s1, r_s2, r_s3 = st.columns(3)
        fc = r_s1.number_input("F.C. (lpm)", 30, 220, 75)
        fr = r_s2.number_input("F.R. (rpm)", 8, 60, 16)
        sat = r_s3.number_input("SatO2 (%)", 70, 100, 96)
        r_s4, r_s5 = st.columns(2)
        temp = r_s4.number_input("Temperatura (C)", 34.0, 42.0, 36.5, step=0.1)
        hgt = r_s5.text_input("HGT (mg/dL)", "110")
        obs = st.text_input("Observaciones (opcional)", "", placeholder="Ej.: paciente en ayunas, edema MMII...")
        if st.form_submit_button("Guardar signos vitales", use_container_width=True, type="primary"):
            hora_limpia = hora_toma_str.strip() if ":" in hora_toma_str else ahora().strftime("%H:%M")
            fecha_str = f"{fecha_toma.strftime('%d/%m/%Y')} {hora_limpia}"
            registro = {
                "paciente": paciente_sel,
                "TA": ta,
                "FC": fc,
                "FR": fr,
                "Sat": sat,
                "Temp": temp,
                "HGT": hgt,
                "fecha": fecha_str,
            }
            if obs.strip():
                registro["observaciones"] = obs.strip()
            if user.get("nombre"):
                registro["registrado_por"] = user.get("nombre", "")
            st.session_state["vitales_db"].append(registro)
            guardar_datos()
            alerta = False
            if fc > 110 or fc < 50:
                st.error(f"ALERTA: Frecuencia cardiaca critica -> {fc} lpm")
                alerta = True
            if sat < 92:
                st.error(f"ALERTA: Desaturacion -> SatO2 {sat}%")
                alerta = True
            if temp > 38.0:
                st.warning(f"Fiebre detectada -> {temp} C")
                alerta = True
            if not alerta:
                st.success("Signos vitales guardados correctamente.")
            st.rerun()

    if vits:
        st.divider()
        col_tit, col_chk, col_btn = st.columns([3, 1.2, 1])
        col_tit.markdown("#### Historial de signos vitales")
        confirmar_borrado = col_chk.checkbox("Confirmar", key="conf_borrar_vital")
        if col_btn.button("Borrar ultimo control", use_container_width=True, disabled=not confirmar_borrado):
            st.session_state["vitales_db"].remove(vits[-1])
            guardar_datos()
            st.success("Registro eliminado.")
            st.rerun()
        limite = seleccionar_limite_registros(
            "Controles a mostrar",
            len(vits),
            key="clinica_limite_vitales",
            default=50,
            opciones=(10, 20, 50, 100, 150, 200),
        )
        df_vits = pd.DataFrame(vits[-limite:]).drop(columns=["paciente"], errors="ignore")
        df_vits["fecha_dt"] = df_vits["fecha"].apply(_parse_fecha_hora)
        df_vits = df_vits.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"])
        rename_map = {
            "fecha": "Fecha y Hora",
            "TA": "T.A.",
            "FC": "F.C.",
            "FR": "F.R.",
            "Sat": "SatO2%",
            "Temp": "Temp C",
            "HGT": "HGT",
            "observaciones": "Obs.",
            "registrado_por": "Registrado por",
        }
        df_vits = df_vits.rename(columns={k: v for k, v in rename_map.items() if k in df_vits.columns})
        with lista_plegable("Historial de signos vitales", count=len(df_vits), expanded=False, height=400):
            mostrar_dataframe_con_scroll(df_vits, height=340)
