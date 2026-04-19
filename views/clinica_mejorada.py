"""
Vista Clínica MEJORADA - Signos Vitales Profesional
- Tabla profesional con diseño moderno
- Verificación real de guardado
- Botones mejorados y visibles
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
    paciente_nombre = paciente_sel
    
    if isinstance(paciente_sel, str) and " - " in paciente_sel:
        # Formato: "Nombre - DNI"
        partes = paciente_sel.split(" - ")
        if len(partes) >= 2:
            paciente_nombre = " - ".join(partes[:-1])  # Todo excepto el último
            paciente_id = partes[-1]  # El DNI al final
    elif isinstance(paciente_sel, dict):
        paciente_id = paciente_sel.get("dni") or paciente_sel.get("id")
        paciente_nombre = f"{paciente_sel.get('nombre', '')} {paciente_sel.get('apellido', '')}"
    
    return paciente_nombre, paciente_id or paciente_sel


def _render_tabla_signos_vitales(signos: List[Dict], paciente_nombre: str):
    """Renderiza una tabla profesional de signos vitales."""
    
    if not signos:
        st.info(f"📋 No hay signos vitales registrados para {paciente_nombre}")
        return
    
    # Convertir a DataFrame
    df = pd.DataFrame(signos)
    
    # Formatear fecha
    if 'fecha_registro' in df.columns:
        df['fecha_registro'] = pd.to_datetime(df['fecha_registro']).dt.strftime('%d/%m/%Y %H:%M')
    
    # Seleccionar y renombrar columnas
    columnas_display = {
        'fecha_registro': 'Fecha y Hora',
        'tension_arterial': 'T.A.',
        'frecuencia_cardiaca': 'F.C.',
        'frecuencia_respiratoria': 'F.R.',
        'temperatura': 'Temp °C',
        'saturacion_oxigeno': 'SatO2%',
        'glucemia': 'Glucemia',
        'observaciones': 'Observaciones'
    }
    
    # Filtrar columnas que existen
    cols_existentes = [c for c in columnas_display.keys() if c in df.columns]
    df_display = df[cols_existentes].rename(columns=columnas_display)
    
    # Estilo profesional
    st.markdown("### 📊 Historial de Signos Vitales")
    
    # Contador
    st.caption(f"Total de registros: {len(signos)}")
    
    # Tabla con estilo
    st.dataframe(
        df_display,
        use_container_width=True,
        height=min(400, len(df) * 45 + 50),
        column_config={
            'Fecha y Hora': st.column_config.TextColumn('Fecha y Hora', width='medium'),
            'T.A.': st.column_config.TextColumn('T.A.', width='small'),
            'F.C.': st.column_config.NumberColumn('F.C.', width='small'),
            'F.R.': st.column_config.NumberColumn('F.R.', width='small'),
            'Temp °C': st.column_config.NumberColumn('Temp', width='small', format="%.1f"),
            'SatO2%': st.column_config.NumberColumn('SatO2%', width='small'),
            'Glucemia': st.column_config.TextColumn('Glucemia', width='small'),
        },
        hide_index=True
    )
    
    # Alertas clínicas si hay valores críticos
    alertas = []
    for _, row in df.head(3).iterrows():  # Revisar últimos 3 registros
        if pd.notna(row.get('frecuencia_cardiaca')):
            if row['frecuencia_cardiaca'] > 110 or row['frecuencia_cardiaca'] < 50:
                alertas.append(f"⚠️ FC crítica: {row['frecuencia_cardiaca']} lpm el {row.get('fecha_registro', 'N/A')}")
        
        if pd.notna(row.get('saturacion_oxigeno')):
            if row['saturacion_oxigeno'] < 92:
                alertas.append(f"🚨 Desaturación: {row['saturacion_oxigeno']}% el {row.get('fecha_registro', 'N/A')}")
        
        if pd.notna(row.get('temperatura')):
            if row['temperatura'] > 38.0:
                alertas.append(f"🌡️ Fiebre: {row['temperatura']}°C el {row.get('fecha_registro', 'N/A')}")
    
    if alertas:
        st.markdown("---")
        st.markdown("#### 🚨 Alertas Clínicas Recientes")
        for alerta in alertas[:5]:  # Mostrar máximo 5
            st.warning(alerta)


def _render_formulario_signos_vitales(paciente_id: str, paciente_nombre: str):
    """Renderiza el formulario de signos vitales."""
    
    st.markdown("---")
    st.markdown("### ➕ Nuevo Control de Signos Vitales")
    
    with st.form("form_signos_vitales", clear_on_submit=True):
        # Fecha y hora
        col_fecha, col_hora = st.columns(2)
        with col_fecha:
            fecha = st.date_input(
                "📅 Fecha",
                value=datetime.now().date(),
                key="sv_fecha"
            )
        with col_hora:
            hora = st.time_input(
                "🕐 Hora",
                value=datetime.now().time(),
                key="sv_hora"
            )
        
        # Tensión arterial
        col_ta, col_obs = st.columns([1, 2])
        with col_ta:
            ta = st.text_input(
                "🫀 Tensión Arterial",
                placeholder="120/80",
                help="Formato: sistólica/diastólica",
                key="sv_ta"
            )
        with col_obs:
            observaciones = st.text_input(
                "📝 Observaciones",
                placeholder="Ej: Paciente en ayunas, post ejercicio...",
                key="sv_obs"
            )
        
        # Valores numéricos en 5 columnas
        st.markdown("**📊 Valores de Laboratorio**")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            fc = st.number_input(
                "❤️ FC (lpm)",
                min_value=30, max_value=220, value=75,
                help="Frecuencia Cardiaca",
                key="sv_fc"
            )
        with col2:
            fr = st.number_input(
                "🌬️ FR (rpm)",
                min_value=8, max_value=60, value=16,
                help="Frecuencia Respiratoria",
                key="sv_fr"
            )
        with col3:
            sat = st.number_input(
                "💨 SatO₂ (%)",
                min_value=70, max_value=100, value=98,
                help="Saturación de Oxígeno",
                key="sv_sat"
            )
        with col4:
            temp = st.number_input(
                "🌡️ Temp (°C)",
                min_value=34.0, max_value=42.0, value=36.5, step=0.1,
                help="Temperatura Corporal",
                key="sv_temp"
            )
        with col5:
            glucemia = st.text_input(
                "🩸 Glucemia",
                placeholder="110",
                help="Glucemia capilar",
                key="sv_glucemia"
            )
        
        # Botón de guardar con estilo profesional
        st.markdown("---")
        col_guardar, col_spacer = st.columns([1, 3])
        with col_guardar:
            submitted = st.form_submit_button(
                "💾 GUARDAR SIGNOS VITALES",
                use_container_width=True,
                type="primary"
            )
        
        if submitted:
            # Validaciones
            errores = []
            if ta and "/" not in ta:
                errores.append("La tensión arterial debe tener formato '120/80'")
            
            if errores:
                for error in errores:
                    st.error(f"❌ {error}")
                return False
            
            # Preparar datos
            ta_sistolica = None
            ta_diastolica = None
            if ta and "/" in ta:
                try:
                    partes = ta.split("/")
                    ta_sistolica = int(partes[0])
                    ta_diastolica = int(partes[1])
                except:
                    pass
            
            # Mostrar spinner mientras guarda
            with st.spinner("🔄 Guardando en la nube..."):
                exito, mensaje = guardar_signos_vitales_seguro(
                    paciente_id=paciente_id,
                    tension_arterial=ta,
                    frecuencia_cardiaca=int(fc),
                    frecuencia_respiratoria=int(fr),
                    temperatura=float(temp),
                    saturacion_oxigeno=int(sat),
                    glucemia=glucemia,
                    observaciones=observaciones
                )
            
            if exito:
                # Verificar alertas clínicas
                alertas = []
                if fc > 110 or fc < 50:
                    alertas.append(f"⚠️ ALERTA: Frecuencia cardíaca crítica ({fc} lpm)")
                if sat < 92:
                    alertas.append(f"🚨 ALERTA: Desaturación de oxígeno ({sat}%)")
                if temp > 38.0:
                    alertas.append(f"🌡️ ATENCIÓN: Fiebre detectada ({temp}°C)")
                if ta_sistolica and (ta_sistolica > 140 or ta_sistolica < 90):
                    alertas.append(f"🫀 ATENCIÓN: Tensión arterial alterada ({ta})")
                
                if alertas:
                    st.warning("**⚠️ Se detectaron los siguientes valores anormales:**")
                    for alerta in alertas:
                        st.warning(alerta)
                
                st.success(f"✅ {mensaje}")
                st.balloons()
                
                log_event("signos_vitales_guardado", f"Paciente: {paciente_nombre}, TA: {ta}, FC: {fc}")
                return True
            else:
                st.error(f"❌ Error al guardar: {mensaje}")
                st.info("💡 Si el error persiste, verifica la conexión a internet o contacta soporte.")
                log_event("signos_vitales_error", f"Paciente: {paciente_nombre}, Error: {mensaje}")
                return False
    
    return False


def _render_verificacion_guardado(paciente_id: str):
    """Verifica en tiempo real si hay datos guardados."""
    
    st.markdown("---")
    st.markdown("### 🔍 Verificación de Datos")
    
    storage = get_supabase_storage()
    
    # Contar en Supabase
    count_supabase = storage.contar_signos_vitales(paciente_id)
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            label="☁️ En Supabase (Nube)",
            value=count_supabase,
            help="Registros guardados en la nube"
        )
    
    with col2:
        # Contar en local
        local_count = 0
        try:
            from core.database import obtener_datos
            datos_local = obtener_datos()
            if datos_local and "vitales_db" in datos_local:
                # Filtrar por paciente
                vitales_local = datos_local["vitales_db"]
                for v in vitales_local:
                    if isinstance(v, dict):
                        if v.get("paciente_id") == paciente_id or v.get("dni") == paciente_id:
                            local_count += 1
        except:
            pass
        
        st.metric(
            label="💾 En Local",
            value=local_count,
            help="Registros en archivo local (backup)"
        )
    
    with col3:
        estado = "✅ Sincronizado" if count_supabase > 0 else "⚠️ Sin datos"
        st.metric(
            label="📊 Estado",
            value=estado,
            help="Sincronización entre local y nube"
        )
    
    if count_supabase == 0:
        st.warning("⚠️ No hay signos vitales guardados para este paciente en la nube.")
        st.info("💡 Usa el formulario de arriba para registrar el primer control.")


def render(paciente_sel=None, user=None):
    """Función principal de renderizado."""
    
    # Header profesional
    st.markdown("# 🏥 Signos Vitales")
    st.caption("Control y seguimiento profesional de signos vitales del paciente")
    
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
        st.warning("⚠️ **Selecciona un paciente** desde el menú lateral para ver y registrar signos vitales.")
        
        # Instrucciones
        with st.expander("📖 ¿Cómo usar esta sección?"):
            st.markdown("""
            1. **Selecciona un paciente** del menú lateral (Buscador y selección)
            2. **Completa el formulario** con los signos vitales actuales
            3. **Haz clic en GUARDAR** para registrar en la nube
            4. **Visualiza el historial** en la tabla profesional de abajo
            """)
        return
    
    # Info del paciente en tarjeta profesional
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
        padding: 1rem;
        border-radius: 8px;
        border-left: 4px solid #2563eb;
        margin-bottom: 1rem;
    ">
        <h4 style="margin: 0; color: white;">👤 {paciente_nombre}</h4>
        <p style="margin: 0.5rem 0 0 0; color: #94a3b8; font-size: 0.875rem;">
            DNI: {paciente_id} | Empresa: {st.session_state.get('user', {}).get('empresa', 'Girardi')}
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Verificación de datos existentes
    _render_verificacion_guardado(paciente_id)
    
    # Formulario de nuevo control
    guardado_ok = _render_formulario_signos_vitales(paciente_id, paciente_nombre)
    
    # Si se guardó correctamente, recargar datos
    if guardado_ok:
        st.rerun()
    
    # Historial en tabla profesional
    with st.spinner("📊 Cargando historial..."):
        signos = obtener_signos_vitales_paciente(
            paciente_id=paciente_id,
            pagina=1,
            por_pagina=50  # Mostrar más registros
        )
    
    _render_tabla_signos_vitales(signos, paciente_nombre)
    
    # Footer
    st.markdown("---")
    st.caption("💾 Los datos se guardan automáticamente en la nube (Supabase) para máxima seguridad y disponibilidad.")


# Para compatibilidad
if __name__ == "__main__":
    render()
