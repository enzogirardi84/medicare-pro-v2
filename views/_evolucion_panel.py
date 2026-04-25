"""Panel de evolución clínica. Extraído de views/evolucion.py."""
import base64
import html

import streamlit as st
from core.alert_toasts import queue_toast
from core.database import guardar_datos
from core.guardado_universal import guardar_registro
from core.view_helpers import bloque_estado_vacio, bloque_mc_grid_tarjetas, lista_plegable
from core.ui_components import (
    badge,
    timeline_item,
    medical_card,
    status_dot,
    text_gradient,
)
from core.utils import (
    ahora,
    firma_a_base64,
    obtener_config_firma,
    optimizar_imagen_bytes,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)

# Lazy import canvas
_canvas = None


def get_canvas():
    global _canvas
    if _canvas is None:
        try:
            from streamlit_drawable_canvas import st_canvas
            _canvas = st_canvas
        except ImportError:
            _canvas = False
    return _canvas


st_canvas = get_canvas()
CANVAS_DISPONIBLE = bool(st_canvas)


def _historial_evoluciones_scroll_interno(evs_mas_recientes_primero, altura_iframe_px: int = 520):
    """
    Historial en iframe con altura fija: el scroll vive adentro (Streamlit suele romper overflow en st.markdown).
    USA NUEVO SISTEMA DE TIMELINE CLÍNICO con componentes mc-*.
    """
    timeline_items = []
    for i, ev in enumerate(evs_mas_recientes_primero):
        fecha = str(ev.get("fecha", ""))
        firma = str(ev.get("firma", ""))
        nota = str(ev.get("nota", ""))
        plantilla = ev.get("plantilla")
        es_urgente = ev.get("urgente", False) or "urgente" in nota.lower()
        
        # Determinar status del item
        status = "critico" if es_urgente else "normal"
        
        # Construir contenido
        contenido = nota[:300] + "..." if len(nota) > 300 else nota
        if plantilla:
            contenido = f'<span class="mc-badge mc-badge-info">{html.escape(str(plantilla))}</span><br>{contenido}'
        
        timeline_items.append({
            "date": fecha,
            "title": f"Evolución - {html.escape(firma)}",
            "content": contenido,
            "status": status,
        })
    
    # Construir timeline HTML con las nuevas clases CSS
    timeline_html = []
    timeline_html.append('<div class="mc-timeline">')
    for item in timeline_items:
        status_class = item["status"] if item["status"] in ["critico", "mejora"] else ""
        timeline_html.append(f'''
        <div class="mc-timeline-item {status_class}">
            <div class="mc-timeline-header">
                <span class="mc-timeline-date">{item["date"]}</span>
            </div>
            <h4 class="mc-timeline-title">{item["title"]}</h4>
            <div class="mc-timeline-content">{item["content"]}</div>
        </div>
        ''')
    timeline_html.append('</div>')
    
    timeline_str = "\n".join(timeline_html)
    
    # Incluir todas las clases CSS del sistema de componentes
    doc = f"""<!DOCTYPE html>
<html lang="es"><head><meta charset="utf-8"/>
<style>
  html, body {{ margin:0; height:100%; background:#0f172a; font-family:system-ui,-apple-system,sans-serif; }}
  .mc-evol-scroll {{
    height:100%; box-sizing:border-box; overflow-y:auto; overflow-x:hidden;
    -webkit-overflow-scrolling:touch; overscroll-behavior:contain;
    padding:16px; border:1px solid rgba(148,163,184,0.4); border-radius:10px;
    background:rgba(30,41,59,0.5);
  }}
  /* Timeline clínico */
  .mc-timeline {{
    position: relative;
    padding-left: 1.5rem;
  }}
  .mc-timeline::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 2px;
    background: linear-gradient(180deg, #3b82f6 0%, #22c55e 50%, #94a3b8 100%);
    border-radius: 2px;
  }}
  .mc-timeline-item {{
    position: relative;
    padding-bottom: 1.25rem;
    padding-left: 1rem;
  }}
  .mc-timeline-item::before {{
    content: "";
    position: absolute;
    left: -1.625rem;
    top: 0.25rem;
    width: 10px;
    height: 10px;
    border-radius: 50%;
    background: #3b82f6;
    border: 2px solid #0f172a;
    box-shadow: 0 0 0 2px #3b82f6;
  }}
  .mc-timeline-item.critico::before {{
    background: #ef4444;
    box-shadow: 0 0 0 2px #ef4444;
    animation: pulse-dot 2s ease-in-out infinite;
  }}
  @keyframes pulse-dot {{
    0%, 100% {{ box-shadow: 0 0 0 2px #ef4444, 0 0 0 4px rgba(239, 68, 68, 0.3); }}
    50% {{ box-shadow: 0 0 0 2px #ef4444, 0 0 0 8px rgba(239, 68, 68, 0.1); }}
  }}
  .mc-timeline-header {{
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
  }}
  .mc-timeline-date {{
    font-size: 0.75rem;
    color: #64748b;
    font-weight: 500;
  }}
  .mc-timeline-title {{
    font-size: 0.9rem;
    font-weight: 600;
    color: #f1f5f9;
    margin: 0 0 0.5rem 0;
  }}
  .mc-timeline-content {{
    font-size: 0.85rem;
    color: #94a3b8;
    line-height: 1.6;
    background: rgba(30, 41, 59, 0.4);
    padding: 0.75rem;
    border-radius: 6px;
    border-left: 3px solid #3b82f6;
    white-space: pre-wrap;
    word-break: break-word;
  }}
  /* Badges */
  .mc-badge {{
    display: inline-flex;
    align-items: center;
    gap: 0.375rem;
    padding: 0.25rem 0.625rem;
    border-radius: 9999px;
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.025em;
    text-transform: uppercase;
    white-space: nowrap;
    border: 1px solid transparent;
    margin-bottom: 0.5rem;
  }}
  .mc-badge-info {{
    background: rgba(59, 130, 246, 0.12);
    color: #3b82f6;
    border-color: rgba(59, 130, 246, 0.25);
  }}
  /* Scrollbar */
  ::-webkit-scrollbar {{ width: 6px; height: 6px; }}
  ::-webkit-scrollbar-track {{ background: rgba(15, 23, 42, 0.5); border-radius: 3px; }}
  ::-webkit-scrollbar-thumb {{ background: rgba(100, 116, 139, 0.5); border-radius: 3px; }}
</style></head><body>
<div class="mc-evol-scroll">{timeline_str}</div>
</body></html>"""

    st.html(doc, height=altura_iframe_px, scrolling=False)


def _render_panel_evolucion_clinica(paciente_sel, user, puede_registrar, puede_borrar):
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Evolución clínica</h2>
            <p class="mc-hero-text">Acá documentan <strong>todos los profesionales</strong> (médicos, enfermería, operativos): notas de evolución, cambios del paciente,
            curaciones en texto y <strong>fotos de heridas, lesiones o hallazgos</strong>. Firma del paciente o familiar opcional; en celulares viejos conviene foto de firma antes que el lienzo.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Multidisciplina</span>
                <span class="mc-chip">Plantillas clínicas</span>
                <span class="mc-chip">Fotos clínicas</span>
                <span class="mc-chip">Auditoría legal</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Notas", "Evolución con plantillas: clínica general, Enfermería, Heridas, respiratorio, etc."),
            ("Imágenes", "Cámara o archivo desde el teléfono (heridas, dispositivos, evolución visual)."),
            ("Firma", "Opcional: foto de firma o lienzo si el equipo lo permite."),
        ]
    )
    st.caption(
        "Podés registrar primero la firma (opcional). En el formulario: plantilla, nota y **fotografía clínica** (subir archivo o usar cámara). "
        "Enfermería suele usar plantillas **Enfermería** o **Heridas**."
    )

    if CANVAS_DISPONIBLE:
        st.markdown("##### Firma Digital del Paciente / Familiar")
        firma_cfg = obtener_config_firma("evolucion")
        metodo_firma = st.radio(
            "Metodo de firma",
            ["Subir foto de la firma (recomendado en celulares viejos)", "Firmar en pantalla"],
            horizontal=False,
            key="metodo_firma_evolucion",
        )
        firma_subida = None
        canvas_result = None
        if metodo_firma.startswith("Subir"):
            firma_subida = st.file_uploader(
                "Subir imagen de la firma",
                type=["png", "jpg", "jpeg"],
                key="firma_upload_evolucion",
            )
        else:
            st.caption("Usa el lienzo solo si el telefono responde fluido.")
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

        if st.button("Guardar Firma Digital", use_container_width=True, type="primary"):
            b64_firma = firma_a_base64(
                canvas_image_data=canvas_result.image_data if canvas_result is not None else None,
                uploaded_file=firma_subida,
            )
            if b64_firma:
                if "firmas_tactiles_db" not in st.session_state or not isinstance(st.session_state["firmas_tactiles_db"], list):
                    st.session_state["firmas_tactiles_db"] = []
                st.session_state["firmas_tactiles_db"].append({
                    "paciente": paciente_sel,
                    "fecha": ahora().strftime("%d/%m/%Y %H:%M"),
                    "firma_img": b64_firma,
                })
                from core.database import _trim_db_list
                _trim_db_list("firmas_tactiles_db", 200)
                guardar_datos(spinner=True)
                queue_toast("Firma guardada correctamente.")
                st.rerun()
            else:
                st.error("No se detecto una firma valida. Puedes subir una foto o usar el lienzo.")
    else:
        st.warning("Libreria de firma no disponible. Puedes subir una imagen de la firma.")
        st.file_uploader(
            "Subir imagen de la firma",
            type=["png", "jpg", "jpeg"],
            key="firma_upload_evolucion_sin_canvas",
        )

    st.divider()

    plantillas_evolucion = {
        "Libre": "",
        "Clinica general": "Motivo de la visita:\nSignos relevantes:\nConducta indicada:\nRespuesta del paciente:\nPlan y seguimiento:",
        "SOAP": "S - Subjetivo (motivo / síntomas referidos):\nO - Objetivo (signos, examen físico):\nA - Evaluación / Diagnóstico:\nP - Plan y conducta:",
        "Enfermeria": "Procedimiento realizado:\nEstado general del paciente:\nSitio de acceso / curación:\nTolerancia al procedimiento:\nIndicaciones para el próximo control:",
        "Heridas": "Ubicación de la lesión:\nAspecto del lecho:\nExudado / olor:\nCuración aplicada:\nEvolución respecto al control previo:\n(Opcional: adjuntar foto con la cámara o un archivo debajo)",
        "Respiratorio": "Saturacion actual:\nDispositivo / flujo de oxigeno:\nTrabajo respiratorio:\nAuscultacion:\nConducta y seguimiento:",
        "EPOC / Asma": "Disnea (escala 0-10):\nUso de musculatura accesoria:\nSaturación / FEV1 estimado:\nBroncoespasmo / sibilancias:\nMedicación broncodilatadora aplicada:\nRespuesta y plan:",
        "Neurológico / ACV": "Nivel de conciencia (GCS):\nFuerza y sensibilidad por miembro:\nLenguaje / afasia:\nNIHSS estimado:\nImagen solicitada:\nConducta y derivación:",
        "Post-procedimiento": "Procedimiento realizado:\nAcceso / zona intervenida:\nComplicaciones inmediatas:\nEstado hemodinámico post:\nIndicaciones y cuidados:\nPróximo control:",
        "Seguimiento crónico": "Diagnóstico de base:\nCumplimiento del tratamiento:\nSignos / síntomas actuales:\nLaboratorio / estudios recientes:\nAjuste de medicación:\nFecha próximo control:",
        "Pediatria": "Motivo de consulta:\nPeso / talla / temperatura:\nAlimentacion / hidratacion:\nEvaluacion general:\nPlan y recomendaciones:",
        "Cuidados paliativos": "Sintomas predominantes:\nDolor / confort:\nApoyo familiar:\nIntervenciones realizadas:\nPlan para las proximas horas:",
    }

    if puede_registrar:
        evs_all = [e for e in st.session_state.get("evoluciones_db", []) if e.get("paciente") == paciente_sel]
        if evs_all:
            ultima_ev = max(evs_all, key=lambda x: x.get("fecha", ""))
            _c1, _c2, _c3 = st.columns(3)
            _c1.metric("Última evolución", ultima_ev.get("fecha", "S/D"))
            _c2.metric("Profesional", (ultima_ev.get("firma") or "S/D")[:28])
            _c3.metric("Total evoluciones", len(evs_all))

        plantilla = st.selectbox(
            "Plantilla de evolucion",
            list(plantillas_evolucion.keys()),
            key="evol_plantilla_sel"
        )
        plantilla_prev = st.session_state.get("evol_plantilla_prev", "Libre")
        if plantilla != plantilla_prev:
            st.session_state["evol_nota_draft"] = plantillas_evolucion.get(plantilla, "")
            st.session_state["evol_plantilla_prev"] = plantilla
        if plantilla != "Libre":
            st.caption("Se carga una guia sugerida. Podés editarla antes de guardar.")

        st.caption("Acceso rápido:")
        _btns = st.columns(5)
        _acceso_rapido = [
            ("SOAP", "SOAP"),
            ("Enfermería", "Enfermeria"),
            ("Heridas", "Heridas"),
            ("EPOC", "EPOC / Asma"),
            ("Post-proc.", "Post-procedimiento"),
        ]
        for idx, (label, key_pl) in enumerate(_acceso_rapido):
            if _btns[idx].button(label, key=f"qpl_{key_pl}", use_container_width=True):
                st.session_state["evol_nota_draft"] = plantillas_evolucion[key_pl]
                st.session_state["evol_plantilla_prev"] = key_pl
                st.rerun()

        with st.form("evol", clear_on_submit=False):
            nota = st.text_area(
                "Nota medica / Evolucion clinica",
                value=st.session_state.get("evol_nota_draft", ""),
                height=220,
                placeholder="Escribir aqui la evolucion...",
                key="evol_nota_textarea"
            )
            desc_w = st.text_input("Descripción de la herida / lesión / imagen clínica (opcional)")
            st.markdown("**Fotografía clínica** (herida, lesión, punto de acceso, etc.) — una sola imagen por guardado.")
            col_up, col_cam = st.columns(2)
            with col_up:
                archivo_foto = st.file_uploader(
                    "Subir foto desde el dispositivo (galería o archivos)",
                    type=["png", "jpg", "jpeg", "webp"],
                    key="evol_foto_archivo",
                )
            with col_cam:
                usar_camara = st.checkbox("Usar cámara ahora", key="evol_usar_cam")
                foto_cam = st.camera_input("Capturar imagen", key="cam_evol") if usar_camara else None

            if st.form_submit_button("Firmar y Guardar Evolucion", use_container_width=True, type="primary"):
                if nota.strip():
                    fecha_n = ahora().strftime("%d/%m/%Y %H:%M")
                    if "evoluciones_db" not in st.session_state or not isinstance(st.session_state["evoluciones_db"], list):
                        st.session_state["evoluciones_db"] = []
                    st.session_state["evoluciones_db"].append({
                        "paciente": paciente_sel,
                        "nota": nota.strip(),
                        "fecha": fecha_n,
                        "firma": user.get("nombre", "Sistema"),
                        "plantilla": plantilla,
                    })
                    from core.database import _trim_db_list
                    _trim_db_list("evoluciones_db", 500)

                    raw_foto = None
                    if archivo_foto is not None:
                        raw_foto = archivo_foto.getvalue()
                    elif foto_cam is not None:
                        raw_foto = foto_cam.getvalue()

                    if raw_foto:
                        foto_bytes, _ = optimizar_imagen_bytes(raw_foto, max_size=(1280, 1280), quality=70)
                        base64_foto = base64.b64encode(foto_bytes).decode("utf-8")
                        if "fotos_heridas_db" not in st.session_state or not isinstance(st.session_state["fotos_heridas_db"], list):
                            st.session_state["fotos_heridas_db"] = []
                        st.session_state["fotos_heridas_db"].append({
                            "paciente": paciente_sel,
                            "fecha": fecha_n,
                            "descripcion": desc_w.strip(),
                            "base64_foto": base64_foto,
                            "firma": user.get("nombre", "Sistema"),
                        })
                        _trim_db_list("fotos_heridas_db", 100)

                    registrar_auditoria_legal(
                        "Evolucion Clinica",
                        paciente_sel,
                        "Nueva evolucion",
                        user.get("nombre", ""),
                        user.get("matricula", ""),
                        f"Se registro evolucion con plantilla {plantilla}.",
                    )
                    guardar_datos(spinner=True)

                    try:
                        paciente_nombre = paciente_sel
                        paciente_id = paciente_sel
                        if isinstance(paciente_sel, str) and " - " in paciente_sel:
                            partes = paciente_sel.split(" - ")
                            paciente_nombre = " - ".join(partes[:-1])
                            paciente_id = partes[-1]
                        exito_local, mensaje_local = guardar_registro(
                            tipo="evoluciones",
                            paciente_id=paciente_id,
                            paciente_nombre=paciente_nombre,
                            datos={
                                "evolucion": nota.strip(),
                                "plantilla": plantilla,
                                "indicaciones": "",
                                "firma": user.get("nombre", "Sistema"),
                                "fecha": fecha_n
                            }
                        )
                        if exito_local:
                            from core.app_logging import log_event
                            log_event("evolucion", "guardado_local_ok")
                    except Exception as e_local:
                        from core.app_logging import log_event
                        log_event("evolucion", f"error_guardado_local:{type(e_local).__name__}")

                    try:
                        from core.nextgen_sync import sync_visita_evolucion_to_nextgen
                        sync_visita_evolucion_to_nextgen(paciente_sel, nota)
                    except Exception as e_nextgen:
                        from core.app_logging import log_event
                        log_event("evolucion", f"nextgen_sync_skip:{type(e_nextgen).__name__}")

                    queue_toast("Evolucion guardada correctamente.")
                    st.session_state["evol_nota_draft"] = ""
                    st.session_state["evol_plantilla_prev"] = "Libre"
                    st.rerun()
                else:
                    st.error("La nota medica no puede estar vacia.")
    else:
        st.caption("La carga de nuevas evoluciones queda deshabilitada para este rol.")

    from core.db_sql import get_evoluciones_by_paciente
    from core.nextgen_sync import _obtener_uuid_paciente, _obtener_uuid_empresa

    evs_paciente = []
    uso_sql = False

    try:
        partes = paciente_sel.split(" - ")
        if len(partes) > 1:
            dni = partes[1].strip()
            empresa = st.session_state.get("u_actual", {}).get("empresa", "Clinica General")
            empresa_id = _obtener_uuid_empresa(empresa)
            if empresa_id:
                pac_uuid = _obtener_uuid_paciente(dni, empresa_id)
                if pac_uuid:
                    evs_sql = get_evoluciones_by_paciente(pac_uuid)
                    uso_sql = True
                    for e in evs_sql:
                        fecha_raw = e.get("fecha_registro", "")
                        fecha_fmt = fecha_raw[:16].replace("T", " ") if fecha_raw else "S/D"
                        evs_paciente.append({
                            "paciente": paciente_sel,
                            "nota": e.get("nota", ""),
                            "fecha": fecha_fmt,
                            "firma": e.get("firma_medico", "Sistema"),
                            "plantilla": e.get("plantilla", "Libre")
                        })
    except Exception as e:
        from core.app_logging import log_event
        log_event("evoluciones_sql_error", f"Error: {e}")
        st.warning("⚠️ Usando datos locales (modo offline)")

    if not uso_sql:
        evs_paciente = [e for e in st.session_state.get("evoluciones_db", []) if e.get("paciente") == paciente_sel]

    if evs_paciente:
        st.divider()
        st.markdown("#### Historial de Evoluciones Clinicas")

        busqueda_evol = st.text_input(
            "🔍 Buscar en notas",
            placeholder="Palabras clave: diagnóstico, medicamento, profesional...",
            key=f"busq_evol_{paciente_sel}",
        ).strip().lower()
        if busqueda_evol:
            evs_paciente = [
                e for e in evs_paciente
                if busqueda_evol in str(e.get("nota", "")).lower()
                or busqueda_evol in str(e.get("firma", "")).lower()
                or busqueda_evol in str(e.get("plantilla", "")).lower()
                or busqueda_evol in str(e.get("fecha", "")).lower()
            ]
            st.caption(f"{len(evs_paciente)} resultado(s) para '{busqueda_evol}'")

        limite_evol = seleccionar_limite_registros(
            "Evoluciones a mostrar",
            len(evs_paciente),
            key=f"limite_evol_{paciente_sel}",
            default=20,
        )
        col_chk, col_btn = st.columns([1.2, 2.8])
        confirmar_borrado = col_chk.checkbox("Confirmar", key="conf_del_evol")
        if col_btn.button("Borrar ultima evolucion", use_container_width=True, disabled=not confirmar_borrado):
            if not evs_paciente:
                st.error("No hay evoluciones para borrar.")
            else:
                ultima = evs_paciente[-1]
                try:
                    st.session_state["evoluciones_db"].remove(evs_paciente[-1])
                except ValueError:
                    pass  # Intencional: item ya fue removido por otra operación concurrente
                registrar_auditoria_legal(
                    "Evolucion Clinica",
                    paciente_sel,
                    "Borrado de evolucion",
                    user.get("nombre", ""),
                    user.get("matricula", ""),
                    f"Evolucion borrada | Fecha: {ultima.get('fecha', 'S/D')}",
                    referencia=f"EVOL|{ultima.get('fecha', 'S/D')}",
                    empresa=mi_empresa,
                    usuario=user if isinstance(user, dict) else None,
                    modulo="Evolucion",
                    criticidad="alta",
                )
                guardar_datos(spinner=True)
                queue_toast("Evolucion borrada.")
                st.rerun()
            _historial_evoluciones_scroll_interno(list(reversed(evs_paciente[-limite_evol:])))
    else:
        bloque_estado_vacio(
            "Sin evoluciones todavía",
            "Este paciente no tiene evoluciones médicas registradas.",
            sugerencia="Usá el formulario de arriba para cargar la primera evolución con firma.",
        )

    fotos_heridas = [x for x in st.session_state.get("fotos_heridas_db", []) if x.get("paciente") == paciente_sel]
    if fotos_heridas:
        st.divider()
        st.markdown("#### Línea de tiempo de heridas y lesiones (fotos clínicas)")
        limite_fotos = seleccionar_limite_registros(
            "Fotos a mostrar",
            len(fotos_heridas),
            key=f"limite_fotos_heridas_{paciente_sel}",
            default=12,
            opciones=(6, 12, 20, 30),
        )
        with lista_plegable("Galería de fotos clínicas", count=min(limite_fotos, len(fotos_heridas)), expanded=False, height=520):
            for foto in reversed(fotos_heridas[-limite_fotos:]):
                with st.container(border=True):
                    st.markdown(f"**{foto.get('fecha', 'S/D')}** | **{foto.get('firma', 'Sin firma')}**")
                    if foto.get("descripcion"):
                        st.caption(foto.get("descripcion"))
                    try:
                        st.image(base64.b64decode(foto.get("base64_foto", "")), use_container_width=True)
                    except Exception:
                        st.warning("No se pudo mostrar una foto registrada.")
