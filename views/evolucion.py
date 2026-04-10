import base64
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

# --- Constantes y Configuración ---
PLANTILLAS_EVOLUCION = {
    "Libre": "",
    "Clínica general": "Motivo de la visita:\nSignos relevantes:\nConducta indicada:\nRespuesta del paciente:\nPlan y seguimiento:",
    "Enfermería": "Procedimiento realizado:\nEstado general del paciente:\nSitio de acceso / curación:\nTolerancia al procedimiento:\nIndicaciones para el próximo control:",
    "Heridas": "Ubicación de la lesión:\nAspecto del lecho:\nExudado / olor:\nCuración aplicada:\nEvolución respecto al control previo:",
    "Respiratorio": "Saturación actual:\nDispositivo / flujo de oxígeno:\nTrabajo respiratorio:\nAuscultación:\nConducta y seguimiento:",
    "Pediatría": "Motivo de consulta:\nPeso / talla / temperatura:\nAlimentación / hidratación:\nEvaluación general:\nPlan y recomendaciones:",
    "Cuidados paliativos": "Síntomas predominantes:\nDolor / confort:\nApoyo familiar:\nIntervenciones realizadas:\nPlan para las próximas horas:",
}

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
    """Renderiza el formulario para registrar una nueva evolución médica o de enfermería."""
    with st.form("evol_form", clear_on_submit=True):
        st.markdown("##### Nueva Evolución")
        plantilla = st.selectbox("Plantilla de evolución", list(PLANTILLAS_EVOLUCION.keys()))
        
        if plantilla != "Libre":
            st.caption("Se carga una guía sugerida para agilizar el registro y mantener el formato clínico.")
            
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
                f"Plantilla: {plantilla} | Foto adjunta: {'Sí' if foto_w else 'No'}",
            )
            guardar_datos()
            st.toast("Evolución clínica guardada en la historia.", icon="✅")
            st.rerun()


def _render_historial_evoluciones(evs_paciente: List[Dict[str, Any]], paciente_sel: str, user: Dict[str, Any], puede_borrar: bool) -> None:
    """Muestra el historial anticolapso de todas las evoluciones del paciente."""
    st.divider()
    col_tit, col_btn = st.columns([3, 1])
    col_tit.markdown("#### Historial de Evoluciones Clínicas")
    
    # Lógica corregida para borrar el último registro de forma segura
    if puede_borrar:
        with col_btn:
            confirmar = st.checkbox("Habilitar borrado", key="conf_del_evol")
            if st.button("Borrar última evolución", use_container_width=True, disabled=not confirmar):
                ultima = evs_paciente[-1]
                st.session_state["evoluciones_db"].remove(ultima)
                registrar_auditoria_legal(
                    "Evolución Clínica", paciente_sel, "Borrado de evolución",
                    user.get("nombre", ""), user.get("matricula", ""),
                    f"Se eliminó la evolución del {ultima.get('fecha', 'S/D')}.",
                )
                guardar_datos()
                st.toast("Evolución eliminada con éxito.", icon="🗑️")
                st.rerun()
    else:
        st.caption("Borrado reservado a coordinación médica o administración.")

    limite_evol = seleccionar_limite_registros(
        "Evoluciones a mostrar", len(evs_paciente),
        key=f"limite_evol_{paciente_sel}", default=30, opciones=(10, 30, 50, 100)
    )
    
    registros_mostrar = evs_paciente[-limite_evol:]
    st.caption(f"Mostrando {len(registros_mostrar)} de {len(evs_paciente)} evoluciones (Vista global compartida).")
    
    # Contenedor con scroll para evitar colapso visual
    with st.container(height=560):
        for ev in reversed(registros_mostrar):
            with st.container(border=True):
                col_cab1, col_cab2 = st.columns([3, 1])
                col_cab1.markdown(f"**🗓️ {ev.get('fecha', 'S/D')}** | 🩺 **{ev.get('firma', 'Profesional S/D')}**")
                
                if plantilla := ev.get("plantilla"):
                    if plantilla != "Libre":
                        col_cab2.caption(f"_{plantilla}_")
                        
                st.write(ev.get("nota", "Sin contenido registrado."))


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
    puede_borrar = puede_accion(rol_actual, "evolucion_borrar")

    st.subheader("Evolución Médica e Interdisciplinaria")

    _render_captura_firma(paciente_sel)
    st.divider()

    if puede_registrar:
        _render_formulario_evolucion(paciente_sel, user)
    else:
        st.caption("La carga de nuevas evoluciones está deshabilitada para tu perfil.")

    # Recuperación Global de Datos
    # Se obtienen TODAS las evoluciones de la DB filtrando solo por paciente (no por usuario)
    # Esto asegura que todos los profesionales vean las notas de los demás.
    evs_paciente = [e for e in st.session_state.get("evoluciones_db", []) if e.get("paciente") == paciente_sel]
    if evs_paciente:
        _render_historial_evoluciones(evs_paciente, paciente_sel, user, puede_borrar)
    else:
        st.info("Aún no hay evoluciones registradas para este paciente en el sistema.")

    fotos_heridas = [f for f in st.session_state.get("fotos_heridas_db", []) if f.get("paciente") == paciente_sel]
    if fotos_heridas:
        _render_historial_fotos(fotos_heridas, paciente_sel)
