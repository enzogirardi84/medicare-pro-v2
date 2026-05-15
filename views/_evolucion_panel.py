"""Panel de evolución clínica. Extraído de views/evolucion.py."""
import base64
import html

import streamlit as st
from core._exports_history import build_history_pdf_bytes
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





def _generar_pdf_historia_clinica(paciente_sel):
    """Genera bytes del PDF de historia clínica usando build_history_pdf_bytes."""
    detalles = st.session_state.get("db", {})
    mi_empresa = detalles.get("empresa", "")
    profesional = st.session_state.get("user", "")
    if isinstance(profesional, dict):
        profesional = profesional.get("nombre", "") or profesional.get("username", "")
    try:
        return build_history_pdf_bytes(
            st.session_state, paciente_sel, mi_empresa, profesional=profesional
        )
    except Exception as exc:
        st.error(f"Error generando PDF: {exc}")
        return None


def _render_panel_evolucion_clinica(paciente_sel, user, puede_registrar, puede_borrar):
    st.markdown("##### Evolución clínica")

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
        "Percentilo": "Motivo de consulta:\nPeso / talla / temperatura:\nAlimentacion / hidratacion:\nEvaluacion general:\nPlan y recomendaciones:",
        "Cuidados paliativos": "Sintomas predominantes:\nDolor / confort:\nApoyo familiar:\nIntervenciones realizadas:\nPlan para las proximas horas:",
    }

    if puede_registrar:
        evs_all = [e for e in st.session_state.get("evoluciones_db", []) if e.get("paciente") == paciente_sel]
        if evs_all:
            ultima_ev = max(evs_all, key=lambda x: x.get("fecha", ""))
            _c1, _c2, _c3 = st.columns(3)
            _c1.metric("Última evolución", ultima_ev.get("fecha", "S/D"))
            _c2.metric("Profesional", (ultima_ev.get("firma") or "S/D"))
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

            if st.form_submit_button("Firmar y Guardar Evolucion", width='stretch', type="primary"):
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
        st.markdown("#### Historial de Evoluciones Clinicas", unsafe_allow_html=True)

        busqueda_evol = st.text_input(
            "Buscar en notas",
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

        # Botón para descargar PDF de historia clínica
        c1, c2 = st.columns([0.7, 0.3])
        with c1:
            st.markdown(f"**{len(evs_paciente)} evolución(es)**")
        with c2:
            if st.button("Descargar PDF", key=f"btn_pdf_historial_{paciente_sel}", type="primary"):
                pdf_bytes = _generar_pdf_historia_clinica(paciente_sel)
                if pdf_bytes:
                    st.download_button(
                        label="Descargar PDF",
                        data=pdf_bytes,
                        file_name=f"Historia_Clinica_{paciente_sel.replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        key=f"download_pdf_historial_{paciente_sel}",
                    )

        # Historial de Evoluciones (expanders individuales)
        st.markdown("#### Historial de Evoluciones", unsafe_allow_html=True)
        total_evs = len(evs_paciente)
        for idx, ev in enumerate(reversed(evs_paciente[-limite_evol:])):
            ev_num = total_evs - idx
            fecha = str(ev.get("fecha", ""))[:16]
            plantilla = ev.get("plantilla", "Sin plantilla")
            nota = str(ev.get("nota", ""))
            firma = str(ev.get("firma", ""))
            es_urgente = ev.get("urgente", False) or "urgente" in nota.lower()

            with st.expander(f"Evolución #{ev_num} — {fecha} — {plantilla}"):
                if es_urgente:
                    st.error("Marcada como URGENTE")
                st.markdown(f"**Fecha:** `{fecha}`", unsafe_allow_html=True)
                if plantilla:
                    st.markdown(f"**Plantilla:** {html.escape(plantilla)}", unsafe_allow_html=True)
                if nota:
                    st.markdown("**Nota:**", unsafe_allow_html=True)
                    st.markdown(html.escape(nota), unsafe_allow_html=True)
                if firma and firma.strip():
                    st.success("Firmado digitalmente")

                # Botón borrar esta evolución específica
                btn_key = f"borrar_ev_especifica_{ev_num}_{idx}_{paciente_sel}"
                if st.button("Borrar esta evolución", key=btn_key, type="secondary"):
                    real_idx = (total_evs - 1) - idx
                    if 0 <= real_idx < len(evs_paciente):
                        ev_borrada = evs_paciente.pop(real_idx)
                        st.session_state["evoluciones_db"] = evs_paciente
                        guardar_datos()
                        st.toast(f"Evolución #{ev_num} eliminada.", icon="🗑️")
                        try:
                            registrar_auditoria_legal(
                                "EVOLUCION_BORRADA",
                                paciente_sel,
                                detalles={
                                    "fecha": ev_borrada.get("fecha"),
                                    "plantilla": ev_borrada.get("plantilla"),
                                    "responsable": user.get("nombre", ""),
                                },
                            )
                        except Exception as _aud_exc:
                            from core.app_logging import log_event
                            log_event("evolucion_panel", f"auditoria_falla:{type(_aud_exc).__name__}:{_aud_exc}")
                        st.rerun()

        # Botón tradicional: Borrar última evolución
        col_chk, col_btn = st.columns([1.2, 2.8])
        confirmar_borrado = col_chk.checkbox("Confirmar", key=f"conf_del_evol_{paciente_sel}")
        if col_btn.button("Borrar ultima evolucion", width='stretch', disabled=not confirmar_borrado):
            if not evs_paciente:
                st.error("No hay evoluciones para borrar.")
            else:
                ultima = evs_paciente[-1]
                try:
                    st.session_state["evoluciones_db"].remove(evs_paciente[-1])
                except ValueError:
                    pass
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
                        st.image(base64.b64decode(foto.get("base64_foto", "")), width='stretch')
                    except Exception:
                        st.warning("No se pudo mostrar una foto registrada.")

    st.divider()
    st.markdown("##### Firma Digital del Paciente / Familiar")
    st.caption("Solicitar firma al finalizar la consulta, después de completar la evolución clínica.")
    if CANVAS_DISPONIBLE:
        firma_cfg = obtener_config_firma("evolucion")
        metodo_firma = st.radio(
            "Método de firma",
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
            st.caption("Usá el lienzo solo si el teléfono responde fluido.")
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

        if st.button("Guardar Firma Digital", width='stretch', type="primary"):
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
                st.error("No se detectó una firma válida. Podés subir una foto o usar el lienzo.")
    else:
        st.warning("Librería de firma no disponible. Podés subir una imagen de la firma.")
        st.file_uploader(
            "Subir imagen de la firma",
            type=["png", "jpg", "jpeg"],
            key="firma_upload_evolucion_sin_canvas",
        )
