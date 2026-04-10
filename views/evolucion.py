import base64
from datetime import datetime
from typing import Dict, Any, List

import streamlit as st

from core.database import guardar_datos
from core.utils import (
    ahora,
    firma_a_base64,
    obtener_config_firma,
    optimizar_imagen_bytes,
    puede_accion,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_DISPONIBLE = True
except ImportError:
    pass

# --- 1. Plantillas Exclusivas de Profesionales de Salud ---
PLANTILLAS_EVOLUCION = {
    "Libre": "",
    "Médico": "Motivo de consulta:\nExamen físico / Signos relevantes:\nDiagnóstico presuntivo:\nConducta / Tratamiento indicado:\nPlan y seguimiento:",
    "Enfermería": "Procedimiento realizado / Control:\nEstado general del paciente:\nSitio de acceso / Curación:\nTolerancia al procedimiento:\nIndicaciones al paciente/familia:",
    "Kinesiología": "Evaluación funcional / Respiratoria:\nTono y trofismo muscular:\nTécnicas aplicadas:\nTolerancia a la sesión:\nPautas para el hogar:",
    "Psicología": "Estado de ánimo / Afectividad:\nContenido del discurso:\nIntervención realizada:\nEvolución respecto a sesión previa:\nPlan terapéutico:",
    "Nutrición": "Peso / IMC actual:\nTolerancia a la dieta:\nAdherencia al plan alimentario:\nModificaciones indicadas:\nEducación nutricional brindada:",
    "Fonoaudiología": "Evaluación de la deglución / fonación:\nEjercicios realizados:\nRespuesta del paciente:\nPautas alimentarias / fonatorias:\nSeguimiento:"
}

# --- Funciones de Utilidad y Seguridad Legal ---
def _es_editable(fecha_str: str, firma_registro: str, nombre_usuario: str) -> tuple[bool, int]:
    """Evalúa si una evolución tiene menos de 30 minutos y pertenece EXCLUSIVAMENTE al usuario actual."""
    if firma_registro != nombre_usuario:
        return False, 0  # No es el autor, se bloquea la edición/borrado
    try:
        fecha_dt = datetime.strptime(fecha_str, "%d/%m/%Y %H:%M")
        ahora_dt = ahora()
        
        if ahora_dt.tzinfo is not None:
            ahora_dt = ahora_dt.replace(tzinfo=None)
            
        minutos_transcurridos = (ahora_dt - fecha_dt).total_seconds() / 60.0
        minutos_restantes = int(30 - minutos_transcurridos)
        
        return (minutos_transcurridos <= 30), max(0, minutos_restantes)
    except Exception:
        return False, 0


# --- Subcomponentes de UI ---
def _render_captura_firma(paciente_sel: str) -> None:
    """Renderiza el bloque de captura de firma digital del paciente/familiar."""
    st.markdown("##### Firma Digital del Paciente / Familiar")
    
    if not CANVAS_DISPONIBLE:
        st.warning("Librería de firma interactiva no disponible. Usa la subida de imagen.")
        firma_subida = st.file_uploader("Subir imagen de la firma", type=["png", "jpg", "jpeg"], key="firma_upload_evolucion_sin_canvas")
        canvas_result = None
    else:
        firma_cfg = obtener_config_firma("evolucion")
        metodo_firma = st.radio(
            "Método de firma",
            ["Subir foto de la firma (recomendado en celulares)", "Firmar en pantalla"],
            horizontal=True,
            key="metodo_firma_evolucion",
        )
        
        firma_subida = None
        canvas_result = None
        
        if "Subir" in metodo_firma:
            firma_subida = st.file_uploader("Subir imagen de la firma", type=["png", "jpg", "jpeg"], key="firma_upload_evolucion")
        else:
            st.caption("Usa el lienzo solo si el dispositivo responde fluido.")
            canvas_result = st_canvas(
                fill_color="rgba(255, 255, 255, 1)",
                stroke_width=firma_cfg["stroke_width"],
                stroke_color="#000000",
                background_color="#ffffff",
                height=firma_cfg["height"],
                width=firma_cfg["width"],
                drawing_mode="freedraw",
                display_toolbar=firma_cfg["display_toolbar"],
                key="canvas_firma_evolucion",
            )

    if st.button("Guardar Firma Digital", use_container_width=True, type="secondary"):
        b64_firma = firma_a_base64(
            canvas_image_data=canvas_result.image_data if canvas_result else None,
            uploaded_file=firma_subida,
        )

        if b64_firma:
            st.session_state["firmas_tactiles_db"].append({
                "paciente": paciente_sel,
                "fecha": ahora().strftime("%d/%m/%Y %H:%M"),
                "firma_img": b64_firma,
            })
            guardar_datos()
            st.toast("Firma guardada correctamente.", icon="✅")
            st.rerun()
        else:
            st.error("No se detectó una firma válida. Sube una foto o usa el lienzo.")


def _render_formulario_evolucion(paciente_sel: str, user: Dict[str, Any]) -> None:
    """Renderiza el formulario para registrar una nueva evolución médica o interdisciplinaria."""
    with st.form("evol_form", clear_on_submit=True):
        st.markdown("##### Nueva Evolución")
        plantilla = st.selectbox("Especialidad del Profesional", list(PLANTILLAS_EVOLUCION.keys()))
        
        if plantilla != "Libre":
            st.caption(f"Guía sugerida para {plantilla}. Puedes modificar el texto como necesites.")
            
        nota = st.text_area(
            "Nota médica / Evolución clínica",
            value=PLANTILLAS_EVOLUCION.get(plantilla, ""),
            height=220,
            placeholder="Escribir aquí la evolución...",
        )
        
        col_foto1, col_foto2 = st.columns([3, 1])
        desc_w = col_foto1.text_input("Descripción de la herida / lesión (Opcional)")

        with col_foto2:
            st.markdown("Foto de control")
            usar_camara = st.checkbox("Encender cámara")
            foto_w = st.camera_input("Tomar foto ahora", key="cam_evol") if usar_camara else None

        if st.form_submit_button("Firmar y Guardar Evolución", use_container_width=True, type="primary"):
            if not nota.strip():
                st.error("La nota médica no puede estar vacía.")
                return
                
            fecha_n = ahora().strftime("%d/%m/%Y %H:%M")
            profesional_nombre = user.get("nombre", "Usuario Desconocido")
            
            # 1. Guardar Evolución
            st.session_state["evoluciones_db"].append({
                "paciente": paciente_sel,
                "nota": nota.strip(),
                "fecha": fecha_n,
                "firma": profesional_nombre,
                "plantilla": plantilla,
            })

            # 2. Guardar Foto (si aplica)
            if foto_w is not None:
                foto_bytes, _ = optimizar_imagen_bytes(foto_w.getvalue(), max_size=(1280, 1280), quality=70)
                st.session_state["fotos_heridas_db"].append({
                    "paciente": paciente_sel,
                    "fecha": fecha_n,
                    "descripcion": desc_w.strip(),
                    "base64_foto": base64.b64encode(foto_bytes).decode("utf-8"),
                    "firma": profesional_nombre,
                })

            # 3. Auditoría y Persistencia
            registrar_auditoria_legal(
                "Evolución Clínica",
                paciente_sel,
                "Nueva evolución",
                profesional_nombre,
                user.get("matricula", ""),
                f"Especialidad: {plantilla} | Foto adjunta: {'Sí' if foto_w else 'No'}",
            )
            guardar_datos()
            st.toast("Evolución clínica guardada en la historia.", icon="✅")
            st.rerun()


def _render_historial_evoluciones(evs_paciente: List[Dict[str, Any]], paciente_sel: str, user: Dict[str, Any]) -> None:
    """Muestra el historial anticolapso de todas las evoluciones con controles de edición/borrado por autor."""
    st.divider()
    st.markdown("#### Historial de Evoluciones Clínicas")
    
    limite_evol = seleccionar_limite_registros(
        "Evoluciones a mostrar", len(evs_paciente),
        key=f"limite_evol_{paciente_sel}", default=30, opciones=(10, 30, 50, 100)
    )
    
    registros_mostrar = evs_paciente[-limite_evol:]
    st.caption(f"Mostrando {len(registros_mostrar)} de {len(evs_paciente)} evoluciones (Vista global interdisciplinaria).")
    
    # Contenedor con SCROLL ACTIVO para anti-colapso (height=560)
    with st.container(height=560):
        for ev in reversed(registros_mostrar):
            real_index = st.session_state["evoluciones_db"].index(ev)
            
            with st.container(border=True):
                col_cab1, col_cab2 = st.columns([3, 1])
                col_cab1.markdown(f"**🗓️ {ev.get('fecha', 'S/D')}** | 🩺 **{ev.get('firma', 'Profesional S/D')}**")
                
                if plantilla := ev.get("plantilla"):
                    if plantilla != "Libre":
                        col_cab2.caption(f"_{plantilla}_")
                
                # --- Lógica Estricta de 30 minutos y Autoría ---
                editable, mins_restantes = _es_editable(ev.get("fecha", ""), ev.get("firma", ""), user.get("nombre", ""))
                edit_state_key = f"edit_mode_{real_index}"
                
                if st.session_state.get(edit_state_key, False):
                    # --- MODO EDICIÓN ---
                    nueva_nota = st.text_area("Editar contenido", value=ev.get("nota", ""), height=150, key=f"text_edit_{real_index}")
                    col_e1, col_e2 = st.columns(2)
                    
                    if col_e1.button("Guardar Cambios", key=f"save_{real_index}", type="primary"):
                        marca_edicion = f"\n\n*(Editado: {ahora().strftime('%H:%M')})*"
                        st.session_state["evoluciones_db"][real_index]["nota"] = nueva_nota.strip() + marca_edicion
                        st.session_state[edit_state_key] = False
                        
                        registrar_auditoria_legal(
                            "Evolución Clínica", paciente_sel, "Edición de evolución",
                            user.get("nombre", ""), user.get("matricula", ""),
                            f"Evolución original de {ev.get('fecha')} editada.",
                        )
                        guardar_datos()
                        st.rerun()
                        
                    if col_e2.button("Cancelar", key=f"cancel_{real_index}"):
                        st.session_state[edit_state_key] = False
                        st.rerun()
                else:
                    # --- MODO LECTURA ---
                    st.write(ev.get("nota", "Sin contenido registrado."))
                    
                    # Botones de acción (Solo visibles si es el autor y pasaron < 30 min)
                    if editable:
                        st.divider()
                        col_btn1, col_btn2, col_btn3 = st.columns([2, 2, 3])
                        
                        # Acción Editar
                        if col_btn1.button(f"✏️ Editar ({mins_restantes} min)", key=f"btn_edit_{real_index}"):
                            st.session_state[edit_state_key] = True
                            st.rerun()
                            
                        # Acción Borrar (Protegida por checkbox)
                        chk_borrar = col_btn2.checkbox("Habilitar borrado", key=f"chk_del_{real_index}")
                        if col_btn3.button("🗑️ Borrar registro", key=f"btn_del_{real_index}", type="primary", disabled=not chk_borrar):
                            st.session_state["evoluciones_db"].pop(real_index)
                            registrar_auditoria_legal(
                                "Evolución Clínica", paciente_sel, "Borrado de evolución",
                                user.get("nombre", ""), user.get("matricula", ""),
                                f"Evolución de las {ev.get('fecha')} eliminada por su autor.",
                            )
                            guardar_datos()
                            st.toast("Evolución eliminada con éxito.", icon="🗑️")
                            st.rerun()


def _render_historial_fotos(fotos_heridas: List[Dict[str, Any]], paciente_sel: str) -> None:
    """Muestra el timeline fotográfico (heridas y lesiones) con lazy loading y scroll."""
    st.divider()
    st.markdown("#### Línea de tiempo de heridas y lesiones")
    
    limite_fotos = seleccionar_limite_registros(
        "Fotos a mostrar", len(fotos_heridas),
        key=f"limite_fotos_heridas_{paciente_sel}", default=12, opciones=(6, 12, 24, 50),
    )
    
    registros_fotos = fotos_heridas[-limite_fotos:]
    st.caption(f"Mostrando {len(registros_fotos)} de {len(fotos_heridas)} fotos registradas.")

    with st.container(height=600):
        for foto in reversed(registros_fotos):
            with st.container(border=True):
                st.markdown(f"**{foto.get('fecha', 'S/D')}** | Registrado por: **{foto.get('firma', 'S/D')}**")
                if descripcion := foto.get("descripcion"):
                    st.caption(descripcion)
                    
                if base64_foto := foto.get("base64_foto"):
                    try:
                        st.image(base64.b64decode(base64_foto), use_container_width=True)
                    except Exception:
                        st.error("Archivo de imagen corrupto o no disponible.")


# --- Función Principal (Enrutador) ---
def render_evolucion(paciente_sel: str, user: Dict[str, Any], rol: str = None) -> None:
    if not paciente_sel:
        st.info("Selecciona un paciente en el menú lateral.")
        return

    rol_actual = rol or user.get("rol", "")
    puede_registrar = puede_accion(rol_actual, "evolucion_registrar")

    st.subheader("Evolución Médica e Interdisciplinaria")

    _render_captura_firma(paciente_sel)
    st.divider()

    if puede_registrar:
        _render_formulario_evolucion(paciente_sel, user)
    else:
        st.caption("La carga de nuevas evoluciones está deshabilitada para tu perfil.")

    # Recuperación Global de Datos
    evs_paciente = [e for e in st.session_state.get("evoluciones_db", []) if e.get("paciente") == paciente_sel]
    if evs_paciente:
        _render_historial_evoluciones(evs_paciente, paciente_sel, user)
    else:
        st.info("Aún no hay evoluciones registradas para este paciente en el sistema.")

    fotos_heridas = [f for f in st.session_state.get("fotos_heridas_db", []) if f.get("paciente") == paciente_sel]
    if fotos_heridas:
        _render_historial_fotos(fotos_heridas, paciente_sel)
