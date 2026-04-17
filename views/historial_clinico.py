"""
HISTORIAL CLINICO COMPLETO
Muestra y guarda TODOS los datos del paciente en un solo lugar
"""

import json
import streamlit as st
import pandas as pd
from datetime import datetime

from core.guardado_universal import (
    guardar_registro,
    obtener_historial_paciente,
    obtener_registros
)


def _generar_historial_texto(paciente_nombre, paciente_id, user=None):
    """Genera texto completo del historial clinico para descarga."""
    sep = "=" * 60
    sep2 = "-" * 60
    lineas = [
        sep, "HISTORIAL CLINICO COMPLETO", sep,
        f"Paciente: {paciente_nombre}",
        f"DNI / ID: {paciente_id}",
        f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    ]
    if user:
        lineas.append(f"Por: {user.get('nombre', '')}")
    lineas += [sep, ""]

    signos = obtener_registros("signos_vitales", paciente_id)
    lineas += [f"SIGNOS VITALES ({len(signos)} registros)", sep2]
    for s in signos:
        d = s.get("datos", {})
        lineas.append(f"  Fecha: {s.get('fecha', '-')}")
        for campo, lbl in [("tension_arterial","T.A"),("frecuencia_cardiaca","F.C"),("temperatura","Temp"),
                           ("saturacion_oxigeno","SatO2"),("glucemia","Gluc"),("peso","Peso"),("talla","Talla")]:
            if d.get(campo):
                lineas.append(f"    {lbl}: {d[campo]}")
        if d.get("observaciones"):
            lineas.append(f"    Obs: {d['observaciones']}")
        lineas.append("")

    evoluciones = obtener_registros("evoluciones", paciente_id)
    ss_evols = [e for e in st.session_state.get("evoluciones_db", [])
                if paciente_id in str(e.get("paciente","")) or paciente_nombre in str(e.get("paciente",""))]
    total_evols = len(evoluciones) + len(ss_evols)
    lineas += [f"EVOLUCIONES ({total_evols} registros)", sep2]
    for e in evoluciones:
        d = e.get("datos", {})
        firma = d.get("firma", d.get("firma_medico", e.get("paciente_nombre", "")))
        nota = d.get("nota", d.get("nota_medica", d.get("evolucion", "-")))
        lineas.append(f"  Fecha: {e.get('fecha','-')} | Plantilla: {d.get('plantilla','Libre')} | Por: {firma}")
        for l in str(nota).split("\n"):
            lineas.append(f"    {l}")
        if d.get("indicaciones"):
            lineas.append(f"  Indicaciones: {d['indicaciones']}")
        lineas.append("")
    for se in ss_evols:
        lineas.append(f"  Fecha: {se.get('fecha','-')} | Por: {se.get('firma','')}")
        for l in str(se.get('nota','')).split("\n"):
            lineas.append(f"    {l}")
        lineas.append("")

    recetas = obtener_registros("recetas", paciente_id)
    lineas += [f"RECETAS ({len(recetas)} registros)", sep2]
    for r in recetas:
        d = r.get("datos", {})
        lineas.append(f"  Fecha: {r.get('fecha','-')}")
        lineas.append(f"  Medicamentos: {d.get('medicamentos','-')}")
        if d.get("indicaciones"):
            lineas.append(f"  Indicaciones: {d['indicaciones']}")
        lineas.append("")

    materiales = obtener_registros("materiales", paciente_id)
    lineas += [f"MATERIALES E INSUMOS ({len(materiales)} registros)", sep2]
    for m in materiales:
        d = m.get("datos", {})
        lineas.append(f"  Fecha: {m.get('fecha','-')} | {d.get('material','-')} x {d.get('cantidad','-')}")
        if d.get("observaciones"):
            lineas.append(f"  Obs: {d['observaciones']}")
        lineas.append("")

    lineas += [sep, "FIN DEL HISTORIAL CLINICO", sep]
    return "\n".join(lineas)


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
            
            # Preparar datos para tabla
            tabla_signos = []
            for s in signos:
                datos = s.get('datos', {})
                tabla_signos.append({
                    'Fecha': s.get('fecha', ''),
                    'T.A.': datos.get('tension_arterial', ''),
                    'F.C.': datos.get('frecuencia_cardiaca', ''),
                    'F.R.': datos.get('frecuencia_respiratoria', ''),
                    'Temp': datos.get('temperatura', ''),
                    'SatO2': datos.get('saturacion_oxigeno', ''),
                    'Gluc': datos.get('glucemia', ''),
                    'Peso': datos.get('peso', ''),
                    'Talla': datos.get('talla', ''),
                    'Obs': datos.get('observaciones', '')
                })
            
            df_signos = pd.DataFrame(tabla_signos)
            st.dataframe(
                df_signos,
                use_container_width=True,
                hide_index=True,
                height=min(350, len(df_signos) * 45 + 50),
                column_config={
                    'Fecha': st.column_config.TextColumn('Fecha/Hora', width=120),
                    'T.A.': st.column_config.TextColumn('T.A.', width=90),
                    'F.C.': st.column_config.NumberColumn('F.C.', width=70),
                    'F.R.': st.column_config.NumberColumn('F.R.', width=70),
                    'Temp': st.column_config.NumberColumn('Temp', width=70, format="%.1f"),
                    'SatO2': st.column_config.NumberColumn('SatO2', width=70),
                    'Gluc': st.column_config.TextColumn('Gluc', width=70),
                    'Peso': st.column_config.NumberColumn('Peso', width=70),
                    'Talla': st.column_config.NumberColumn('Talla', width=70),
                    'Obs': st.column_config.TextColumn('Observaciones', width=150)
                }
            )
            
            # Descargar
            csv = df_signos.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar CSV", csv, f"signos_vitales_{paciente_id}.csv", "text/csv")
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
            st.markdown(f"#### 📋 Evoluciones Guardadas ({len(evoluciones)} total)")
            for evo in reversed(evoluciones[-10:]):  # Mostrar últimas 10
                datos = evo.get('datos', {})
                with st.expander(f"📅 {evo.get('fecha', 'Sin fecha')}"):
                    st.markdown(f"**👤 Registrado por:** {evo.get('paciente_nombre', '')}")
                    st.markdown("**📝 Evolución:**")
                    nota_txt = datos.get('evolucion', datos.get('nota', 'Sin evolución'))
                    st.markdown(f'<div class="mc-scroll-block">{nota_txt}</div>', unsafe_allow_html=True)
                    if datos.get('indicaciones'):
                        st.markdown("**💊 Indicaciones:**")
                        st.markdown(f'<div class="mc-scroll-block" style="max-height:120px">{datos["indicaciones"]}</div>', unsafe_allow_html=True)
        else:
            st.info("📋 No hay evoluciones registradas. Usa el formulario de arriba para agregar la primera.")
    
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
        
        # Mostrar recetas
        recetas = obtener_registros("recetas", paciente_id)
        if recetas:
            st.markdown(f"#### 📋 Recetas Guardadas ({len(recetas)} total)")
            
            for rec in reversed(recetas[-5:]):  # Mostrar últimas 5
                datos = rec.get('datos', {})
                with st.expander(f"📅 {rec.get('fecha', 'Sin fecha')}"):
                    st.markdown("**💊 Medicamentos:**")
                    st.markdown(f'<div class="mc-scroll-block">{datos.get("medicamentos", "Sin medicamentos")}</div>', unsafe_allow_html=True)
                    if datos.get('indicaciones'):
                        st.markdown("**📝 Indicaciones:**")
                        st.markdown(f'<div class="mc-scroll-block" style="max-height:100px">{datos["indicaciones"]}</div>', unsafe_allow_html=True)
        else:
            st.info("📋 No hay recetas registradas. Usa el formulario de arriba para agregar la primera.")
    
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
            st.markdown(f"#### 📋 Materiales Usados ({len(materiales)} total)")
            
            # Preparar tabla
            tabla_mat = []
            for m in materiales:
                datos = m.get('datos', {})
                tabla_mat.append({
                    'Fecha': m.get('fecha', ''),
                    'Material': datos.get('material', ''),
                    'Cantidad': datos.get('cantidad', 0),
                    'Observaciones': datos.get('observaciones', '')
                })
            
            df_mat = pd.DataFrame(tabla_mat)
            st.dataframe(
                df_mat,
                use_container_width=True,
                hide_index=True,
                height=min(300, len(df_mat) * 45 + 50),
                column_config={
                    'Fecha': st.column_config.TextColumn('Fecha/Hora', width=130),
                    'Material': st.column_config.TextColumn('Material/Insumo', width=200),
                    'Cantidad': st.column_config.NumberColumn('Cantidad', width=90),
                    'Observaciones': st.column_config.TextColumn('Observaciones', width=250)
                }
            )
            
            csv = df_mat.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar CSV", csv, f"materiales_{paciente_id}.csv", "text/csv")
        else:
            st.info("📋 No hay materiales registrados. Usa el formulario de arriba para agregar el primero.")
    
    # === TAB 5: HISTORIAL COMPLETO ===
    with tab5:
        st.markdown("### 📚 Historial Clínico Completo")

        # --- BOTONES DE DESCARGA ---
        st.markdown("#### 📥 Descargar Historial")
        dcol1, dcol2 = st.columns(2)
        with dcol1:
            texto_hist = _generar_historial_texto(paciente_nombre, paciente_id, user)
            st.download_button(
                "📄 Descargar Historial Completo (.txt)",
                data=texto_hist.encode("utf-8"),
                file_name=f"historial_{paciente_id.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.txt",
                mime="text/plain",
                use_container_width=True,
                type="primary",
                key="dl_historial_txt"
            )
        with dcol2:
            todos_regs = obtener_historial_paciente(paciente_id)
            ss_evols = [e for e in st.session_state.get("evoluciones_db", [])
                        if paciente_id in str(e.get("paciente","")) or paciente_nombre in str(e.get("paciente",""))]
            json_export = json.dumps(
                {"paciente": paciente_nombre, "dni": paciente_id,
                 "exportado": datetime.now().isoformat(),
                 "historial_local": todos_regs, "evoluciones_sesion": ss_evols},
                ensure_ascii=False, indent=2
            )
            st.download_button(
                "🔷 Descargar JSON Completo",
                data=json_export.encode("utf-8"),
                file_name=f"historial_{paciente_id.replace(' ','_')}.json",
                mime="application/json",
                use_container_width=True,
                key="dl_historial_json"
            )

        st.markdown("---")
        historial = obtener_historial_paciente(paciente_id)

        if historial:
            st.success(f"Total de registros en historial: {len(historial)}")
            
            # Ordenar por fecha
            historial_ordenado = sorted(historial, key=lambda x: x.get('timestamp', ''), reverse=True)
            
            for registro in historial_ordenado[:20]:  # Mostrar últimos 20
                tipo = registro.get('tipo', 'desconocido')
                fecha = registro.get('fecha', 'Sin fecha')
                datos = registro.get('datos', {})
                
                # Icono y color según tipo
                iconos = {
                    'signos_vitales': ('📊', 'blue'),
                    'evoluciones': ('📝', 'green'),
                    'recetas': ('💊', 'orange'),
                    'materiales': ('🔧', 'red'),
                    'evolucion': ('📝', 'green'),
                    'receta': ('�', 'orange'),
                    'material': ('🔧', 'red')
                }
                icono, color = iconos.get(tipo, ('📄', 'gray'))
                
                with st.expander(f"{icono} **{tipo.replace('_', ' ').upper()}** - {fecha}"):
                    st.caption(f"ID: {registro.get('id', 'N/A')}")
                    
                    if tipo in ['signos_vitales']:
                        cols = st.columns(4)
                        metricas = [
                            ('T.A.', datos.get('tension_arterial', '-')),
                            ('F.C.', datos.get('frecuencia_cardiaca', '-')),
                            ('F.R.', datos.get('frecuencia_respiratoria', '-')),
                            ('Temp', datos.get('temperatura', '-')),
                            ('SatO2', datos.get('saturacion_oxigeno', '-')),
                            ('Gluc', datos.get('glucemia', '-')),
                            ('Peso', datos.get('peso', '-')),
                            ('Talla', datos.get('talla', '-'))
                        ]
                        for i, (label, valor) in enumerate(metricas):
                            with cols[i % 4]:
                                st.metric(label, valor)
                        if datos.get('observaciones'):
                            st.markdown(f"**📝 Observaciones:** {datos.get('observaciones')}")
                    
                    elif tipo in ['evoluciones', 'evolucion']:
                        st.markdown("**📝 Evolución Clínica:**")
                        nota_ev = datos.get('nota', datos.get('nota_medica', datos.get('evolucion', 'Sin evolución')))
                        st.markdown(f'<div class="mc-scroll-block">{nota_ev}</div>', unsafe_allow_html=True)
                        if datos.get('indicaciones'):
                            st.markdown("**💊 Indicaciones:**")
                            st.markdown(f'<div class="mc-scroll-block" style="max-height:100px">{datos["indicaciones"]}</div>', unsafe_allow_html=True)
                    
                    elif tipo in ['recetas', 'receta']:
                        st.markdown("**💊 Medicamentos:**")
                        st.markdown(f'<div class="mc-scroll-block">{datos.get("medicamentos", "Sin medicamentos")}</div>', unsafe_allow_html=True)
                        if datos.get('indicaciones'):
                            st.markdown("**📝 Indicaciones generales:**")
                            st.markdown(f'<div class="mc-scroll-block" style="max-height:100px">{datos["indicaciones"]}</div>', unsafe_allow_html=True)
                    
                    elif tipo in ['materiales', 'material']:
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Material", datos.get('material', '-'))
                        with col2:
                            st.metric("Cantidad", datos.get('cantidad', '-'))
                        if datos.get('observaciones'):
                            st.markdown(f"**📝 Observaciones:** {datos.get('observaciones')}")
        else:
            st.info("No hay registros en el historial clínico")
    
    # === INFO FINAL ===
    st.markdown("---")
    st.success("✅ **Todos los datos se guardan automáticamente en el historial clínico del paciente**")
    st.caption("Los datos se almacenan localmente y están disponibles para consultas futuras.")


if __name__ == "__main__":
    render()
