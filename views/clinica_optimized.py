"""
Vista de Clínica OPTIMIZADA
- Guarda directamente en Supabase (nube)
- No ocupa RAM (lazy loading)
- Paginación para historial
- Manejo robusto de errores
"""

from __future__ import annotations

import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import streamlit as st

from core.ui_professional import card, badge, alert
from core.supabase_storage import (
    guardar_signos_vitales_seguro,
    obtener_signos_vitales_paciente,
    get_supabase_storage
)
from core.app_logging import log_event


def _get_paciente_activo() -> tuple[str, str]:
    """Obtiene el paciente activo del session_state."""
    paciente_sel = st.session_state.get("paciente_sel", "")
    
    # Intentar extraer ID/DNI del paciente
    paciente_id = None
    if isinstance(paciente_sel, str) and " - " in paciente_sel:
        # Formato: "Nombre - DNI"
        partes = paciente_sel.split(" - ")
        if len(partes) >= 2:
            paciente_id = partes[-1]  # El DNI al final
    
    return paciente_sel, paciente_id or paciente_sel


def _render_formulario_signos_vitales(paciente_id: str, paciente_nombre: str):
    """Renderiza el formulario de signos vitales optimizado."""
    
    st.markdown("#### Nuevo control de signos vitales")
    
    with st.form("form_signos_vitales", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            fecha = st.date_input(
                "Fecha",
                value=datetime.now().date(),
                key="sv_fecha"
            )
            hora = st.text_input(
                "Hora (HH:MM)",
                value=datetime.now().strftime("%H:%M"),
                key="sv_hora"
            )
            
        with col2:
            ta = st.text_input("Tension Arterial", "120/80", key="sv_ta")
            obs = st.text_input("Observaciones", "", key="sv_obs")
        
        # Fila de valores numéricos
        col3, col4, col5, col6, col7 = st.columns(5)
        
        with col3:
            fc = st.number_input("F.C.", 30, 220, 75, key="sv_fc")
        with col4:
            fr = st.number_input("F.R.", 8, 60, 16, key="sv_fr")
        with col5:
            sat = st.number_input("SatO2%", 70, 100, 96, key="sv_sat")
        with col6:
            temp = st.number_input("Temp °C", 34.0, 42.0, 36.5, step=0.1, key="sv_temp")
        with col7:
            hgt = st.text_input("HGT", "110", key="sv_hgt")
        
        # Botón de guardar
        submitted = st.form_submit_button(
            "Guardar Signos Vitales",
            use_container_width=True,
            type="primary"
        )
        
        if submitted:
            # Validaciones
            if not ta or "/" not in ta:
                st.error("Tension arterial debe tener formato 'sistolica/diastolica'")
                return False
            
            # Guardar en Supabase
            with st.spinner("Guardando en la nube..."):
                exito, mensaje = guardar_signos_vitales_seguro(
                    paciente_id=paciente_id,
                    tension_arterial=ta,
                    frecuencia_cardiaca=int(fc),
                    frecuencia_respiratoria=int(fr),
                    temperatura=float(temp),
                    saturacion_oxigeno=int(sat),
                    glucemia=hgt,
                    observaciones=obs
                )
            
            if exito:
                # Alertas clínicas
                alertas = []
                if fc > 110 or fc < 50:
                    alertas.append(f"ALERTA: Frecuencia cardiaca critica: {fc} lpm")
                if sat < 92:
                    alertas.append(f"ALERTA: Desaturacion: {sat}%")
                if temp > 38.0:
                    alertas.append(f"ATENCION: Fiebre detectada: {temp}°C")
                
                if alertas:
                    for alerta in alertas:
                        if "ALERTA" in alerta:
                            st.error(alerta)
                        else:
                            st.warning(alerta)
                else:
                    st.success(mensaje)
                
                log_event("signos_vitales_ui", f"Guardado OK - {paciente_nombre}")
                return True
            else:
                st.error(mensaje)
                log_event("signos_vitales_ui", f"Error guardando - {mensaje}")
                return False
    
    return False


def _render_historial_paginado(paciente_id: str):
    """Renderiza historial con paginación (no ocupa RAM)."""
    
    st.markdown("---")
    st.markdown("#### Historial de Signos Vitales")
    
    # Obtener conteo total
    storage = get_supabase_storage()
    total_registros = storage.contar_signos_vitales(paciente_id)
    
    if total_registros == 0:
        st.info("No hay signos vitales registrados para este paciente")
        return
    
    # Controles de paginación
    por_pagina = st.selectbox(
        "Registros por pagina",
        options=[10, 20, 50, 100],
        index=1,
        key="sv_por_pagina"
    )
    
    total_paginas = (total_registros + por_pagina - 1) // por_pagina
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("Anterior", disabled=st.session_state.get("sv_pagina", 1) <= 1):
            st.session_state["sv_pagina"] = st.session_state.get("sv_pagina", 1) - 1
            st.rerun()
    
    with col2:
        pagina_actual = st.number_input(
            f"Pagina (de {total_paginas})",
            min_value=1,
            max_value=total_paginas,
            value=st.session_state.get("sv_pagina", 1),
            key="sv_pagina"
        )
    
    with col3:
        if st.button("Siguiente", disabled=pagina_actual >= total_paginas):
            st.session_state["sv_pagina"] = pagina_actual + 1
            st.rerun()
    
    # Obtener datos de la página actual
    with st.spinner("Cargando..."):
        signos = obtener_signos_vitales_paciente(
            paciente_id=paciente_id,
            pagina=pagina_actual,
            por_pagina=por_pagina
        )
    
    if not signos:
        st.info("No hay datos en esta pagina")
        return
    
    # Mostrar tabla
    df = pd.DataFrame(signos)
    
    # Renombrar columnas para mostrar
    columnas_mostrar = {
        "fecha_registro": "Fecha",
        "tension_arterial": "T.A.",
        "frecuencia_cardiaca": "F.C.",
        "frecuencia_respiratoria": "F.R.",
        "temperatura": "Temp",
        "saturacion_oxigeno": "SatO2%",
        "glucemia": "HGT",
        "observaciones": "Obs."
    }
    
    # Seleccionar solo columnas que existen
    columnas_existentes = [c for c in columnas_mostrar.keys() if c in df.columns]
    df_display = df[columnas_existentes].rename(columns=columnas_mostrar)
    
    st.dataframe(
        df_display,
        use_container_width=True,
        height=min(400, len(df) * 35 + 38)
    )
    
    # Info de paginación
    st.caption(f"Mostrando {len(signos)} de {total_registros} registros totales")


def render(paciente_sel=None, user=None):
    """Función principal de renderizado optimizado."""
    
    st.markdown("## Signos Vitales")
    st.caption("Control y seguimiento de signos vitales del paciente")
    
    # Obtener paciente activo
    if paciente_sel:
        # Usar paciente pasado como parámetro
        if isinstance(paciente_sel, str) and " - " in paciente_sel:
            partes = paciente_sel.split(" - ")
            paciente_nombre = " - ".join(partes[:-1])
            paciente_id = partes[-1]
        else:
            paciente_nombre = paciente_sel
            paciente_id = paciente_sel
    else:
        paciente_nombre, paciente_id = _get_paciente_activo()
    
    if not paciente_id:
        st.warning("Selecciona un paciente para ver y registrar signos vitales")
        return
    
    # Info del paciente
    st.markdown(f"**Paciente:** {paciente_nombre}")
    
    # Formulario
    guardado_ok = _render_formulario_signos_vitales(paciente_id, paciente_nombre)
    
    if guardado_ok:
        # Limpiar caché para recargar datos
        st.rerun()
    
    # Historial paginado
    _render_historial_paginado(paciente_id)


# Mantener compatibilidad con código anterior
if __name__ == "__main__":
    render()
