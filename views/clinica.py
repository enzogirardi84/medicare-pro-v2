from datetime import datetime
from typing import List, Dict, Any

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros

# --- Constantes Clínicas (Umbrales de Alerta) ---
UMBRAL_FC_ALTA = 110
UMBRAL_FC_BAJA = 50
UMBRAL_SAT_BAJA = 92
UMBRAL_TEMP_ALTA = 38.0


def _parse_fecha_hora(fecha_str: str) -> datetime:
    """Convierte un string de fecha/hora a un objeto datetime de forma segura."""
    for formato in ("%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(fecha_str, formato)
        except ValueError:
            continue
    return datetime.min


def _render_ultimo_control(vits_ordenados: List[Dict[str, Any]]) -> None:
    """Muestra el panel superior con las métricas del último registro."""
    ultimo = vits_ordenados[-1]
    st.markdown("##### Último control registrado")
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    
    c1.metric("T.A.", ultimo.get("TA", "-"))
    c2.metric("F.C.", f"{ultimo.get('FC', '-')} lpm")
    c3.metric("F.R.", f"{ultimo.get('FR', '-')} rpm")
    c4.metric("SatO2", f"{ultimo.get('Sat', '-')} %")
    c5.metric("Temp", f"{ultimo.get('Temp', '-')} °C")
    c6.metric("HGT", ultimo.get("HGT", "-"))
    
    if len(vits_ordenados) >= 2:
        penultimo = vits_ordenados[-2]
        try:
            delta_fc = int(ultimo.get("FC", 0)) - int(penultimo.get("FC", 0))
            tendencia = "↑" if delta_fc > 0 else "↓" if delta_fc < 0 else "→"
            st.caption(f"Tendencia FC: {tendencia} {abs(delta_fc)} lpm respecto al control anterior")
        except ValueError:
            pass


def _procesar_alertas(fc: int, sat: int, temp: float) -> bool:
    """Evalúa los signos y lanza toasts persistentes si hay anomalías."""
    alerta = False
    if fc > UMBRAL_FC_ALTA or fc < UMBRAL_FC_BAJA:
        st.toast(f"ALERTA: Frecuencia cardíaca crítica -> {fc} lpm", icon="🚨")
        alerta = True
    if sat < UMBRAL_SAT_BAJA:
        st.toast(f"ALERTA: Desaturación -> SatO2 {sat}%", icon="🫁")
        alerta = True
    if temp > UMBRAL_TEMP_ALTA:
        st.toast(f"Fiebre detectada -> {temp} °C", icon="🌡️")
        alerta = True
    return alerta


def _render_formulario_vitales(paciente_sel: str) -> None:
    """Renderiza el formulario para un nuevo control de signos vitales."""
    st.divider()
    with st.form("vitales_f", clear_on_submit=True):
        st.markdown("##### Nuevo Control de Signos Vitales")
        col_time1, col_time2 = st.columns(2)
        fecha_toma = col_time1.date_input("Fecha", value=ahora().date(), key="fecha_vits")
        hora_toma_str = col_time2.text_input("Hora (HH:MM)", value=ahora().strftime("%H:%M"), key="hora_vits")
        
        ta = st.text_input("Tensión Arterial (TA)", "120/80")
        col_signos = st.columns(5)
        fc = col_signos[0].number_input("F.C. (lpm)", 30, 220, 75)
        fr = col_signos[1].number_input("F.R. (rpm)", 8, 60, 16)
        sat = col_signos[2].number_input("SatO2 (%)", 70, 100, 96)
        temp = col_signos[3].number_input("Temperatura (°C)", 34.0, 42.0, 36.5, step=0.1)
        hgt = col_signos[4].text_input("HGT (mg/dL)", "110")
        
        if st.form_submit_button("Guardar Signos Vitales", use_container_width=True, type="primary"):
            hora_limpia = hora_toma_str.strip() if ":" in hora_toma_str else ahora().strftime("%H:%M")
            fecha_str = f"{fecha_toma.strftime('%d/%m/%Y')} {hora_limpia}"
            
            st.session_state["vitales_db"].append({
                "paciente": paciente_sel, 
                "TA": ta, "FC": fc, "FR": fr, "Sat": sat, "Temp": temp, "HGT": hgt, 
                "fecha": fecha_str
            })
            guardar_datos()
            
            alerta_lanzada = _procesar_alertas(fc, sat, temp)
            if not alerta_lanzada:
                st.toast("Signos vitales guardados correctamente.", icon="✅")
                
            st.rerun()


def _render_historial(vits: List[Dict[str, Any]]) -> None:
    """Renderiza la tabla histórica y la acción de borrado."""
    st.divider()
    col_tit, col_btn = st.columns([3, 1])
    col_tit.markdown("#### Historial de Signos Vitales")
    
    # Lógica corregida para borrar en Streamlit
    with col_btn:
        confirmar = st.checkbox("Habilitar borrado", key="conf_borrar_vital")
        if st.button("Borrar último control", use_container_width=True, disabled=not confirmar):
            st.session_state["vitales_db"].remove(vits[-1])
            guardar_datos()
            st.toast("Registro eliminado.", icon="🗑️")
            st.rerun()

    limite = seleccionar_limite_registros(
        "Controles a mostrar",
        len(vits),
        key="clinica_limite_vitales",
        default=50,
        opciones=(10, 20, 50, 100, 150, 200),
    )
    
    df_vits = pd.DataFrame(vits[-limite:]).drop(columns=["paciente"], errors='ignore')
    df_vits["fecha_dt"] = df_vits["fecha"].apply(_parse_fecha_hora)
    df_vits = df_vits.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"])
    df_vits = df_vits.rename(columns={
        "fecha": "Fecha y Hora", "TA": "T.A.", "FC": "F.C.", 
        "FR": "F.R.", "Sat": "SatO2%", "Temp": "Temp °C", "HGT": "HGT"
    })
    
    mostrar_dataframe_con_scroll(df_vits, height=360)


# --- Función Principal ---
def render_clinica(paciente_sel: str) -> None:
    if not paciente_sel:
        st.info("Selecciona un paciente en el menú lateral.")
        return

    st.subheader("Signos Vitales - Control Clínico")
    vits = [v for v in st.session_state.get("vitales_db", []) if v.get("paciente") == paciente_sel]

    if vits:
        vits_ordenados = sorted(vits, key=lambda x: _parse_fecha_hora(x.get("fecha", "")))
        _render_ultimo_control(vits_ordenados)
    else:
        st.info("Aún no hay signos vitales registrados para este paciente.")

    _render_formulario_vitales(paciente_sel)

    if vits:
        _render_historial(vits)
