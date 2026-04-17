"""
HISTORIAL CLINICO COMPLETO
Muestra y guarda TODOS los datos del paciente en un solo lugar
"""

import streamlit as st
import pandas as pd
from datetime import datetime

from core.guardado_universal import (
    guardar_registro,
    obtener_historial_paciente,
    obtener_registros
)


def render(paciente_sel=None, user=None):
    """Vista de historial clínico completo."""
    
    st.markdown("# 📋 Historial Clínico Completo")
    st.caption("Todo el historial médico del paciente en un solo lugar")
    
    # Obtener paciente
    if not paciente_sel:
        paciente_sel = st.session_state.get("paciente_sel", "")
    
    if not paciente_sel:
        st.error("❌ Selecciona un paciente primero")
        return
    
    # Extraer datos del paciente
    paciente_nombre = paciente_sel
    paciente_id = paciente_sel
    
    if isinstance(paciente_sel, str) and " - " in paciente_sel:
        partes = paciente_sel.split(" - ")
        paciente_nombre = " - ".join(partes[:-1])
        paciente_id = partes[-1]
    
    # Mostrar info del paciente
    st.info(f"👤 **Paciente:** {paciente_nombre} | **DNI:** {paciente_id}")
    
    # === TABS PARA DIFERENTES SECCIONES ===
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Signos Vitales", 
        "📝 Evoluciones", 
        "💊 Recetas",
        "🔧 Materiales",
        "📚 Historial Completo"
    ])
    
    # === TAB 1: SIGNOS VITALES ===
    with tab1:
        st.markdown("### 📊 Signos Vitales")
        
        with st.form("form_signos_vitales_historial"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                ta = st.text_input("Tensión Arterial", placeholder="120/80")
                fc = st.number_input("Frec. Cardiaca", 30, 220, 75)
                fr = st.number_input("Frec. Respiratoria", 8, 60, 16)
            
            with col2:
                sat = st.number_input("Saturación O2 (%)", 70, 100, 98)
                temp = st.number_input("Temperatura (°C)", 34.0, 42.0, 36.5, step=0.1)
                glucemia = st.text_input("Glucemia", placeholder="110")
            
            with col3:
                peso = st.number_input("Peso (kg)", 0.0, 300.0, 70.0, step=0.1)
                talla = st.number_input("Talla (cm)", 0, 250, 170)
                observaciones = st.text_area("Observaciones", height=100)
            
            submitted = st.form_submit_button(
                "💾 GUARDAR SIGNOS VITALES",
                use_container_width=True,
                type="primary"
            )
            
            if submitted:
                datos = {
                    "tension_arterial": ta,
                    "frecuencia_cardiaca": fc,
                    "frecuencia_respiratoria": fr,
                    "saturacion_oxigeno": sat,
                    "temperatura": temp,
                    "glucemia": glucemia,
                    "peso": peso,
                    "talla": talla,
                    "observaciones": observaciones
                }
                
                exito, mensaje = guardar_registro(
                    tipo="signos_vitales",
                    paciente_id=paciente_id,
                    paciente_nombre=paciente_nombre,
                    datos=datos
                )
                
                if exito:
                    st.success(f"✅ {mensaje}")
                    st.balloons()
                    st.rerun()
                else:
                    st.error(f"❌ {mensaje}")
        
        # Mostrar tabla de signos vitales guardados
        signos = obtener_registros("signos_vitales", paciente_id)
        if signos:
            st.markdown("#### 📋 Signos Vitales Guardados")
            df_signos = pd.DataFrame(signos)
            st.dataframe(df_signos.tail(10), use_container_width=True, hide_index=True)
        else:
            st.info("No hay signos vitales registrados")
    
    # === TAB 2: EVOLUCIONES ===
    with tab2:
        st.markdown("### 📝 Evoluciones Clínicas")
        
        with st.form("form_evoluciones_historial"):
            evolucion = st.text_area("Evolución clínica", height=200, 
                                   placeholder="Describe la evolución del paciente...")
            indicaciones = st.text_area("Indicaciones y tratamiento", height=150,
                                      placeholder="Medicamentos, dosis, frecuencia...")
            
            submitted = st.form_submit_button(
                "💾 GUARDAR EVOLUCIÓN",
                use_container_width=True,
                type="primary"
            )
            
            if submitted:
                if not evolucion.strip():
                    st.error("❌ Debes escribir la evolución")
                else:
                    datos = {
                        "evolucion": evolucion,
                        "indicaciones": indicaciones
                    }
                    
                    exito, mensaje = guardar_registro(
                        tipo="evoluciones",
                        paciente_id=paciente_id,
                        paciente_nombre=paciente_nombre,
                        datos=datos
                    )
                    
                    if exito:
                        st.success(f"✅ {mensaje}")
                        st.rerun()
                    else:
                        st.error(f"❌ {mensaje}")
        
        # Mostrar evoluciones guardadas
        evoluciones = obtener_registros("evoluciones", paciente_id)
        if evoluciones:
            st.markdown("#### 📋 Evoluciones Guardadas")
            for evo in reversed(evoluciones[-5:]):
                with st.expander(f"📅 {evo.get('fecha', 'Sin fecha')}"):
                    st.write(f"**Evolución:** {evo.get('evolucion', '')}")
                    if evo.get('indicaciones'):
                        st.write(f"**Indicaciones:** {evo.get('indicaciones', '')}")
        else:
            st.info("No hay evoluciones registradas")
    
    # === TAB 3: RECETAS ===
    with tab3:
        st.markdown("### 💊 Recetas Médicas")
        
        with st.form("form_recetas_historial"):
            medicamentos = st.text_area("Medicamentos", height=200,
                                      placeholder="1. Paracetamol 500mg - 1 cada 8hs\n2. Amoxicilina 500mg - 1 cada 12hs...")
            indicaciones_receta = st.text_area("Indicaciones generales", height=100)
            
            submitted = st.form_submit_button(
                "💾 GUARDAR RECETA",
                use_container_width=True,
                type="primary"
            )
            
            if submitted:
                datos = {
                    "medicamentos": medicamentos,
                    "indicaciones": indicaciones_receta
                }
                
                exito, mensaje = guardar_registro(
                    tipo="recetas",
                    paciente_id=paciente_id,
                    paciente_nombre=paciente_nombre,
                    datos=datos
                )
                
                if exito:
                    st.success(f"✅ {mensaje}")
                    st.rerun()
                else:
                    st.error(f"❌ {mensaje}")
    
    # === TAB 4: MATERIALES ===
    with tab4:
        st.markdown("### 🔧 Materiales e Insumos Usados")
        
        with st.form("form_materiales_historial"):
            material = st.text_input("Material/insumo", placeholder="Ej: Gasas estériles 10x10")
            cantidad = st.number_input("Cantidad", 1, 1000, 1)
            observaciones_mat = st.text_area("Observaciones")
            
            submitted = st.form_submit_button(
                "💾 GUARDAR MATERIAL",
                use_container_width=True,
                type="primary"
            )
            
            if submitted:
                datos = {
                    "material": material,
                    "cantidad": cantidad,
                    "observaciones": observaciones_mat
                }
                
                exito, mensaje = guardar_registro(
                    tipo="materiales",
                    paciente_id=paciente_id,
                    paciente_nombre=paciente_nombre,
                    datos=datos
                )
                
                if exito:
                    st.success(f"✅ {mensaje}")
                    st.rerun()
                else:
                    st.error(f"❌ {mensaje}")
        
        # Mostrar materiales
        materiales = obtener_registros("materiales", paciente_id)
        if materiales:
            st.markdown("#### 📋 Materiales Usados")
            df_mat = pd.DataFrame(materiales)
            st.dataframe(df_mat.tail(10), use_container_width=True, hide_index=True)
        else:
            st.info("No hay materiales registrados")
    
    # === TAB 5: HISTORIAL COMPLETO ===
    with tab5:
        st.markdown("### 📚 Historial Clínico Completo")
        
        historial = obtener_historial_paciente(paciente_id)
        
        if historial:
            st.success(f"Total de registros en historial: {len(historial)}")
            
            # Ordenar por fecha
            historial_ordenado = sorted(historial, key=lambda x: x.get('timestamp', ''), reverse=True)
            
            for registro in historial_ordenado[:20]:  # Mostrar últimos 20
                tipo = registro.get('tipo', 'desconocido')
                fecha = registro.get('fecha', 'Sin fecha')
                
                # Icono según tipo
                icono = {
                    'signos_vitales': '📊',
                    'evolucion': '📝',
                    'receta': '💊',
                    'visita': '📅',
                    'material': '🔧'
                }.get(tipo, '📄')
                
                with st.expander(f"{icono} {tipo.upper()} - {fecha}"):
                    datos = registro.get('datos', {})
                    
                    if tipo == 'signos_vitales':
                        col1, col2, col3 = st.columns(3)
                        with col1:
                            st.write(f"**TA:** {datos.get('tension_arterial', 'N/A')}")
                            st.write(f"**FC:** {datos.get('frecuencia_cardiaca', 'N/A')}")
                        with col2:
                            st.write(f"**FR:** {datos.get('frecuencia_respiratoria', 'N/A')}")
                            st.write(f"**Temp:** {datos.get('temperatura', 'N/A')}")
                        with col3:
                            st.write(f"**SatO2:** {datos.get('saturacion_oxigeno', 'N/A')}")
                            st.write(f"**Glucemia:** {datos.get('glucemia', 'N/A')}")
                    
                    elif tipo == 'evolucion':
                        st.write(f"**Evolución:** {datos.get('evolucion', 'N/A')}")
                        st.write(f"**Indicaciones:** {datos.get('indicaciones', 'N/A')}")
                    
                    elif tipo == 'receta':
                        st.write(f"**Medicamentos:** {datos.get('medicamentos', 'N/A')}")
                    
                    elif tipo == 'material':
                        st.write(f"**Material:** {datos.get('material', 'N/A')}")
                        st.write(f"**Cantidad:** {datos.get('cantidad', 'N/A')}")
        else:
            st.info("No hay registros en el historial clínico")
    
    # === INFO FINAL ===
    st.markdown("---")
    st.success("✅ **Todos los datos se guardan automáticamente en el historial clínico del paciente**")
    st.caption("Los datos se almacenan localmente y están disponibles para consultas futuras.")


if __name__ == "__main__":
    render()
