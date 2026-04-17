from core.alert_toasts import queue_toast
import base64
import io

import streamlit as st

from core.clinical_exports import (
    build_backup_pdf_bytes,
    build_consent_pdf_bytes,
    build_history_pdf_bytes,
    build_patient_excel_bytes,
)
from core.database import guardar_datos
from core.view_helpers import aviso_registro_clinico_legal, aviso_sin_paciente, bloque_mc_grid_tarjetas
from core.utils import (
    ahora,
    firma_a_base64,
    mapa_detalles_pacientes,
    obtener_config_firma,
    puede_accion,
    registrar_auditoria_legal,
)
from core.db_sql import get_consentimientos_by_paciente, insert_consentimiento
from core.nextgen_sync import _obtener_uuid_paciente, _obtener_uuid_empresa
from core.app_logging import log_event

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas

    CANVAS_DISPONIBLE = True
except ImportError:
    pass


def _render_lazy_download(container, key_base, prepare_label, download_label, build_fn, file_name, mime, unavailable_message=None):
    cache_key = f"lazy_export_{key_base}"
    payload = st.session_state.get(cache_key)

    if payload:
        container.download_button(
            download_label,
            data=payload,
            file_name=file_name,
            mime=mime,
            key=f"download_{key_base}",
            use_container_width=True,
        )
        if container.button("Actualizar archivo", key=f"refresh_{key_base}", use_container_width=True):
            st.session_state.pop(cache_key, None)
            st.rerun()
        return

    if container.button(prepare_label, key=f"prepare_{key_base}", use_container_width=True):
        with st.spinner("Preparando archivo..."):
            try:
                payload = build_fn()
            except Exception:
                payload = None
        if payload:
            st.session_state[cache_key] = payload
            st.rerun()
        elif unavailable_message:
            container.info(unavailable_message)
        else:
            container.warning("No se pudo generar el archivo solicitado.")


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

    st.markdown("## Documentos del paciente")
    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})

    tab_docs, tab_cons = st.tabs(["📄 Exportar documentos", "✍️ Consentimiento legal"])

    with tab_docs:
        st.caption("Presiona **Preparar**, espera la generacion, luego **Descargar**.")
        col_d1, col_d2 = st.columns(2)

        with col_d1:
            st.markdown("#### 📋 Historia Clínica PDF")
            st.caption("Evoluciones, signos vitales, medicacion, emergencias y mas.")
            if puede_exportar_historia:
                _render_lazy_download(
                    st,
                    key_base=f"pdf_hc_{paciente_sel}",
                    prepare_label="Preparar Historia Clinica (PDF)",
                    download_label="⬇️ Descargar Historia Clinica (PDF)",
                    build_fn=lambda: build_history_pdf_bytes(st.session_state, paciente_sel, mi_empresa, user),
                    file_name=f"HC_{paciente_sel.replace(' ', '_')}.pdf",
                    mime="application/pdf",
                )
            else:
                st.info("Disponible para roles clinicos y de control.")

        with col_d2:
            st.markdown("#### 📊 Exportacion Completa Excel")
            st.caption("Incluye cobros, insumos, medicacion, signos vitales y todos los modulos.")
            if puede_exportar_excel:
                _render_lazy_download(
                    st,
                    key_base=f"pdf_excel_{paciente_sel}",
                    prepare_label="Preparar Excel completo",
                    download_label="⬇️ Descargar Historia Clinica (Excel)",
                    build_fn=lambda: build_patient_excel_bytes(st.session_state, paciente_sel),
                    file_name=f"HC_{paciente_sel.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    unavailable_message="Excel no disponible (falta openpyxl o xlsxwriter).",
                )
            else:
                st.caption("Excel reservado a rol Operativo o Auditoria.")

        if puede_exportar_respaldo:
            with st.expander("Respaldo clinico sintetico (PDF adicional)", expanded=False):
                _render_lazy_download(
                    st,
                    key_base=f"pdf_respaldo_{paciente_sel}",
                    prepare_label="Preparar respaldo clinico",
                    download_label="Descargar Respaldo Clinico (PDF)",
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
            if st.button("Guardar consentimiento legal", use_container_width=True, type="primary", key=f"save_consent_{paciente_sel}"):
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

                        # 1. Guardar en SQL (Dual-Write)
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

                        # 2. Guardar en JSON (Legacy)
                        if not isinstance(st.session_state.get("consentimientos_db"), list):
                            st.session_state["consentimientos_db"] = []
                        st.session_state["consentimientos_db"].append(
                            {
                                "paciente": paciente_sel,
                                "fecha": fecha_str,
                                "firmante": firmante.strip() or paciente_sel.split(" - ")[0],
                                "dni_firmante": dni_firmante.strip() or detalles.get("dni", ""),
                                "vinculo": vinculo,
                                "telefono": telefono.strip(),
                                "observaciones": observaciones.strip(),
                                "firma_b64": firma_b64,
                                "profesional": user.get("nombre", ""),
                                "matricula_profesional": user.get("matricula", ""),
                            }
                        )
                        registrar_auditoria_legal(
                            "Consentimiento",
                            paciente_sel,
                            "Consentimiento legal guardado",
                            user.get("nombre", ""),
                            user.get("matricula", ""),
                            f"Firmante: {firmante.strip() or paciente_sel.split(' - ')[0]} | Vinculo: {vinculo}",
                        )
                        guardar_datos()
                        queue_toast("Consentimiento legal guardado en la historia clinica.")
                        st.rerun()
        else:
            st.caption("Guardar consentimientos queda reservado a roles asistenciales y de coordinacion.")

        consentimientos_paciente = [x for x in st.session_state.get("consentimientos_db", []) if x.get("paciente") == paciente_sel]
        if puede_descargar_consentimiento:
            _render_lazy_download(
                st,
                key_base=f"consent_pdf_{paciente_sel}",
                prepare_label="Preparar consentimiento legal",
                download_label="Descargar consentimiento legal para imprimir (PDF)",
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
