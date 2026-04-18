"""
HISTORIAL CLINICO COMPLETO
Muestra y guarda TODOS los datos del paciente en un solo lugar
Usa sistema dual-read: SQL (Supabase) + session_state (JSON local)
"""

import json
import streamlit as st
from datetime import datetime

# Lazy import pandas - solo cargar cuando se necesite mostrar dataframe
_pandas = None
def get_pandas():
    global _pandas
    if _pandas is None:
        import pandas as pd
        _pandas = pd
    return _pandas

pd = get_pandas()

from core.database import guardar_datos
from core.clinical_exports import collect_patient_sections, build_history_pdf_bytes
from core.utils import ahora, mapa_detalles_pacientes
from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente


def _get_paciente_uuid(paciente_id, empresa):
    """Obtiene UUID del paciente para guardado SQL."""
    try:
        empresa_id = _obtener_uuid_empresa(empresa)
        if empresa_id:
            return _obtener_uuid_paciente(paciente_id, empresa_id)
    except Exception:
        pass
    return None


def _generar_historial_texto(paciente_sel, sections, user=None):
    """Genera texto completo del historial clinico para descarga."""
    sep = "=" * 60
    sep2 = "-" * 60
    
    # Extraer nombre e ID
    paciente_nombre = paciente_sel
    paciente_id = paciente_sel
    if isinstance(paciente_sel, str) and " - " in paciente_sel:
        partes = paciente_sel.rsplit(" - ", 1)
        paciente_nombre = partes[0]
        paciente_id = partes[1]
    
    lineas = [
        sep, "HISTORIAL CLINICO COMPLETO", sep,
        f"Paciente: {paciente_nombre}",
        f"DNI / ID: {paciente_id}",
        f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}",
    ]
    if user:
        lineas.append(f"Por: {user.get('nombre', '')}")
    lineas += [sep, ""]

    # Signos Vitales
    signos = sections.get("Signos Vitales", [])
    lineas += [f"SIGNOS VITALES ({len(signos)} registros)", sep2]
    for s in signos:
        lineas.append(f"  Fecha: {s.get('fecha', '-')}")
        lineas.append(f"    T.A: {s.get('TA', 'S/D')} | F.C: {s.get('FC', 'S/D')} | F.R: {s.get('FR', 'S/D')}")
        lineas.append(f"    Temp: {s.get('Temp', 'S/D')}°C | SatO2: {s.get('Sat', 'S/D')}% | Gluc: {s.get('HGT', 'S/D')}")
        if s.get('observaciones'):
            lineas.append(f"    Obs: {s['observaciones']}")
        lineas.append("")

    # Evoluciones
    evoluciones = sections.get("Procedimientos y Evoluciones", [])
    lineas += [f"EVOLUCIONES ({len(evoluciones)} registros)", sep2]
    for e in evoluciones:
        lineas.append(f"  Fecha: {e.get('fecha','-')} | Por: {e.get('firma','Sistema')}")
        lineas.append(f"    Plantilla: {e.get('plantilla','Libre')}")
        for l in str(e.get('nota','Sin nota')).split("\n"):
            lineas.append(f"    {l}")
        lineas.append("")

    # Recetas/Plan Terapeutico
    recetas = sections.get("Plan Terapeutico", [])
    lineas += [f"PLAN TERAPEUTICO ({len(recetas)} registros)", sep2]
    for r in recetas:
        lineas.append(f"  Fecha: {r.get('fecha','-')}")
        lineas.append(f"    Medicación: {r.get('med','-')}")
        lineas.append(f"    Estado: {r.get('estado_receta','Activa')}")
        if r.get('via'):
            lineas.append(f"    Vía: {r['via']}")
        if r.get('frecuencia'):
            lineas.append(f"    Frecuencia: {r['frecuencia']}")
        lineas.append("")

    # Materiales/Consumos
    materiales = sections.get("Materiales Utilizados", [])
    lineas += [f"MATERIALES E INSUMOS ({len(materiales)} registros)", sep2]
    for m in materiales:
        lineas.append(f"  Fecha: {m.get('fecha','-')}")
        lineas.append(f"    Insumo: {m.get('insumo', m.get('material','-'))} | Cantidad: {m.get('cantidad','-')}")
        if m.get('observaciones'):
            lineas.append(f"    Obs: {m['observaciones']}")
        lineas.append("")

    # Enfermeria
    cuidados = sections.get("Enfermeria y Plan de Cuidados", [])
    lineas += [f"ENFERMERIA ({len(cuidados)} registros)", sep2]
    for c in cuidados:
        lineas.append(f"  Fecha: {c.get('fecha','-')} | Por: {c.get('profesional','-')}")
        lineas.append(f"    Tipo: {c.get('tipo_cuidado','-')}")
        if c.get('intervencion'):
            lineas.append(f"    Intervención: {c['intervencion']}")
        lineas.append("")

    # Emergencias
    emergencias = sections.get("Emergencias y Ambulancia", [])
    lineas += [f"EMERGENCIAS ({len(emergencias)} registros)", sep2]
    for em in emergencias:
        lineas.append(f"  Fecha: {em.get('fecha_evento','-')}")
        lineas.append(f"    Motivo: {em.get('motivo','-')}")
        lineas.append(f"    Destino: {em.get('destino','-')}")
        lineas.append("")

    # Consentimientos
    consentimientos = sections.get("Consentimientos", [])
    lineas += [f"CONSENTIMIENTOS ({len(consentimientos)} registros)", sep2]
    for cons in consentimientos:
        lineas.append(f"  Fecha: {cons.get('fecha','-')} | Tipo: {cons.get('tipo_documento','-')}")
        lineas.append("")

    lineas += [sep, "FIN DEL HISTORIAL CLINICO", sep]
    return "\n".join(lineas)


def render(paciente_sel=None, user=None):
    """Vista de historial clínico completo con dual-read SQL + session_state."""
    
    st.markdown("# 📋 Historial Clínico Completo")
    st.caption("Todo el historial médico del paciente - Datos en tiempo real desde Supabase + local")
    
    # Obtener paciente actual del sidebar si no se pasó
    if not paciente_sel:
        paciente_sel = st.session_state.get("paciente_actual", "")
    
    if not paciente_sel:
        st.warning("⚠️ Selecciona un paciente primero desde la barra lateral")
        st.info("👈 Usa el buscador de pacientes en el sidebar izquierdo")
        return
    
    # Extraer datos del paciente
    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    empresa = detalles.get("empresa", "")
    
    paciente_nombre = paciente_sel
    paciente_id = paciente_sel
    if isinstance(paciente_sel, str) and " - " in paciente_sel:
        partes = paciente_sel.rsplit(" - ", 1)
        paciente_nombre = partes[0]
        paciente_id = partes[1]
    
    # OBTENER DATOS CON DUAL-READ (SQL + session_state)
    with st.spinner("📡 Cargando historial clínico..."):
        sections = collect_patient_sections(st.session_state, paciente_sel)
    
    # Contar totales
    total_signos = len(sections.get("Signos Vitales", []))
    total_evoluciones = len(sections.get("Procedimientos y Evoluciones", []))
    total_recetas = len(sections.get("Plan Terapeutico", []))
    total_materiales = len(sections.get("Materiales Utilizados", []))
    total_cuidados = len(sections.get("Enfermeria y Plan de Cuidados", []))
    
    # Mostrar info del paciente con métricas
    st.info(f"👤 **{paciente_nombre}** | 🆔 **DNI:** {paciente_id} | 🏥 **Empresa:** {empresa or 'No especificada'}")
    
    # Métricas rápidas
    cols = st.columns(5)
    cols[0].metric("📊 Signos", total_signos)
    cols[1].metric("📝 Evoluciones", total_evoluciones)
    cols[2].metric("💊 Recetas", total_recetas)
    cols[3].metric("🔧 Materiales", total_materiales)
    cols[4].metric("🏥 Enfermería", total_cuidados)
    
    # === TABS PARA DIFERENTES SECCIONES ===
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        f"📊 Signos Vitales ({total_signos})", 
        f"📝 Evoluciones ({total_evoluciones})", 
        f"💊 Recetas ({total_recetas})",
        f"🔧 Materiales ({total_materiales})",
        "📚 Historial Completo"
    ])
    
    # === TAB 1: SIGNOS VITALES ===
    with tab1:
        st.markdown("### 📊 Signos Vitales")
        st.caption("💡 Los signos vitales se guardan desde el módulo 'Clínica' o 'Enfermería'. Aquí se muestran todos los registros.")
        
        # Mostrar tabla de signos vitales desde dual-read (SQL + session_state)
        signos = sections.get("Signos Vitales", [])
        if signos:
            st.success(f"📋 Mostrando {len(signos)} registros de signos vitales (Supabase + local)")
            
            # Preparar datos para tabla
            tabla_signos = []
            for s in signos:
                tabla_signos.append({
                    'Fecha': s.get('fecha', ''),
                    'T.A.': s.get('TA', ''),
                    'F.C.': s.get('FC', ''),
                    'F.R.': s.get('FR', ''),
                    'Temp': s.get('Temp', ''),
                    'SatO2': s.get('Sat', ''),
                    'Gluc': s.get('HGT', ''),
                    'Obs': s.get('observaciones', ''),
                    'Registrado por': s.get('registrado_por', s.get('firma', 'Sistema'))
                })
            
            # Ordenar por fecha descendente
            tabla_signos = sorted(tabla_signos, key=lambda x: x['Fecha'], reverse=True)
            
            df_signos = pd.DataFrame(tabla_signos)
            st.dataframe(
                df_signos,
                use_container_width=True,
                hide_index=True,
                height=min(400, len(df_signos) * 45 + 50),
                column_config={
                    'Fecha': st.column_config.TextColumn('Fecha/Hora', width=130),
                    'T.A.': st.column_config.TextColumn('T.A.', width=90),
                    'F.C.': st.column_config.TextColumn('F.C.', width=70),
                    'F.R.': st.column_config.TextColumn('F.R.', width=70),
                    'Temp': st.column_config.TextColumn('Temp', width=70),
                    'SatO2': st.column_config.TextColumn('SatO2', width=70),
                    'Gluc': st.column_config.TextColumn('Gluc', width=70),
                    'Obs': st.column_config.TextColumn('Observaciones', width=200),
                    'Registrado por': st.column_config.TextColumn('Por', width=120)
                }
            )
            
            # Descargar
            csv = df_signos.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar CSV", csv, f"signos_vitales_{paciente_id}.csv", "text/csv")
        else:
            st.info("📭 No hay signos vitales registrados para este paciente")
            st.caption("💡 Usa el módulo 'Clínica' para registrar signos vitales")
    
    # === TAB 2: EVOLUCIONES ===
    with tab2:
        st.markdown("### 📝 Evoluciones Clínicas")
        st.caption("💡 Las evoluciones se guardan desde el módulo 'Evolución'. Aquí se muestran todas.")
        
        # Mostrar evoluciones desde dual-read (SQL + session_state)
        evoluciones = sections.get("Procedimientos y Evoluciones", [])
        if evoluciones:
            st.success(f"📋 Mostrando {len(evoluciones)} evoluciones (Supabase + local)")
            
            # Ordenar por fecha descendente
            evoluciones_ordenadas = sorted(evoluciones, key=lambda x: x.get('fecha', ''), reverse=True)
            
            for evo in evoluciones_ordenadas[:20]:  # Mostrar últimas 20
                with st.expander(f"📅 {evo.get('fecha', 'Sin fecha')} | 📝 {evo.get('plantilla', 'Libre')}"):
                    st.markdown(f"**👤 Registrado por:** {evo.get('firma', 'Sistema')}")
                    if evo.get('id_sql'):
                        st.caption(f"🆔 SQL ID: {evo['id_sql']}")
                    st.markdown("**📝 Nota/Evolución:**")
                    nota_txt = evo.get('nota', 'Sin nota')
                    st.markdown(f'<div style="background:#0f172a;padding:10px;border-radius:8px;max-height:300px;overflow-y:auto;">{nota_txt}</div>', unsafe_allow_html=True)
        else:
            st.info("� No hay evoluciones registradas para este paciente")
            st.caption("💡 Usa el módulo 'Evolución' para registrar evoluciones clínicas")
    
    # === TAB 3: RECETAS ===
    with tab3:
        st.markdown("### 💊 Plan Terapéutico / Recetas")
        st.caption("💡 Las recetas se guardan desde el módulo 'Recetas' o 'Clínica'. Aquí se muestran todas.")
        
        # Mostrar recetas/indicaciones desde dual-read (SQL + session_state)
        recetas = sections.get("Plan Terapeutico", [])
        if recetas:
            st.success(f"📋 Mostrando {len(recetas)} registros del plan terapéutico (Supabase + local)")
            
            # Ordenar por fecha descendente
            recetas_ordenadas = sorted(recetas, key=lambda x: x.get('fecha', ''), reverse=True)
            
            for rec in recetas_ordenadas[:15]:  # Mostrar últimas 15
                with st.expander(f"📅 {rec.get('fecha', 'Sin fecha')} | 💊 {rec.get('med', 'Sin medicación')[:40]}..."):
                    if rec.get('id_sql'):
                        st.caption(f"🆔 SQL ID: {rec['id_sql']}")
                    st.markdown(f"**💊 Medicación/Indicación:**")
                    st.markdown(f'<div style="background:#0f172a;padding:10px;border-radius:8px;">{rec.get("med", "-")}</div>', unsafe_allow_html=True)
                    
                    cols = st.columns(3)
                    cols[0].metric("Estado", rec.get('estado_receta', 'Activa'))
                    cols[1].metric("Vía", rec.get('via', '-') or '-')
                    cols[2].metric("Frecuencia", rec.get('frecuencia', '-') or '-')
                    
                    if rec.get('dias_duracion'):
                        st.caption(f"⏱️ Duración: {rec['dias_duracion']} días")
                    if rec.get('medico_nombre'):
                        st.caption(f"�‍⚕️ Médico: {rec['medico_nombre']}")
        else:
            st.info("� No hay recetas ni plan terapéutico registrado")
            st.caption("💡 Usa el módulo 'Recetas' para agregar medicación")
    
    # === TAB 4: MATERIALES ===
    with tab4:
        st.markdown("### 🔧 Materiales e Insumos")
        st.caption("💡 Los materiales se guardan desde el módulo 'Materiales' o 'Enfermería'. Aquí se muestran todos.")
        
        # Mostrar materiales desde dual-read (SQL + session_state)
        materiales = sections.get("Materiales Utilizados", [])
        if materiales:
            st.success(f"📋 Mostrando {len(materiales)} registros de materiales (Supabase + local)")
            
            # Preparar tabla
            tabla_mat = []
            for m in materiales:
                tabla_mat.append({
                    'Fecha': m.get('fecha', ''),
                    'Material/Insumo': m.get('insumo', m.get('material', '-')),
                    'Cantidad': m.get('cantidad', '-'),
                    'Observaciones': m.get('observaciones', ''),
                    'Profesional': m.get('firma', m.get('profesional', 'Sistema'))
                })
            
            # Ordenar por fecha descendente
            tabla_mat = sorted(tabla_mat, key=lambda x: x['Fecha'], reverse=True)
            
            df_mat = pd.DataFrame(tabla_mat)
            st.dataframe(
                df_mat,
                use_container_width=True,
                hide_index=True,
                height=min(400, len(df_mat) * 45 + 50),
                column_config={
                    'Fecha': st.column_config.TextColumn('Fecha/Hora', width=130),
                    'Material/Insumo': st.column_config.TextColumn('Material', width=250),
                    'Cantidad': st.column_config.TextColumn('Cantidad', width=90),
                    'Observaciones': st.column_config.TextColumn('Observaciones', width=200),
                    'Profesional': st.column_config.TextColumn('Por', width=120)
                }
            )
            
            csv = df_mat.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Descargar CSV", csv, f"materiales_{paciente_id}.csv", "text/csv")
        else:
            st.info("� No hay materiales registrados")
            st.caption("💡 Usa el módulo 'Materiales' para registrar insumos utilizados")
    
    # === TAB 5: HISTORIAL COMPLETO ===
    with tab5:
        st.markdown("### 📚 Historial Clínico Completo")
        st.caption("🔄 Datos sincronizados desde Supabase (PostgreSQL) + almacenamiento local")

        # --- BOTONES DE DESCARGA ---
        st.markdown("#### 📥 Exportar Historial")
        dcol1, dcol2, dcol3 = st.columns(3)
        
        with dcol1:
            # Generar PDF profesional usando el sistema existente
            with st.spinner("📄 Generando PDF..."):
                pdf_bytes = build_history_pdf_bytes(st.session_state, paciente_sel, empresa or "MediCare")
            st.download_button(
                "📄 Descargar PDF",
                data=pdf_bytes,
                file_name=f"historial_{paciente_id.replace(' ','_')}_{datetime.now().strftime('%Y%m%d')}.pdf",
                mime="application/pdf",
                use_container_width=True,
                type="primary",
                key="dl_historial_pdf"
            )
        
        with dcol2:
            # Exportar como JSON con todas las secciones
            json_export = json.dumps(
                {
                    "paciente": paciente_nombre,
                    "dni": paciente_id,
                    "exportado": datetime.now().isoformat(),
                    "empresa": empresa,
                    "secciones": sections
                },
                ensure_ascii=False, indent=2, default=str
            )
            st.download_button(
                "🔷 Descargar JSON",
                data=json_export.encode("utf-8"),
                file_name=f"historial_{paciente_id.replace(' ','_')}.json",
                mime="application/json",
                use_container_width=True,
                key="dl_historial_json"
            )
        
        with dcol3:
            # Debug: mostrar fuente de datos
            st.caption("📊 Fuentes de datos:")
            for nombre, regs in sections.items():
                if regs:
                    st.caption(f"- {nombre}: {len(regs)} registros")

        st.markdown("---")
        st.success(f"✅ Historial completo cargado: {sum(len(r) for r in sections.values())} registros totales")
        st.info("💡 Los datos se leen desde: 1) Supabase SQL (primario) + 2) Almacenamiento local (caché)")
        
        # Mostrar todas las secciones con datos
        for nombre_seccion, registros in sections.items():
            if registros:
                with st.expander(f"📂 {nombre_seccion} ({len(registros)} registros)"):
                    st.json([{k: str(v)[:100] + "..." if len(str(v)) > 100 else v for k, v in r.items()} for r in registros[:5]])
                    if len(registros) > 5:
                        st.caption(f"... y {len(registros) - 5} registros más")


if __name__ == "__main__":
    render()
