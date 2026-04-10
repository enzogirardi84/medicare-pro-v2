from datetime import datetime, date
from typing import Dict, Any, List

import streamlit as st

from core.database import guardar_datos
from core.utils import ahora, seleccionar_limite_registros


def _parse_fecha_nacimiento(fecha_str: str) -> date:
    """Intenta parsear la fecha de nacimiento que viene de la DB como string a objeto date."""
    try:
        return datetime.strptime(fecha_str, "%d/%m/%Y").date()
    except (ValueError, TypeError):
        return date(1990, 1, 1)


def _actualizar_id_en_cascada(viejo_id: str, nuevo_id: str) -> None:
    """Busca en todas las tablas de la base de datos y actualiza el ID del paciente si cambió."""
    if viejo_id == nuevo_id:
        return
        
    for key, value in st.session_state.items():
        if key.endswith("_db") and isinstance(value, list):
            for registro in value:
                if isinstance(registro, dict) and registro.get("paciente") == viejo_id:
                    registro["paciente"] = nuevo_id


def _render_formulario_admision(mi_empresa: str, rol: str, paciente_editar: str = None) -> None:
    """Renderiza el formulario tanto para crear como para editar pacientes."""
    es_edicion = paciente_editar is not None
    detalles_previos = st.session_state["detalles_pacientes_db"].get(paciente_editar, {}) if es_edicion else {}
    
    # Pre-llenar datos si es edición
    nombre_previo = paciente_editar.split(" - ")[0] if es_edicion else ""
    dni_previo = detalles_previos.get("dni", "")
    
    with st.form("adm_form", clear_on_submit=not es_edicion):
        st.markdown(f"##### {'✏️ Editar legajo de ' + nombre_previo if es_edicion else '📝 Datos del nuevo legajo'}")
        
        if es_edicion:
            st.warning("⚠️ Si modificas el Nombre o el DNI, el sistema actualizará automáticamente todas las historias clínicas y evoluciones asociadas para no perder datos.")
            
        col_a, col_b = st.columns(2)
        n = col_a.text_input("Nombre y apellido *", value=nombre_previo, placeholder="Juan Perez")
        o = col_b.text_input("Obra social / prepaga", value=detalles_previos.get("obra_social", ""), placeholder="OSDE / PAMI / Particular")

        col_c, col_d = st.columns(2)
        d = col_c.text_input("DNI del paciente *", value=dni_previo, placeholder="35123456")
        f_nac = col_d.date_input(
            "Fecha de nacimiento",
            value=_parse_fecha_nacimiento(detalles_previos.get("fnac", "")),
            min_value=date(1900, 1, 1),
            max_value=ahora().date(),
        )

        col_e, col_f = st.columns(2)
        sexo_previo = detalles_previos.get("sexo", "Otro")
        idx_sexo = ["F", "M", "Otro"].index(sexo_previo) if sexo_previo in ["F", "M", "Otro"] else 2
        se = col_e.selectbox("Sexo", ["F", "M", "Otro"], index=idx_sexo)
        
        tel = col_f.text_input("WhatsApp / teléfono", value=detalles_previos.get("telefono", ""), placeholder="3584302024")
        dir_p = st.text_input("Dirección exacta", value=detalles_previos.get("direccion", ""), placeholder="Calle 123, barrio, ciudad")

        st.markdown("##### Alertas y antecedentes")
        col_alg, col_pat = st.columns(2)
        alergias = col_alg.text_area("Alergias", value=detalles_previos.get("alergias", ""), placeholder="Ej: penicilina, ibuprofeno...", height=90)
        patologias = col_pat.text_area("Patologías previas / riesgos", value=detalles_previos.get("patologias", ""), placeholder="Ej: DBT, HTA, marcapasos...", height=90)

        # Manejo de Empresa
        empresa_previa = detalles_previos.get("empresa", mi_empresa)
        if rol == "SuperAdmin":
            emp_d = st.text_input("Empresa / clínica", value=empresa_previa)
        else:
            emp_d = empresa_previa
            st.info(f"Paciente asignado a: {emp_d}")
            
        estado_opciones = ["Activo", "De Alta", "Inactivo"]
        estado_previo = detalles_previos.get("estado", "Activo")
        idx_estado = estado_opciones.index(estado_previo) if estado_previo in estado_opciones else 0
        estado_actual = st.selectbox("Estado del paciente", estado_opciones, index=idx_estado)

        col_btn1, col_btn2 = st.columns([3, 1])
        label_boton = "Guardar cambios" if es_edicion else "Habilitar paciente"
        
        if col_btn1.form_submit_button(label_boton, use_container_width=True, type="primary"):
            if not n.strip() or not d.strip():
                st.error("Nombre y DNI son obligatorios.")
                return
                
            nuevo_id = f"{n.strip()} - {d.strip()}"
            
            # Validación de duplicados (solo si es nuevo, o si cambió el DNI)
            if not es_edicion or (es_edicion and d.strip() != dni_previo):
                dni_existente = any(det.get("dni") == d.strip() for k, det in st.session_state["detalles_pacientes_db"].items() if k != paciente_editar)
                if dni_existente:
                    st.error("Ya existe otro paciente con ese DNI en el sistema.")
                    return

            # Si es edición, limpiamos el registro viejo y actualizamos cascada
            if es_edicion:
                if paciente_editar != nuevo_id:
                    _actualizar_id_en_cascada(paciente_editar, nuevo_id)
                    st.session_state["pacientes_db"].remove(paciente_editar)
                    del st.session_state["detalles_pacientes_db"][paciente_editar]
            
            # Guardar/Actualizar detalles
            if nuevo_id not in st.session_state["pacientes_db"]:
                 st.session_state["pacientes_db"].append(nuevo_id)
                 
            st.session_state["detalles_pacientes_db"][nuevo_id] = {
                "dni": d.strip(),
                "fnac": f_nac.strftime("%d/%m/%Y"),
                "sexo": se,
                "telefono": tel.strip(),
                "direccion": dir_p.strip(),
                "empresa": emp_d.strip(),
                "estado": estado_actual,
                "obra_social": o.strip(),
                "alergias": alergias.strip(),
                "patologias": patologias.strip(),
            }
            
            guardar_datos()
            
            if es_edicion:
                st.session_state["editando_admision"] = None
                st.toast(f"Legajo de {n} actualizado correctamente.", icon="✅")
            else:
                st.toast(f"Paciente {n} dado de alta correctamente.", icon="✅")
                
            st.rerun()

        # Botón de cancelar si estamos en modo edición
        if es_edicion:
            if col_btn2.form_submit_button("Cancelar", use_container_width=True):
                st.session_state["editando_admision"] = None
                st.rerun()


def _render_padron_pacientes() -> None:
    """Renderiza el padrón de pacientes con búsqueda, edición y borrado (Anti-colapso)."""
    st.markdown("##### Buscador y Gestión de Padrón")
    buscar_padron = st.text_input("🔍 Buscar por nombre, DNI o empresa...", key="buscar_padron").lower()
    
    # Filtrar pacientes
    pacientes_filtrados = []
    for p in st.session_state.get("pacientes_db", []):
        det = st.session_state["detalles_pacientes_db"].get(p, {})
        texto_busqueda = f"{p.lower()} {det.get('dni', '')} {det.get('empresa', '').lower()}"
        if not buscar_padron or buscar_padron in texto_busqueda:
            pacientes_filtrados.append(p)

    limite = seleccionar_limite_registros(
        "Pacientes a mostrar", len(pacientes_filtrados),
        key="limite_padron", default=20, opciones=(10, 20, 50, 100)
    )
    
    st.caption(f"Mostrando {min(limite, len(pacientes_filtrados))} de {len(pacientes_filtrados)} pacientes encontrados.")

    # Contenedor con SCROLL ACTIVO (Anti-colapso)
    with st.container(height=600):
        for p in pacientes_filtrados[:limite]:
            det = st.session_state["detalles_pacientes_db"].get(p, {})
            
            with st.container(border=True):
                col_info, col_acciones = st.columns([3, 1])
                
                estado_badge = "🟢" if det.get('estado') == 'Activo' else "🔴"
                col_info.markdown(f"**{estado_badge} {p.split(' - ')[0]}**")
                col_info.caption(f"DNI: {det.get('dni', 'S/D')} | O.S: {det.get('obra_social', 'S/D')} | Empresa: {det.get('empresa', 'S/D')}")
                
                with col_acciones:
                    if st.button("✏️ Editar", key=f"edit_adm_{p}", use_container_width=True):
                        st.session_state["editando_admision"] = p
                        st.rerun()
                        
                    # Borrado protegido por checkbox
                    chk_borrar = st.checkbox("Habilitar", key=f"chk_del_adm_{p}")
                    if st.button("🗑️ Borrar", key=f"btn_del_adm_{p}", type="primary", use_container_width=True, disabled=not chk_borrar):
                        st.session_state["pacientes_db"].remove(p)
                        if p in st.session_state["detalles_pacientes_db"]:
                            del st.session_state["detalles_pacientes_db"][p]
                        guardar_datos()
                        st.toast(f"Paciente {p.split(' - ')[0]} eliminado del padrón.", icon="🗑️")
                        st.rerun()


# --- Función Principal (Enrutador) ---
def render_admision(mi_empresa: str, rol: str) -> None:
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Admisión y Gestión de Pacientes</h2>
            <p class="mc-hero-text">Controla el padrón activo de pacientes. Carga nuevos legajos, corrige errores de tipeo y administra las bajas sin perder la integridad de las historias clínicas.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Revisar si estamos en modo edición para forzar esa vista
    paciente_en_edicion = st.session_state.get("editando_admision")

    if paciente_en_edicion:
        st.info("Modo Edición Activado. Modifica los datos y presiona Guardar cambios.")
        _render_formulario_admision(mi_empresa, rol, paciente_editar=paciente_en_edicion)
    else:
        # Usamos pestañas para organizar la UI de forma limpia
        tab1, tab2 = st.tabs(["➕ Nueva Admisión", "📋 Padrón y Gestión (Editar/Borrar)"])
        
        with tab1:
            st.markdown(
                """
                <div class="mc-grid-3">
                    <div class="mc-card"><h4>Datos personales</h4><p>Nombre, DNI, nacimiento y contacto.</p></div>
                    <div class="mc-card"><h4>Datos administrativos</h4><p>Obra social y empresa asignada.</p></div>
                    <div class="mc-card"><h4>Alertas clínicas</h4><p>Alergias y patologías para visualización rápida.</p></div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            _render_formulario_admision(mi_empresa, rol)
            
        with tab2:
            _render_padron_pacientes()
