"""Panel de evolución clínica."""

from __future__ import annotations

import base64
import html

import streamlit as st

from core._exports_history import build_history_pdf_bytes
from core._patient_index import get_patient_records
from core.alert_toasts import queue_toast
from core.app_logging import log_event
from core.database import guardar_datos
from core.seguridad import validate_uploaded_file, sanitize_for_log
from core.guardado_universal import guardar_registro
from core.utils import (
    ahora,
    firma_a_base64,
    obtener_config_firma,
    optimizar_imagen_bytes,
    registrar_auditoria_legal,
    seleccionar_limite_registros,
)
from core.ai_assistant import is_llm_enabled, get_evolution_assistant
from core.ai_features import ai_not_available_warning
from core.view_helpers import bloque_estado_vacio, lista_plegable
from views._tareas_panel import render_tareas_panel

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
    """Genera bytes del PDF de historia clínica."""
    detalles = st.session_state.get("db", {})
    mi_empresa = detalles.get("empresa", "")
    profesional = st.session_state.get("user", "")
    if isinstance(profesional, dict):
        profesional = profesional.get("nombre", "") or profesional.get("username", "")
    try:
        return build_history_pdf_bytes(
            st.session_state,
            paciente_sel,
            mi_empresa,
            profesional=profesional,
        )
    except Exception as exc:
        log_event("evolucion_panel", f"error_pdf:{type(exc).__name__}:{exc}")
        st.error(f"Error generando PDF: {exc}")
        return None


def _optimizar_foto_segura(raw_foto: bytes) -> bytes:
    """Normaliza la salida de optimizar_imagen_bytes, que puede devolver bytes o tupla."""
    resultado = optimizar_imagen_bytes(raw_foto, max_size=(1280, 1280), quality=70)
    if isinstance(resultado, tuple):
        return resultado[0]
    return resultado


def _render_panel_evolucion_clinica(paciente_sel, user, puede_registrar, puede_borrar):
    mi_empresa = user.get("empresa", "") if isinstance(user, dict) else ""
    profesional = user.get("nombre", "Sistema") if isinstance(user, dict) else "Sistema"
    _draft_key = f"_draft_evolucion_{paciente_sel}"

    st.markdown("##### Evolución clínica")
    st.divider()

    plantillas_evolucion = {
        "Libre": "",
        "Clínica general": "Motivo de la visita:\nSignos relevantes:\nConducta indicada:\nRespuesta del paciente:\nPlan y seguimiento:",
        "SOAP": "S - Subjetivo (motivo / síntomas referidos):\nO - Objetivo (signos, examen físico):\nA - Evaluación / Diagnóstico:\nP - Plan y conducta:",
        "Enfermería": "Procedimiento realizado:\nEstado general del paciente:\nSitio de acceso / curación:\nTolerancia al procedimiento:\nIndicaciones para el próximo control:",
        "Heridas": "Ubicación de la lesión:\nAspecto del lecho:\nExudado / olor:\nCuración aplicada:\nEvolución respecto al control previo:\n(Opcional: adjuntar foto con la cámara o un archivo debajo)",
        "Respiratorio": "Saturación actual:\nDispositivo / flujo de oxígeno:\nTrabajo respiratorio:\nAuscultación:\nConducta y seguimiento:",
        "EPOC / Asma": "Disnea (escala 0-10):\nUso de musculatura accesoria:\nSaturación / FEV1 estimado:\nBroncoespasmo / sibilancias:\nMedicación broncodilatadora aplicada:\nRespuesta y plan:",
        "Neurológico / ACV": "Nivel de conciencia (GCS):\nFuerza y sensibilidad por miembro:\nLenguaje / afasia:\nNIHSS estimado:\nImagen solicitada:\nConducta y derivación:",
        "Post-procedimiento": "Procedimiento realizado:\nAcceso / zona intervenida:\nComplicaciones inmediatas:\nEstado hemodinámico post:\nIndicaciones y cuidados:\nPróximo control:",
        "Seguimiento crónico": "Diagnóstico de base:\nCumplimiento del tratamiento:\nSignos / síntomas actuales:\nLaboratorio / estudios recientes:\nAjuste de medicación:\nFecha próximo control:",
        "Percentilo": "Motivo de consulta:\nPeso / talla / temperatura:\nAlimentación / hidratación:\nEvaluación general:\nPlan y recomendaciones:",
        "Cuidados paliativos": "Síntomas predominantes:\nDolor / confort:\nApoyo familiar:\nIntervenciones realizadas:\nPlan para las próximas horas:",
    }

    if puede_registrar:
        evs_all = get_patient_records("evoluciones_db", paciente_sel)
        if evs_all:
            ultima_ev = max(evs_all, key=lambda x: x.get("fecha", ""))
            c1, c2, c3 = st.columns(3)
            c1.metric("Última evolución", ultima_ev.get("fecha", "S/D"))
            c2.metric("Profesional", ultima_ev.get("firma") or "S/D")
            c3.metric("Total evoluciones", len(evs_all))

        plantilla = st.selectbox(
            "Plantilla de evolución",
            list(plantillas_evolucion.keys()),
            key="evol_plantilla_sel",
        )

        plantilla_prev = st.session_state.get(f"evol_plantilla_prev_{paciente_sel}", "Libre")
        if plantilla != plantilla_prev:
            st.session_state[_draft_key] = plantillas_evolucion.get(plantilla, "")
            st.session_state[f"evol_plantilla_prev_{paciente_sel}"] = plantilla

        if plantilla != "Libre":
            st.caption("Se carga una guía sugerida. Podés editarla antes de guardar.")

        _value_for_textarea = st.session_state.get(_draft_key, "")

        _ai_suggest_key = f"_ai_suggest_{paciente_sel}"
        if is_llm_enabled():
            if st.button("🤖 Sugerir evolución con IA", key=_ai_suggest_key, use_container_width=True):
                with st.spinner("Generando sugerencia de evolución..."):
                    assistant = get_evolution_assistant()
                    vitales = st.session_state.get("vitales_db") or []
                    ultimos_vitales = vitales[-1] if vitales else None
                    evs = get_patient_records("evoluciones_db", paciente_sel)
                    ultima_ev = max(evs, key=lambda x: x.get("fecha", "")) if evs else None
                    from core.utils_pacientes import get_detalles_from_db_cache
                    data = get_detalles_from_db_cache(paciente_sel) or {}
                    result = assistant.generate_evolution_suggestion(
                        patient_data=data,
                        vital_signs=ultimos_vitales,
                        symptoms="",
                        previous_evolution=ultima_ev.get("texto", "") if ultima_ev else None,
                    )
                    if result.get("suggestion"):
                        st.session_state[_draft_key] = result["suggestion"]
                        st.rerun()
                    else:
                        err = result.get("error", "Error al generar sugerencia")
                        log_event("evolucion", f"ai_suggest_error:{err[:80]}")
                        st.error(err)
        else:
            ai_not_available_warning()

        with st.form("evol", clear_on_submit=False):
            nota = st.text_area(
                "Nota médica / Evolución clínica",
                value=_value_for_textarea,
                height=220,
                placeholder="Escribir aquí la evolución...",
                key="evol_nota_textarea",
            )
            st.session_state[_draft_key] = nota
            if nota.strip():
                st.session_state["_draft_pending"] = True
            if st.session_state.get(_draft_key, "").strip():
                st.caption("💾 Borrador guardado automáticamente")

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

            imagen_subida = st.file_uploader(
                "Adjuntar imagen (opcional)",
                type=["png", "jpg", "jpeg", "gif", "webp"],
                key=f"evol_img_{paciente_sel}",
                label_visibility="collapsed",
            )

            guardar = st.form_submit_button("Firmar y guardar evolución", width="stretch", type="primary")

        if guardar:
            if not nota.strip():
                log_event("evolucion_panel", "error: nota_vacia")
                st.error("La nota médica no puede estar vacía.")
            else:
                fecha_n = ahora().strftime("%d/%m/%Y %H:%M")
                if "evoluciones_db" not in st.session_state or not isinstance(st.session_state["evoluciones_db"], list):
                    st.session_state["evoluciones_db"] = []

                imagen_b64 = ""
                imagen_nombre = ""
                imagen_tipo = ""
                if imagen_subida is not None:
                    ok, msg = validate_uploaded_file(imagen_subida)
                    if not ok:
                        st.error(f"Archivo no válido: {msg}")
                        st.stop()
                    imagen_bytes = imagen_subida.read()
                    max_img_bytes = 2 * 1024 * 1024
                    if len(imagen_bytes) > max_img_bytes:
                        st.warning("⚠️ La imagen supera 2MB. Se redimensionará automáticamente.")
                        try:
                            imagen_bytes = _optimizar_foto_segura(imagen_bytes)
                        except Exception as exc:
                            log_event("evolucion", f"optimizar_foto fallo: {type(exc).__name__}")
                            imagen_bytes = imagen_bytes[:max_img_bytes]
                    imagen_b64 = base64.b64encode(imagen_bytes).decode()
                    imagen_nombre = imagen_subida.name
                    imagen_tipo = imagen_subida.type

                st.session_state["evoluciones_db"].append({
                    "paciente": paciente_sel,
                    "nota": nota.strip(),
                    "fecha": fecha_n,
                    "firma": profesional,
                    "plantilla": plantilla,
                    "adjunto_img_b64": imagen_b64,
                    "adjunto_img_nombre": imagen_nombre,
                    "adjunto_img_tipo": imagen_tipo,
                })

                try:
                    from core.database import _trim_db_list
                    _trim_db_list("evoluciones_db", 500)
                except Exception as exc:
                    log_event("evolucion", f"trim_db_list fallo: {type(exc).__name__}")

                raw_foto = None
                if archivo_foto is not None:
                    ok, msg = validate_uploaded_file(archivo_foto)
                    if not ok:
                        st.error(f"Archivo no válido: {msg}")
                        st.stop()
                    raw_foto = archivo_foto.getvalue()
                elif foto_cam is not None:
                    raw_foto = foto_cam.getvalue()

                if raw_foto:
                    try:
                        foto_bytes = _optimizar_foto_segura(raw_foto)
                        base64_foto = base64.b64encode(foto_bytes).decode("utf-8")
                        if "fotos_heridas_db" not in st.session_state or not isinstance(st.session_state["fotos_heridas_db"], list):
                            st.session_state["fotos_heridas_db"] = []
                        st.session_state["fotos_heridas_db"].append({
                            "paciente": paciente_sel,
                            "fecha": fecha_n,
                            "descripcion": desc_w.strip(),
                            "base64_foto": base64_foto,
                            "firma": profesional,
                        })
                        from core.database import _trim_db_list
                        _trim_db_list("fotos_heridas_db", 100)
                    except Exception as exc:
                        log_event("evolucion_panel", f"foto_error:{type(exc).__name__}:{exc}")

                try:
                    registrar_auditoria_legal(
                        "Evolución clínica",
                        paciente_sel,
                        "Nueva evolución",
                        profesional,
                        user.get("matricula", "") if isinstance(user, dict) else "",
                        f"Se registró evolución con plantilla {plantilla}.",
                    )
                except Exception as exc:
                    log_event("evolucion_panel", f"auditoria_error:{type(exc).__name__}:{exc}")

                if not guardar_datos(spinner=True):
                    st.error("Error al guardar la evolución. Revisá la conexión e intentá de nuevo.")
                    st.stop()

                # ── Firma Digital RSA (Ley 25.506) ─────────────────────────
                try:
                    from core.digital_signature import DigitalSignatureManager, DocumentType
                    _dsig = DigitalSignatureManager()
                    _user_id = str(user.get("login", user.get("nombre", ""))) if isinstance(user, dict) else ""

                    if _user_id:
                        # Generar claves si no existen
                        if _user_id not in st.session_state.get("digital_signatures_keystore", {}):
                            _dsig.generate_keypair(_user_id)
                            log_event("evolucion", f"rsa_keys_generated:{_user_id}")

                        # Firmar la evolución
                        _doc_content = {
                            "paciente": paciente_sel,
                            "nota": nota.strip(),
                            "fecha": fecha_n,
                            "plantilla": plantilla,
                            "profesional": profesional,
                            "matricula": user.get("matricula", "") if isinstance(user, dict) else "",
                        }
                        _signed = _dsig.sign_document(
                            document=_doc_content,
                            doc_type=DocumentType.EVOLUCION,
                            signer_id=_user_id,
                            signer_name=str(user.get("nombre", profesional)) if isinstance(user, dict) else profesional,
                            signer_role=str(user.get("rol", "Profesional")) if isinstance(user, dict) else "Profesional",
                        )
                        # Guardar metadata de firma en session_state
                        _sig_field = {
                            "signature_id": _signed.signature.signature_id,
                            "document_id": _signed.signature.document_id,
                            "document_hash": _signed.signature.document_hash,
                            "signature_value": _signed.signature.signature_value,
                            "public_key_fingerprint": _signed.signature.public_key_fingerprint,
                            "signed_at": _signed.signature.signed_at,
                            "signer_name": _signed.signature.signer_name,
                            "signer_role": _signed.signature.signer_role,
                            "signer_id": _signed.signature.signer_id,
                            "hash_algorithm": _signed.signature.hash_algorithm,
                            "signature_algorithm": _signed.signature.signature_algorithm,
                        }
                        st.session_state["evoluciones_db"][-1]["firma_digital"] = _sig_field
                        log_event("evolucion", f"firma_digital_ok:{_signed.signature.signature_id[:12]}")
                except Exception as exc:
                    log_event("evolucion", f"firma_digital_error:{type(exc).__name__}:{exc}")

                try:
                    paciente_nombre = paciente_sel
                    paciente_id = paciente_sel
                    if isinstance(paciente_sel, str) and " - " in paciente_sel:
                        partes = paciente_sel.split(" - ")
                        paciente_nombre = " - ".join(partes[:-1])
                        paciente_id = partes[-1]
                    guardar_registro(
                        tipo="evoluciones",
                        paciente_id=paciente_id,
                        paciente_nombre=paciente_nombre,
                        datos={
                            "evolucion": nota.strip(),
                            "plantilla": plantilla,
                            "indicaciones": "",
                            "firma": profesional,
                            "fecha": fecha_n,
                        },
                    )
                except Exception as exc:
                    log_event("evolucion_panel", f"guardado_local_error:{type(exc).__name__}:{exc}")

                st.session_state["_draft_pending"] = False
                st.session_state.pop(_draft_key, None)
                st.session_state[f"evol_plantilla_prev_{paciente_sel}"] = "Libre"
                queue_toast("Evolución guardada correctamente.")
                st.rerun()
    else:
        st.caption("La carga de nuevas evoluciones queda deshabilitada para este rol.")

    render_tareas_panel(paciente_sel)

    evs_paciente = get_patient_records("evoluciones_db", paciente_sel)

    if evs_paciente:
        st.divider()
        st.markdown("#### Historial de evoluciones clínicas", unsafe_allow_html=True)

        evol_search = st.text_input("🔍 Buscar en evoluciones", placeholder="Palabra clave...", key="evol_fulltext_search")
        if evol_search.strip():
            q = evol_search.strip().lower()
            evs_paciente = [
                e for e in evs_paciente
                if q in str(e.get("nota", "")).lower()
                or q in str(e.get("texto", "")).lower()
                or q in str(e.get("detalle", "")).lower()
            ]
            if not evs_paciente:
                st.info(f"Sin resultados para '{evol_search}'")

        limite_evol = seleccionar_limite_registros(
            "Evoluciones a mostrar",
            len(evs_paciente),
            key=f"limite_evol_{paciente_sel}",
            default=20,
        )

        c1, c2 = st.columns([0.7, 0.3])
        with c1:
            st.markdown(f"**{len(evs_paciente)} evolución(es)**")
        with c2:
            if st.button("Descargar PDF", key=f"btn_pdf_historial_{paciente_sel}", type="primary", use_container_width=True):
                pdf_bytes = _generar_pdf_historia_clinica(paciente_sel)
                if pdf_bytes:
                    st.download_button(
                        label="Descargar PDF",
                        data=pdf_bytes,
                        file_name=f"Historia_Clinica_{str(paciente_sel).replace(' ', '_')}.pdf",
                        mime="application/pdf",
                        key=f"download_pdf_historial_{paciente_sel}",
                    )

        st.markdown("#### Historial de evoluciones", unsafe_allow_html=True)
        total_evs = len(evs_paciente)
        for idx, ev in enumerate(reversed(evs_paciente[-limite_evol:])):
            ev_num = total_evs - idx
            fecha = str(ev.get("fecha", ""))[:16]
            plantilla = ev.get("plantilla", "Sin plantilla")
            nota = str(ev.get("nota", ""))
            firma = str(ev.get("firma", ""))
            es_urgente = ev.get("urgente", False) or "urgente" in nota.lower()

            with st.expander(f"Evolución #{ev_num} — {fecha} — {plantilla}", key=f"ev_exp_{idx}_{ev.get('id', '')}"):
                if es_urgente:
                    st.error("Marcada como URGENTE")
                st.markdown(f"**Fecha:** `{html.escape(fecha)}`", unsafe_allow_html=True)
                if plantilla:
                    st.markdown(f"**Plantilla:** {html.escape(str(plantilla))}", unsafe_allow_html=True)
                if nota:
                    st.markdown("**Nota:**", unsafe_allow_html=True)
                    st.markdown(html.escape(nota), unsafe_allow_html=True)
                evo_img = ev.get("adjunto_img_b64", "")
                if evo_img:
                    img_tipo = ev.get("adjunto_img_tipo", "image/png")
                    st.markdown(
                        f"<img src='data:{html.escape(img_tipo)};base64,{evo_img}' "
                        f"style='max-width:300px;max-height:200px;border-radius:8px;margin:4px 0;'/>",
                        unsafe_allow_html=True,
                    )
                if firma and firma.strip():
                    firma_digital = ev.get("firma_digital", {})
                    if firma_digital and firma_digital.get("signature_value"):
                        try:
                            from core.digital_signature import DigitalSignatureManager, SignedDocument, SignatureMetadata
                            _dsig_verify = DigitalSignatureManager()
                            _sig_meta = SignatureMetadata(
                                signature_id=firma_digital.get("signature_id", ""),
                                document_id=firma_digital.get("document_id", ""),
                                document_type="evolucion",
                                signer_id=firma_digital.get("signer_id", ""),
                                signer_name=firma_digital.get("signer_name", ""),
                                signer_role=firma_digital.get("signer_role", ""),
                                signed_at=firma_digital.get("signed_at", ""),
                                hash_algorithm=firma_digital.get("hash_algorithm", "SHA-256"),
                                signature_algorithm=firma_digital.get("signature_algorithm", "RSA-PSS"),
                                document_hash=firma_digital.get("document_hash", ""),
                                signature_value=firma_digital.get("signature_value", ""),
                                public_key_fingerprint=firma_digital.get("public_key_fingerprint", ""),
                            )
                            _signed_doc = SignedDocument(
                                document_id=firma_digital.get("document_id", ""),
                                document_type="evolucion",
                                content={
                                    "paciente": paciente_sel,
                                    "nota": nota,
                                    "fecha": fecha,
                                    "plantilla": plantilla,
                                    "profesional": firma,
                                },
                                signature=_sig_meta,
                                timestamps={"signed_at": firma_digital.get("signed_at", "")},
                            )
                            _valido, _msg = _dsig_verify.verify_signature(_signed_doc)
                            if _valido:
                                st.success(f"✅ Firma digital RSA {firma_digital.get('signature_algorithm', '')} válida — {firma_digital.get('signer_name', '')} ({firma_digital.get('signed_at', '')[:10]})")
                            else:
                                st.error(f"🔴 Firma digital INVÁLIDA: {_msg}")
                        except Exception as exc:
                            log_event("evolucion", f"verificar_firma_error:{type(exc).__name__}:{exc}")
                            st.success(f"✅ Firmado por {firma} (verificación offline)")
                    else:
                        st.success(f"✅ Firmado por {firma}")

                if puede_borrar and st.button("Borrar esta evolución", key=f"borrar_ev_{ev_num}_{idx}_{paciente_sel}", type="secondary", use_container_width=True):
                    real_idx = (total_evs - 1) - idx
                    if 0 <= real_idx < len(evs_paciente):
                        ev_borrada = evs_paciente.pop(real_idx)
                        st.session_state["evoluciones_db"] = evs_paciente
                        try:
                            guardar_datos()
                        except Exception as exc:
                            log_event("evolucion", f"guardar_datos tras borrado fallo: {type(exc).__name__}")
                        try:
                            registrar_auditoria_legal(
                                "EVOLUCION_BORRADA",
                                paciente_sel,
                                detalles={
                                    "fecha": ev_borrada.get("fecha"),
                                    "plantilla": ev_borrada.get("plantilla"),
                                    "responsable": profesional,
                                },
                            )
                        except Exception as exc:
                            log_event("evolucion", f"auditoria_legal tras borrado fallo: {type(exc).__name__}")
                        queue_toast(f"Evolución #{ev_num} eliminada.", icon="🗑️")
                        st.rerun()

        if puede_borrar:
            col_chk, col_btn = st.columns([1.2, 2.8])
            confirmar_borrado = col_chk.checkbox("Confirmar", key=f"conf_del_evol_{paciente_sel}")
            if col_btn.button("Borrar última evolución", width="stretch", disabled=not confirmar_borrado):
                if not evs_paciente:
                    st.error("No hay evoluciones para borrar.")
                else:
                    ultima = evs_paciente[-1]
                    try:
                        st.session_state["evoluciones_db"].remove(ultima)
                    except ValueError:
                        pass
                    try:
                        guardar_datos(spinner=True)
                    except Exception as exc:
                        log_event("evolucion", f"guardar_datos borrado fallo: {type(exc).__name__}")
                    queue_toast("Evolución borrada.")
                    st.rerun()
    else:
        bloque_estado_vacio(
            "Sin evoluciones todavía",
            "Este paciente no tiene evoluciones médicas registradas.",
            sugerencia="Usá el formulario de arriba para cargar la primera evolución con firma.",
        )

    fotos_heridas = get_patient_records("fotos_heridas_db", paciente_sel)
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
                        st.image(base64.b64decode(foto.get("base64_foto", "")), width="stretch")
                    except Exception:
                        st.warning("No se pudo mostrar una foto registrada.")

    st.divider()
    st.markdown("##### Firma digital del paciente / familiar")
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

        if st.button("Guardar firma digital", width="stretch", type="primary"):
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
                try:
                    from core.database import _trim_db_list
                    _trim_db_list("firmas_tactiles_db", 200)
                    guardar_datos(spinner=True)
                except Exception as exc:
                    log_event("firma", f"guardar firma fallo: {type(exc).__name__}")
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
