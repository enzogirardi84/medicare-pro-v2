import base64
import hashlib
import io
import zipfile
from datetime import datetime

import streamlit as st

from core.alert_toasts import queue_toast
from core.clinical_exports import (
    build_backup_pdf_bytes,
    build_consent_pdf_bytes,
    build_history_pdf_bytes,
    build_patient_excel_bytes,
)
from core.database import guardar_datos
from core.view_helpers import aviso_registro_clinico_legal, aviso_sin_paciente
from core.utils import (
    ahora,
    firma_a_base64,
    mapa_detalles_pacientes,
    obtener_config_firma,
    puede_accion,
    registrar_auditoria_legal,
)
from core.db_sql import insert_consentimiento
from core.nextgen_sync import _obtener_uuid_paciente, _obtener_uuid_empresa
from core.app_logging import log_event

try:
    from PyPDF2 import PdfMerger as _PdfMerger
    _PYPDF_DISPONIBLE = True
except ImportError:
    _PYPDF_DISPONIBLE = False

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas
    CANVAS_DISPONIBLE = True
except ImportError:
    pass


def _build_combined_pdf_bytes(session_state, paciente_sel, mi_empresa, user):
    if not _PYPDF_DISPONIBLE:
        return None
    _parts = []
    for _builder in [build_history_pdf_bytes, build_backup_pdf_bytes, build_consent_pdf_bytes]:
        try:
            _b = _builder(session_state, paciente_sel, mi_empresa, user)
            if _b:
                _parts.append(_b)
        except Exception:
            continue
    if not _parts:
        return None
    try:
        _merger = _PdfMerger()
        for _p in _parts:
            _merger.append(io.BytesIO(_p))
        _out = io.BytesIO()
        _merger.write(_out)
        return _out.getvalue()
    except Exception as e:
        log_event("combined_pdf_error", str(e))
        return None


def _build_batch_pdf_zip(session_state, pacientes, mi_empresa, user, progress_callback=None):
    _zip_buf = io.BytesIO()
    _total = len(pacientes)
    with zipfile.ZipFile(_zip_buf, "w", zipfile.ZIP_DEFLATED) as _zf:
        for _i, _pac in enumerate(pacientes):
            try:
                _pdf = build_history_pdf_bytes(session_state, _pac, mi_empresa, user)
                if _pdf:
                    _name = f"HC_{_pac.replace(' ', '_').replace('/', '-')}.pdf"
                    _zf.writestr(_name, _pdf)
            except Exception:
                continue
            if progress_callback:
                progress_callback((_i + 1) / _total)
    return _zip_buf.getvalue()


def _render_export_block(container, key_base, titulo, descripcion, prepare_label, download_label, build_fn, file_name, mime, unavailable_message=None):
    st.markdown(f"**{titulo}**")
    st.caption(descripcion)
    cache_key = f"lazy_export_{key_base}"
    payload = st.session_state.get(cache_key)

    if payload:
        container.download_button(
            download_label,
            data=payload,
            file_name=file_name,
            mime=mime,
            key=f"download_{key_base}",
            width='stretch',
        )
        if container.button("Actualizar archivo", key=f"refresh_{key_base}", width='stretch'):
            st.session_state.pop(cache_key, None)
            st.rerun()
        return

    if container.button(prepare_label, key=f"prepare_{key_base}", width='stretch'):
        with st.spinner("Preparando archivo..."):
            try:
                payload = build_fn()
            except Exception:
                payload = None
        if payload:
            st.session_state[cache_key] = payload
            st.rerun()
        elif unavailable_message:
            st.info(unavailable_message)
        else:
            st.warning("No se pudo generar el archivo solicitado.")


def render_pdf(paciente_sel, mi_empresa, user, rol=None):
    if not paciente_sel:
        aviso_sin_paciente()
        return
    aviso_registro_clinico_legal()
    rol = rol or user.get("rol", "")
    puede_exportar_historia = puede_accion(rol, "pdf_exportar_historia")
    puede_exportar_excel = puede_accion(rol, "pdf_exportar_excel")
    puede_exportar_respaldo = puede_accion(rol, "pdf_exportar_respaldo")
    puede_guardar_consentimiento = puede_accion(rol, "pdf_guardar_consentimiento")
    puede_descargar_consentimiento = puede_accion(rol, "pdf_descargar_consentimiento")
    puede_batch = puede_exportar_historia

    st.markdown("## Documentos del paciente")
    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})

    tab_docs, tab_cons = st.tabs(["Exportar documentos", "Consentimiento legal"])

    with tab_docs:
        col_d1, col_d2 = st.columns(2)

        with col_d1:
            if puede_exportar_historia:
                _render_export_block(
                    st, key_base=f"pdf_hc_{paciente_sel}",
                    titulo="Historia Clinica PDF",
                    descripcion="Evoluciones, signos vitales, medicacion, emergencias y mas.",
                    prepare_label="Preparar PDF",
                    download_label="Descargar PDF",
                    build_fn=lambda: build_history_pdf_bytes(st.session_state, paciente_sel, mi_empresa, user),
                    file_name=f"HC_{paciente_sel.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                )
            else:
                st.info("Historia Clinica PDF: disponible para roles clinicos y de control.")

            if _PYPDF_DISPONIBLE and (puede_exportar_historia or puede_exportar_respaldo):
                _render_export_block(
                    st, key_base=f"pdf_combo_{paciente_sel}",
                    titulo="PDF combinado (todo en uno)",
                    descripcion="Historia clinica + Respaldo + Consentimiento fusionados.",
                    prepare_label="Preparar PDF completo",
                    download_label="Descargar PDF completo",
                    build_fn=lambda: _build_combined_pdf_bytes(st.session_state, paciente_sel, mi_empresa, user),
                    file_name=f"Completo_{paciente_sel.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                    unavailable_message="No se pudo generar el PDF combinado (se necesita al menos un documento disponible).",
                )

        with col_d2:
            if puede_exportar_excel:
                _render_export_block(
                    st, key_base=f"pdf_excel_{paciente_sel}",
                    titulo="Exportacion Completa Excel",
                    descripcion="Incluye cobros, insumos, medicacion, signos vitales y todos los modulos.",
                    prepare_label="Preparar Excel",
                    download_label="Descargar Excel",
                    build_fn=lambda: build_patient_excel_bytes(st.session_state, paciente_sel),
                    file_name=f"HC_{paciente_sel.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    unavailable_message="Excel no disponible (falta openpyxl o xlsxwriter).",
                )
                with st.expander("Diagnostico: datos disponibles para Excel", expanded=False):
                    _diag_keys = [
                        ("vitales_db", "Signos Vitales"),
                        ("evoluciones_db", "Evoluciones"),
                        ("agenda_db", "Visitas"),
                        ("consumos_db", "Materiales"),
                        ("indicaciones_db", "Plan Terapeutico"),
                        ("emergencias_db", "Emergencias"),
                        ("cuidados_enfermeria_db", "Enfermeria"),
                        ("escalas_clinicas_db", "Escalas"),
                        ("estudios_db", "Estudios"),
                        ("checkin_db", "Check-in"),
                        ("balance_db", "Balance"),
                        ("pediatria_db", "Pediatria"),
                        ("facturacion_db", "Facturacion"),
                        ("consentimientos_db", "Consentimientos"),
                    ]
                    _diag_lines = []
                    for _k, _l in _diag_keys:
                        _cnt = len(st.session_state.get(_k, []))
                        _diag_lines.append(f"- {_l}: **{_cnt}** registros en sesion")
                    st.markdown("\n".join(_diag_lines))
                    st.caption("Si ves registros aqui pero el Excel sale vacio, el filtro por paciente no esta coincidiendo. Se agrego un fallback que incluye todo.")
            else:
                st.caption("Excel reservado a rol Operativo o Auditoria.")

        if puede_exportar_respaldo:
            _render_export_block(
                st, key_base=f"pdf_respaldo_{paciente_sel}",
                titulo="Respaldo clinico sintetico",
                descripcion="Resumen compacto de todos los modulos clinicos del paciente.",
                prepare_label="Preparar respaldo",
                download_label="Descargar Respaldo PDF",
                build_fn=lambda: build_backup_pdf_bytes(st.session_state, paciente_sel, mi_empresa, user),
                file_name=f"Respaldo_Clinico_{paciente_sel.replace(' ', '_')}.pdf",
                mime="application/pdf",
            )

    with tab_cons:
        st.caption("Completa los datos del firmante, registra la firma y guarda para incorporarlo a la historia clinica.")

        col_c1, col_c2 = st.columns(2)
        firmante = col_c1.text_input("Nombre del paciente o familiar firmante", value=paciente_sel.split(" - ")[0], key=f"cons_firmante_{paciente_sel}")
        dni_firmante = col_c2.text_input("DNI del firmante", value=detalles.get("dni", ""), key=f"cons_dni_{paciente_sel}")
        col_c3, col_c4 = st.columns(2)
        vinculo = col_c3.selectbox("Vinculo", ["Paciente", "Familiar", "Tutor", "Responsable legal"], key=f"cons_vinc_{paciente_sel}")
        telefono = col_c4.text_input("Telefono de contacto", value=detalles.get("telefono", ""), key=f"cons_tel_{paciente_sel}")
        observaciones = st.text_area(
            "Observaciones del consentimiento",
            placeholder="Ej: familiar responsable presente durante la atencion o aclaraciones legales relevantes.",
            key=f"cons_obs_{paciente_sel}",
        )
        acepta = st.checkbox("Declara aceptar la atencion y terapia en el domicilio informado.", key=f"cons_ok_{paciente_sel}")

        canvas_result = None
        firma_subida = None
        if CANVAS_DISPONIBLE:
            firma_cfg = obtener_config_firma(f"consent_{paciente_sel}")
            metodo_firma = st.radio(
                "Metodo de firma del paciente / familiar",
                ["Subir foto de la firma (recomendado en celulares viejos)", "Firmar en pantalla"],
                horizontal=False,
                key=f"cons_method_{paciente_sel}",
            )
            if metodo_firma.startswith("Subir"):
                firma_subida = st.file_uploader(
                    "Subir imagen de la firma del paciente / familiar",
                    type=["png", "jpg", "jpeg"],
                    key=f"cons_upload_{paciente_sel}",
                )
            else:
                st.caption("Usa el lienzo solo si el celular responde fluido.")
                canvas_result = st_canvas(
                    fill_color="rgba(255,255,255,1)",
                    stroke_width=firma_cfg["stroke_width"],
                    stroke_color="#000000",
                    background_color="#ffffff",
                    height=firma_cfg["height"],
                    width=firma_cfg["width"],
                    drawing_mode="freedraw",
                    display_toolbar=firma_cfg["display_toolbar"],
                    key=f"canvas_consent_{paciente_sel}",
                )
        else:
            st.warning("Libreria de firma no disponible. Puedes subir una imagen de la firma.")
            firma_subida = st.file_uploader(
                "Subir imagen de la firma del paciente / familiar",
                type=["png", "jpg", "jpeg"],
                key=f"cons_upload_{paciente_sel}_sin_canvas",
            )

        if puede_guardar_consentimiento:
            if st.button("Guardar consentimiento legal", width='stretch', type="primary", key=f"save_consent_{paciente_sel}"):
                if not acepta:
                    st.error("Debe confirmar la aceptacion del tratamiento domiciliario.")
                else:
                    firma_b64 = firma_a_base64(
                        canvas_image_data=canvas_result.image_data if canvas_result is not None else None,
                        uploaded_file=firma_subida,
                    )
                    if not firma_b64:
                        st.error("La firma del paciente o familiar no se detecto. Dibujala antes de guardar.")
                    else:
                        fecha_str = ahora().strftime("%d/%m/%Y %H:%M")

                        doc_id = f"consent_{paciente_sel}_{int(datetime.now().timestamp())}"
                        doc_hash = hashlib.sha256(
                            f"{paciente_sel}|{fecha_str}|{firma_b64[:64]}".encode()
                        ).hexdigest()[:16]

                        try:
                            _partes_pac = paciente_sel.split(" - ")
                            _dni_cons = _partes_pac[1].strip() if len(_partes_pac) > 1 else detalles.get("dni", "")
                            _emp_uuid = _obtener_uuid_empresa(mi_empresa)
                            paciente_uuid = _obtener_uuid_paciente(_dni_cons, _emp_uuid) if _dni_cons and _emp_uuid else None
                            if paciente_uuid:
                                datos_sql = {
                                    "paciente_id": paciente_uuid,
                                    "fecha_firma": ahora().isoformat(),
                                    "tipo_documento": "Consentimiento Domiciliario",
                                    "archivo_url": None,
                                    "observaciones": f"Firmante: {firmante.strip()} | DNI: {dni_firmante.strip()} | Vinculo: {vinculo} | Tel: {telefono.strip()}\nObs: {observaciones.strip()}"
                                }
                                insert_consentimiento(datos_sql)
                                log_event("consentimiento_sql_insert", f"Paciente: {paciente_uuid}")
                        except Exception as e:
                            log_event("error_consentimiento_sql", str(e))

                        if not isinstance(st.session_state.get("consentimientos_db"), list):
                            st.session_state["consentimientos_db"] = []
                        st.session_state["consentimientos_db"].append(
                            {
                                "paciente": paciente_sel,
                                "fecha": fecha_str,
                                "tipo_documento": "Consentimiento Domiciliario",
                                "firmante": firmante.strip() or paciente_sel.split(" - ")[0],
                                "dni_firmante": dni_firmante.strip() or detalles.get("dni", ""),
                                "vinculo": vinculo,
                                "telefono": telefono.strip(),
                                "observaciones": observaciones.strip(),
                                "firma_b64": firma_b64,
                                "doc_id": doc_id,
                                "doc_hash": doc_hash,
                                "profesional": user.get("nombre", ""),
                                "matricula_profesional": user.get("matricula", ""),
                            }
                        )
                        from core.database import _trim_db_list
                        _trim_db_list("consentimientos_db", 200)
                        registrar_auditoria_legal(
                            "Consentimiento",
                            paciente_sel,
                            "Consentimiento legal guardado",
                            user.get("nombre", ""),
                            user.get("matricula", ""),
                            f"Firmante: {firmante.strip() or paciente_sel.split(' - ')[0]} | Vinculo: {vinculo}",
                        )
                        guardar_datos(spinner=True)
                        queue_toast("Consentimiento legal guardado en la historia clinica.")
                        st.rerun()
        else:
            st.caption("Guardar consentimientos queda reservado a roles asistenciales y de coordinacion.")

        consentimientos_paciente = [x for x in st.session_state.get("consentimientos_db", []) if x.get("paciente") == paciente_sel]
        if puede_descargar_consentimiento:
            _render_export_block(
                st, key_base=f"consent_pdf_{paciente_sel}",
                titulo="Descargar consentimiento",
                descripcion="PDF del consentimiento legal firmado para imprimir.",
                prepare_label="Preparar PDF",
                download_label="Descargar PDF",
                build_fn=lambda: build_consent_pdf_bytes(st.session_state, paciente_sel, mi_empresa, user),
                file_name=f"Consentimiento_{paciente_sel.replace(' ', '_')}.pdf",
                mime="application/pdf",
                unavailable_message="Todavia no hay consentimiento guardado para este paciente.",
            )
        else:
            st.caption("La descarga del consentimiento queda reservada a roles clinicos y de control.")

        if consentimientos_paciente:
            ultimo = consentimientos_paciente[-1]
            st.info(
                f"Ultimo consentimiento: {ultimo.get('fecha', 'S/D')} | "
                f"Firmante: {ultimo.get('firmante', 'S/D')} | Vinculo: {ultimo.get('vinculo', 'S/D')}"
            )
            if ultimo.get("firma_b64"):
                try:
                    st.image(base64.b64decode(ultimo["firma_b64"]), caption="Firma registrada", width=280)
                except Exception as e:
                    log_event("pdf_view_error", str(e))
        elif puede_descargar_consentimiento:
            st.warning("Todavia no hay consentimientos guardados. Completa el formulario y guarda primero.")

    # Batch
    if puede_batch:
        with st.expander("Exportacion por lote (varios pacientes)", expanded=False):
            _pacientes = sorted(st.session_state.get("pacientes_db", []))
            if not _pacientes:
                st.warning("No hay pacientes cargados en esta sesion.")
            else:
                _seleccion = st.multiselect("Seleccionar pacientes", _pacientes, default=[paciente_sel], key="batch_pac_sel")
                st.caption(f"{len(_seleccion)} paciente(s) seleccionado(s).")
                if _seleccion and st.button("Generar ZIP con HC de seleccionados", key="batch_pdf_btn"):
                    _barra = st.progress(0, text="Generando PDFs...")
                    _status = st.empty()
                    _status.info(f"Procesando 0/{len(_seleccion)}...")
                    def _progreso(frac):
                        _barra.progress(frac)
                        _done = int(frac * len(_seleccion))
                        _status.info(f"Procesando {_done}/{len(_seleccion)}...")
                    _zip_bytes = _build_batch_pdf_zip(st.session_state, _seleccion, mi_empresa, user, progress_callback=_progreso)
                    _barra.empty()
                    _status.empty()
                    if _zip_bytes:
                        st.success(f"{len(_seleccion)} PDFs generados.")
                        st.download_button(
                            "Descargar ZIP",
                            data=_zip_bytes,
                            file_name=f"Lote_HC_{ahora().strftime('%d%m%Y')}.zip",
                            mime="application/zip",
                            width='stretch',
                        )
                    else:
                        st.warning("No se pudo generar ningun PDF. Verifica ReportLab.")
