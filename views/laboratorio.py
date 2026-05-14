"""Laboratorio - Subir resultados completos (PDF/imagen) con descarga."""
from __future__ import annotations

import base64
from datetime import datetime

import streamlit as st

from core.alert_toasts import queue_toast
from core.app_logging import log_event
from core.database import guardar_datos
from core.export_utils import sanitize_filename_component
from core.utils import ahora
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio


def _generar_pdf_lab(registro: dict) -> bytes:
    try:
        from fpdf import FPDF
        pdf = FPDF(format="A4")
        pdf.set_margins(15, 10, 15)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 12, "Resultado de Laboratorio", align="C")
        pdf.ln(14)
        pdf.set_font("Helvetica", "", 10)
        for label, key in [
            ("Paciente", "paciente"), ("Tipo de estudio", "tipo_estudio"),
            ("Fecha del analisis", "fecha"),
            ("Medico solicitante", "medico_solicitante"),
            ("Observaciones", "observaciones"),
        ]:
            val = str(registro.get(key, "") or "")
            if val:
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(42, 6, label + ":")
                pdf.set_font("Helvetica", "", 9)
                pdf.multi_cell(0, 6, val)
                pdf.ln(2)
        pdf.ln(10)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 5, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')} | ID: {registro.get('id','')}", align="C")
        return pdf.output(dest="S").encode("latin-1", errors="replace")
    except Exception as e:
        log_event("lab", f"error_pdf:{e}")
        return b""


def render_laboratorio(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Laboratorio</h2>
            <p class="mc-hero-text">Subi resultados completos (PDF, imagen) con datos del estudio. Descarga y revision incluida.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Subir estudio</span>
                <span class="mc-chip">Historial</span>
                <span class="mc-chip">Descargar PDF</span>
            </div>
        </div>
    """, unsafe_allow_html=True)

    if "laboratorio_db" not in st.session_state:
        st.session_state["laboratorio_db"] = []
    lab_db = st.session_state["laboratorio_db"]
    lab_paciente = [r for r in lab_db if r.get("paciente") == paciente_sel]

    tabs = st.tabs(["Subir estudio", "Historial"])

    # ============ TAB: SUBIR ============
    with tabs[0]:
        with st.form("lab_form", clear_on_submit=True):
            st.markdown("##### Datos del estudio")
            c1, c2 = st.columns(2)
            tipo_estudio = c1.text_input("Tipo de estudio", placeholder="Ej: Analisis clinico, Perfil hepatico, Urocultivo...")
            fecha = c2.date_input("Fecha del analisis", value=ahora().date())

            medico = st.text_input("Medico solicitante", placeholder="Opcional")

            archivo = st.file_uploader(
                "Subir resultado (PDF, imagen)",
                type=["pdf", "png", "jpg", "jpeg"],
                help="PDF del laboratorio o foto del resultado.",
            )

            observaciones = st.text_area("Notas", placeholder="Comentarios sobre el resultado...")

            if st.form_submit_button("Guardar estudio", width="stretch", type="primary"):
                if not tipo_estudio.strip():
                    st.error("El tipo de estudio es obligatorio.")
                elif archivo is None:
                    st.error("Debe adjuntar el archivo del resultado.")
                else:
                    archivo_b64 = base64.b64encode(archivo.getvalue()).decode()
                    registro = {
                        "paciente": paciente_sel,
                        "tipo_estudio": tipo_estudio.strip(),
                        "fecha": fecha.strftime("%d/%m/%Y"),
                        "medico_solicitante": medico.strip(),
                        "observaciones": observaciones.strip(),
                        "archivo_b64": archivo_b64,
                        "archivo_tipo": archivo.type or "",
                        "archivo_nombre": archivo.name,
                        "visto": False,
                        "empresa": mi_empresa,
                        "registrado_por": user.get("nombre", "Sistema"),
                        "fecha_registro": ahora().isoformat(),
                        "id": f"lab_{int(datetime.now().timestamp())}",
                    }
                    lab_db.append(registro)
                    guardar_datos(spinner=True)
                    queue_toast(f"Estudio {tipo_estudio.strip()} guardado.")
                    log_event("lab_guardar", f"{tipo_estudio} - {paciente_sel}")
                    st.rerun()

    # ============ TAB: HISTORIAL ============
    with tabs[1]:
        if lab_paciente:
            for i, r in enumerate(reversed(lab_paciente)):
                with st.container(border=True):
                    col1, col2, col3 = st.columns([3, 1, 1])
                    col1.markdown(f"**{r.get('tipo_estudio','?')}** — {r.get('fecha','')}")
                    col2.markdown("✅ Visto" if r.get("visto") else "⏳ Pendiente")
                    if r.get("medico_solicitante"):
                        col3.caption(f"Dr. {r['medico_solicitante']}")
                    if r.get("observaciones"):
                        st.caption(r["observaciones"])

                    cols_btn = st.columns(4)
                    # Ver archivo
                    if r.get("archivo_b64"):
                        at = r.get("archivo_tipo", "application/octet-stream")
                        an = r.get("archivo_nombre", "resultado")
                        ab = r["archivo_b64"]
                        cols_btn[0].markdown(
                            f'<a href="data:{at};base64,{ab}" download="{an}" target="_blank">Ver archivo</a>',
                            unsafe_allow_html=True,
                        )

                    # PDF
                    pdf_bytes = _generar_pdf_lab(r)
                    if pdf_bytes:
                        nf = sanitize_filename_component(f"lab_{r.get('tipo_estudio','resultado')}_{r.get('fecha','')}")
                        cols_btn[1].download_button("PDF", pdf_bytes, f"{nf}.pdf", "application/pdf", key=f"lp_{i}", width="content")

                    # Marcar visto
                    if not r.get("visto"):
                        if cols_btn[2].button("Marcar visto", key=f"lv_{i}", width="content"):
                            r["visto"] = True
                            guardar_datos(spinner=True)
                            st.rerun()

                    # Eliminar
                    if cols_btn[3].button("Eliminar", key=f"ld_{i}", width="content"):
                        lab_db.remove(r)
                        guardar_datos(spinner=True)
                        st.rerun()
        else:
            bloque_estado_vacio(
                "Sin estudios",
                "No hay resultados de laboratorio para este paciente.",
                sugerencia="Subi un estudio en la pestana Subir estudio.",
            )
