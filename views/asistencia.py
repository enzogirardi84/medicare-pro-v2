import streamlit as st
import pandas as pd
from datetime import datetime
from core.utils import ahora
from core.database import guardar_datos

def render_asistencia(mi_empresa, user):
    st.subheader("⏱️ Panel de Control de Asistencias en Vivo")
    st.info("Monitoreo en tiempo real de los profesionales que se encuentran actualmente trabajando dentro del domicilio de un paciente.")
    
    hoy_str = ahora().strftime("%d/%m/%Y")
    chks_hoy = [c for c in st.session_state.get("checkin_db", []) if c.get("fecha_hora", "").startswith(hoy_str) and c.get("empresa") == mi_empresa]
    
    estado_profesionales = {}
    for c in chks_hoy:
        prof = c["profesional"]
        pac = c["paciente"]
        try:
            dt = datetime.strptime(c["fecha_hora"], "%d/%m/%Y %H:%M:%S")
        except:
            dt = datetime.strptime(c["fecha_hora"], "%d/%m/%Y %H:%M")
            
        if "LLEGADA" in c["tipo"]:
            estado_profesionales[prof] = {"estado": "En Guardia", "llegada": dt, "paciente": pac}
        elif "SALIDA" in c["tipo"]:
            estado_profesionales[prof] = {"estado": "Fuera", "llegada": None, "paciente": None}
            
    activos = {k: v for k, v in estado_profesionales.items() if v["estado"] == "En Guardia"}
    
    if activos:
        st.markdown("#### 🟢 Profesionales Actualmente en Domicilio")
        for prof, data in activos.items():
            with st.container(border=True):
                col_info, col_btn = st.columns([3, 1])
                dt_llegada = data["llegada"]
                
                duracion = ahora().replace(tzinfo=None) - dt_llegada
                horas, rem = divmod(duracion.seconds, 3600)
                minutos, _ = divmod(rem, 60)
                
                col_info.markdown(f"👤 **{prof}** está en el domicilio de **{data['paciente']}**")
                col_info.caption(f"Ingresó a las: {dt_llegada.strftime('%H:%M')} ➔ **Tiempo transcurrido: {horas}h {minutos}m**")
                
                if col_btn.button("🔴 Forzar Salida", key=f"force_out_{prof}", use_container_width=True):
                    st.session_state["checkin_db"].append({
                        "paciente": data["paciente"], 
                        "profesional": prof, 
                        "fecha_hora": ahora().strftime("%d/%m/%Y %H:%M:%S"), 
                        "tipo": f"SALIDA (Forzada por Admin: {user['nombre']})", 
                        "empresa": mi_empresa
                    })
                    guardar_datos()
                    st.success(f"Salida forzada registrada correctamente para {prof}.")
                    st.rerun()
    else:
        st.success("En este momento no hay profesionales con guardias abiertas en los domicilios.")
        
    st.divider()
    st.markdown("#### 📋 Auditoría de todos los movimientos de hoy")
    if chks_hoy:
        df_chks = pd.DataFrame(chks_hoy).drop(columns=["empresa"], errors='ignore')
        df_chks = df_chks.rename(columns={"paciente": "Paciente", "profesional": "Profesional", "fecha_hora": "Fecha y Hora", "tipo": "Acción"})
        st.dataframe(df_chks.iloc[::-1], use_container_width=True, hide_index=True)
    else:
        st.write("Sin movimientos en el día de la fecha.")
