"""Laboratorio - Gestion de resultados con archivos y PDF."""
from __future__ import annotations

import base64
import io
from datetime import datetime

import pandas as pd
import streamlit as st

from core.alert_toasts import queue_toast
from core.app_logging import log_event
from core.database import guardar_datos
from core.export_utils import sanitize_filename_component
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas


def _generar_pdf_lab(registro: dict) -> bytes:
    """Genera PDF con resultado de laboratorio."""
    try:
        from fpdf import FPDF
        pdf = FPDF(format="A5")
        pdf.set_margins(12, 10, 12)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Resultado de Laboratorio", align="C")
        pdf.ln(12)
        pdf.set_font("Helvetica", "", 10)
        for label, key in [
            ("Paciente", "paciente"), ("Analito", "analito"),
            ("Valor", "valor"), ("Unidad", "unidad"),
            ("Rango ref.", "rango_referencia"),
            ("Fecha", "fecha"), ("Observaciones", "observaciones"),
        ]:
            val = str(registro.get(key, "") or "")
            if val:
                pdf.set_font("Helvetica", "B", 9)
                pdf.cell(40, 6, label + ":")
                pdf.set_font("Helvetica", "", 9)
                pdf.cell(0, 6, val)
                pdf.ln(5)
        pdf.ln(8)
        pdf.set_font("Helvetica", "I", 7)
        pdf.cell(0, 5, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="C")
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
            <p class="mc-hero-text">Gestion de resultados: carga manual, archivos PDF/imagen, descarga PDF de cada resultado.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Carga manual</span>
                <span class="mc-chip">Archivos adjuntos</span>
                <span class="mc-chip">Descargar PDF</span>
            </div>
        </div>
    """, unsafe_allow_html=True)
    bloque_mc_grid_tarjetas([
        ("Cargar resultado", "Analito, valor, unidad y archivo adjunto opcional."),
        ("Historial", "Resultados anteriores con descarga PDF."),
        ("Pendientes", "Resultados sin revisar."),
    ])

    if "laboratorio_db" not in st.session_state:
        st.session_state["laboratorio_db"] = []
    lab_db = st.session_state["laboratorio_db"]
    lab_paciente = [r for r in lab_db if r.get("paciente") == paciente_sel]

    tabs = st.tabs(["Cargar resultado", "Historial", "Pendientes"])

    # ============ TAB: Cargar ============
    with tabs[0]:
        with st.form("lab_form", clear_on_submit=True):
            st.markdown("##### Datos del analisis")
            c1, c2 = st.columns(2)
            fecha = c1.date_input("Fecha del analisis", value=ahora().date())
            analito = c2.text_input("Analito", placeholder="Ej: Hemoglobina, Glucosa, TSH")

            c3, c4, c5 = st.columns(3)
            valor = c3.text_input("Valor obtenido")
            unidad = c4.text_input("Unidad", placeholder="g/dL, mg/dL...")
            rango = c5.text_input("Rango de referencia", placeholder="Ej: 13-17 g/dL")

            observaciones = st.text_area("Observaciones", placeholder="Notas adicionales sobre el resultado...")

            # Archivo adjunto (opcional)
            archivo = st.file_uploader(
                "Adjuntar archivo (PDF/imagen del resultado)",
                type=["pdf", "png", "jpg", "jpeg"],
                help="Opcional. Subi el PDF o foto del resultado real.",
            )
            archivo_b64 = ""
            archivo_tipo = ""
            archivo_nombre = ""
            if archivo is not None:
                archivo_b64 = base64.b64encode(archivo.getvalue()).decode()
                archivo_tipo = archivo.type or ""
                archivo_nombre = archivo.name

            if st.form_submit_button("Guardar resultado", width="stretch", type="primary"):
                if not analito.strip():
                    st.error("El nombre del analito es obligatorio.")
                elif not valor.strip():
                    st.error("El valor del analito es obligatorio.")
                else:
                    registro = {
                        "paciente": paciente_sel,
                        "fecha": fecha.strftime("%d/%m/%Y"),
                        "analito": analito.strip(),
                        "valor": valor.strip(),
                        "unidad": unidad.strip(),
                        "rango_referencia": rango.strip(),
                        "observaciones": observaciones.strip(),
                        "archivo_b64": archivo_b64,
                        "archivo_tipo": archivo_tipo,
                        "archivo_nombre": archivo_nombre,
                        "visto": False,
                        "empresa": mi_empresa,
                        "registrado_por": user.get("nombre", "Sistema"),
                        "fecha_registro": ahora().isoformat(),
                    }
                    lab_db.append(registro)
                    guardar_datos(spinner=True)
                    queue_toast(f"Resultado de {analito.strip()} guardado.")
                    log_event("lab_guardar", f"{analito} - {paciente_sel}")
                    st.rerun()

    # ============ TAB: Historial ============
    with tabs[1]:
        if lab_paciente:
            st.caption(f"Resultados de **{paciente_sel}** — {len(lab_paciente)} registros")
            for i, r in enumerate(reversed(lab_paciente)):
                with st.container(border=True):
                    cols = st.columns([3, 1, 1, 1])
                    cols[0].markdown(f"**{r.get('analito','')}**")
                    cols[1].markdown(f"{r.get('valor','')} {r.get('unidad','')}")
                    cols[2].markdown(f"{r.get('fecha','')}")
                    cols[3].markdown("✅ Visto" if r.get("visto") else "⏳ Pendiente")

                    if r.get("archivo_b64"):
                        ext = r.get("archivo_nombre", "").split(".")[-1] if r.get("archivo_nombre") else "pdf"
                        btn_label = f"Ver archivo ({ext})"
                        if st.button(btn_label, key=f"lab_view_{i}", width="stretch"):
                            st.markdown(
                                f'<a href="data:{r["archivo_tipo"] or "application/octet-stream"};base64,{r["archivo_b64"]}" '
                                f'download="{r.get("archivo_nombre", "archivo")}" target="_blank">Abrir archivo</a>',
                                unsafe_allow_html=True,
                            )

                    # Boton PDF
                    pdf_bytes = _generar_pdf_lab(r)
                    if pdf_bytes:
                        nombre_file = sanitize_filename_component(f"lab_{r.get('analito','resultado')}_{r.get('fecha','')}")
                        st.download_button(
                            label="Descargar PDF",
                            data=pdf_bytes,
                            file_name=f"{nombre_file}.pdf",
                            mime="application/pdf",
                            key=f"lab_pdf_{i}",
                            width="stretch",
                        )
        else:
            bloque_estado_vacio(
                "Sin resultados",
                "No hay analitos registrados para este paciente.",
                sugerencia="Carga resultados en la pestana Cargar resultado.",
            )

    # ============ TAB: Pendientes ============
    with tabs[2]:
        no_vistos = [r for r in lab_paciente if not r.get("visto")]
        if no_vistos:
            st.caption(f"{len(no_vistos)} resultado(s) pendiente(s) de revision:")
            for i, r in enumerate(no_vistos):
                with st.container(border=True):
                    st.markdown(f"**{r['analito']}**: {r['valor']} {r.get('unidad','')} — {r.get('fecha','')}")
                    if r.get("observaciones"):
                        st.caption(r["observaciones"])
                    if st.checkbox("Marcar como visto", key=f"lab_visto_{i}"):
                        r["visto"] = True
                        guardar_datos(spinner=True)
                        queue_toast(f"{r['analito']} marcado como visto.")
                        st.rerun()
        else:
            bloque_estado_vacio(
                "Sin pendientes",
                "Todos los resultados fueron revisados.",
                sugerencia="Carga nuevos resultados en la pestana Cargar resultado.",
            )
