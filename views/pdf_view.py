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
from core.utils import ahora, firma_a_base64, obtener_config_firma, registrar_auditoria_legal

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas

    CANVAS_DISPONIBLE = True
except ImportError:
    pass


def render_pdf(paciente_sel, mi_empresa, user):
    if not paciente_sel:
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Centro documental del paciente</h2>
            <p class="mc-hero-text">Genera documentos listos para imprimir, archivar o entregar. La historia clinica, el respaldo y el consentimiento legal quedan concentrados en una sola vista.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">PDF institucional</span>
                <span class="mc-chip">Respaldo imprimible</span>
                <span class="mc-chip">Consentimiento legal</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Generar Documentos del Paciente")
    detalles = st.session_state["detalles_pacientes_db"].get(paciente_sel, {})
    pdf_hc = build_history_pdf_bytes(st.session_state, paciente_sel, mi_empresa, user)
    pdf_respaldo = build_backup_pdf_bytes(st.session_state, paciente_sel, mi_empresa, user)
    excel_bytes = build_patient_excel_bytes(st.session_state, paciente_sel)

    col_d1, col_d2, col_d3 = st.columns(3)
    col_d1.download_button(
        "Descargar Historia Clinica Completa (PDF)",
        data=pdf_hc,
        file_name=f"HC_{paciente_sel.replace(' ', '_')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )
    if excel_bytes:
        col_d2.download_button(
            "Descargar Historia Clinica (Excel)",
            data=excel_bytes,
            file_name=f"HC_{paciente_sel.replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True,
        )
    else:
        col_d2.info("Excel no disponible.")
    col_d3.download_button(
        "Descargar Respaldo Clinico (PDF)",
        data=pdf_respaldo,
        file_name=f"Respaldo_Clinico_{paciente_sel.replace(' ', '_')}.pdf",
        mime="application/pdf",
        use_container_width=True,
    )

    st.success("Descargas seguras activadas.")
    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>Historia completa</h4><p>Incluye datos del paciente, registros clinicos y firmas para archivo institucional.</p></div>
            <div class="mc-card"><h4>Respaldo rapido</h4><p>Version sintetica en PDF para guardar o imprimir cuando no hace falta todo el detalle.</p></div>
            <div class="mc-card"><h4>Consentimiento legal</h4><p>Documento formal pensado para paciente y familia, listo para impresion y firma.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.divider()

    st.markdown("#### Consentimiento legal de atencion domiciliaria")
    st.caption("Este documento queda listo para imprimir y firmar por el paciente o un familiar responsable.")

    st.markdown(
        """
        <div class="mc-callout">
            <strong>Recomendacion:</strong> completar primero los datos del firmante, luego registrar la firma y finalmente guardar para dejar el consentimiento incorporado en la historia clinica.
        </div>
        """,
        unsafe_allow_html=True,
    )

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
    if CANVAS_DISPONIBLE:
        firma_cfg = obtener_config_firma(f"consent_{paciente_sel}")
        firma_subida = st.file_uploader(
            "O subir foto de la firma del paciente / familiar",
            type=["png", "jpg", "jpeg"],
            key=f"cons_upload_{paciente_sel}",
        )
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
        firma_subida = None

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
                st.session_state["consentimientos_db"].append(
                    {
                        "paciente": paciente_sel,
                        "fecha": ahora().strftime("%d/%m/%Y %H:%M"),
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
                st.success("Consentimiento legal guardado en la historia clinica.")
                st.rerun()

    consentimiento_pdf = build_consent_pdf_bytes(st.session_state, paciente_sel, mi_empresa, user)
    if consentimiento_pdf:
        st.download_button(
            "Descargar consentimiento legal para imprimir (PDF)",
            data=consentimiento_pdf,
            file_name=f"Consentimiento_{paciente_sel.replace(' ', '_')}.pdf",
            mime="application/pdf",
            use_container_width=True,
        )
        ultimo = [x for x in st.session_state.get("consentimientos_db", []) if x.get("paciente") == paciente_sel][-1]
        st.info(
            f"Ultimo consentimiento registrado: {ultimo.get('fecha', 'S/D')} | "
            f"Firmante: {ultimo.get('firmante', 'S/D')} | Vinculo: {ultimo.get('vinculo', 'S/D')}"
        )
        if ultimo.get("firma_b64"):
            try:
                st.image(base64.b64decode(ultimo["firma_b64"]), caption="Firma paciente / familiar registrada", width=280)
            except Exception:
                pass
