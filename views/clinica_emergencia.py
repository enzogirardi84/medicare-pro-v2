"""
VISTA CLINICA DE EMERGENCIA
Funciona 100% local, no depende de Supabase
Guarda datos inmediatamente en local_data.json
"""

import streamlit as st
from datetime import datetime

try:
    from core._database_supabase import supabase as _supabase
    from core.db_sql import insert_signo_vital
except ImportError:
    _supabase = None
    insert_signo_vital = None
    # log_event("emergencia", "Supabase no disponible")  # This line is commented out because log_event is not defined
    st.warning("Supabase no disponible. Guardado local.")

from core.guardado_universal import (
    guardar_signos_vitales,
    obtener_signos_vitales
)


def render(paciente_sel=None, user=None):
    """Renderiza la vista con guardado DUAL: Supabase + Local."""
    
    st.markdown("# 🏥 Signos Vitales y Evoluciones")
    
    # Obtener paciente (si no viene como parametro, usar session_state)
    if not paciente_sel:
        paciente_sel = st.session_state.get("paciente_sel", "")
    
    if not paciente_sel:
        st.error("❌ Selecciona un paciente del menú lateral primero")
        return
    
    # Extraer nombre y DNI
    paciente_nombre = paciente_sel
    paciente_id = paciente_sel
    
    if isinstance(paciente_sel, str) and " - " in paciente_sel:
        partes = paciente_sel.split(" - ")
        paciente_nombre = " - ".join(partes[:-1])
        paciente_id = partes[-1]
    
    st.info(f"👤 Paciente: **{paciente_nombre}** (DNI: {paciente_id})")
    
    # === FORMULARIO SIGNOS VITALES ===
    st.markdown("---")
    st.markdown("### ➕ Nuevo Control de Signos Vitales")
    
    with st.form("form_signos_vitales_emergencia"):
        col1, col2, col3 = st.columns(3)
        
        with col1:
            ta = st.text_input("🫀 Tensión Arterial", placeholder="120/80", key="ta_emer")
            fc = st.number_input("❤️ Frecuencia Cardiaca", 30, 220, 75, key="fc_emer")
        
        with col2:
            fr = st.number_input("🌬️ Frecuencia Respiratoria", 8, 60, 16, key="fr_emer")
            sat = st.number_input("💨 Saturación O2", 70, 100, 98, key="sat_emer")
        
        with col3:
            temp = st.number_input("🌡️ Temperatura", 34.0, 42.0, 36.5, step=0.1, key="temp_emer")
            glucemia = st.number_input("🩸 Glucemia (mg/dL)", 0, 999, 110, step=1, key="hgt_emer")
        
        observaciones = st.text_area("📝 Observaciones", key="obs_emer")
        
        submitted = st.form_submit_button(
            "💾 GUARDAR SIGNOS VITALES (LOCAL)",
            width='stretch',
            type="primary"
        )
        
        if submitted:
            ta_limpia = str(ta or "").strip()
            if ta_limpia and not (
                "/" in ta_limpia
                and len(ta_limpia.replace("/", "").replace(" ", "")) >= 4
                and all(p.isdigit() for p in ta_limpia.replace(" ", "").split("/") if p)
                and len([p for p in ta_limpia.replace(" ", "").split("/") if p]) == 2
            ):
                st.error("Formato de Tensión Arterial inválido. Use ###/### (ej: 120/80).")
            else:
                with st.spinner("Guardando..."):
                    exito, mensaje = guardar_signos_vitales(
                        paciente_id=paciente_id,
                        paciente_nombre=paciente_nombre,
                        tension_arterial=ta,
                        frecuencia_cardiaca=fc,
                        frecuencia_respiratoria=fr,
                        temperatura=temp,
                        saturacion_oxigeno=sat,
                        glucemia=int(glucemia) if glucemia is not None else None,
                        observaciones=observaciones,
                    )
                if exito:
                    from core.alert_toasts import queue_toast
                    queue_toast(f"✅ {mensaje}")
                    st.rerun()
                else:
                    st.error(f"❌ {mensaje}")
    
    # === TABLA DE SIGNOS VITALES GUARDADOS ===
    st.markdown("---")
    st.markdown("### 📊 Signos Vitales Guardados")
    
    signos = obtener_signos_vitales(paciente_id)
    
    if signos:
        st.success(f"✅ Hay {len(signos)} registros guardados localmente")
        
        # Preparar datos para tabla bonita
        tabla_datos = []
        for s in signos:
            datos = s.get('datos', {})
            tabla_datos.append({
                'Fecha': s.get('fecha', ''),
                'T.A.': datos.get('tension_arterial', ''),
                'F.C.': datos.get('frecuencia_cardiaca', ''),
                'F.R.': datos.get('frecuencia_respiratoria', ''),
                'Temp': datos.get('temperatura', ''),
                'SatO2': datos.get('saturacion_oxigeno', ''),
                'Gluc': datos.get('glucemia', ''),
                'Observaciones': datos.get('observaciones', '')
            })
        
        import pandas as pd
        df = pd.DataFrame(tabla_datos)
        
        # Tabla con formato profesional
        st.dataframe(
            df,
            width='stretch',
            hide_index=True,
            height=min(400, len(df) * 45 + 50),
            column_config={
                'Fecha': st.column_config.TextColumn('Fecha/Hora', width='medium'),
                'T.A.': st.column_config.TextColumn('Tensión Arterial', width='medium'),
                'F.C.': st.column_config.NumberColumn('Frec. Cardiaca', width='small'),
                'F.R.': st.column_config.NumberColumn('Frec. Respiratoria', width='small'),
                'Temp': st.column_config.NumberColumn('Temperatura °C', width='small', format="%.1f"),
                'SatO2': st.column_config.NumberColumn('Sat O2 %', width='small'),
                'Gluc': st.column_config.TextColumn('Glucemia', width='small'),
                'Observaciones': st.column_config.TextColumn('Observaciones', width='large')
            }
        )
        
        # Botón para descargar
        csv = df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Descargar CSV",
            data=csv,
            file_name=f"signos_vitales_{paciente_id}.csv",
            mime="text/csv",
            width='content'
        )
    else:
        st.info("📋 No hay signos vitales guardados para este paciente. Usa el formulario de arriba para agregar el primero.")
    
    # === INFO DE SEGURIDAD ===
    st.markdown("---")
    st.info("""
    💾 **Información de seguridad:**
    - Los datos se guardan en `.streamlit/local_data.json` y en Supabase (nube)
    - Se crean backups automáticos por cada guardado
    - Tus datos están seguros y disponibles en cualquier momento
    """)


if __name__ == "__main__":
    render()
