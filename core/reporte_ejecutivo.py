"""Reporte ejecutivo PDF - resumen de operaciones para toma de decisiones."""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

import streamlit as st

from core.app_logging import log_event
from core.export_utils import pdf_output_bytes, safe_text


def generar_reporte_ejecutivo(mi_empresa: str) -> bytes:
    """Genera PDF con resumen ejecutivo de operaciones."""
    try:
        from fpdf import FPDF

        pdf = FPDF(format="A4")
        pdf.set_margins(15, 15, 15)
        pdf.add_page()

        # Header
        pdf.set_font("Helvetica", "B", 18)
        pdf.cell(0, 12, f"Reporte Ejecutivo - {mi_empresa}", align="C")
        pdf.ln(14)
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 5, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", align="C")
        pdf.ln(10)

        # Resumen de pacientes
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Resumen de Pacientes", align="L")
        pdf.ln(8)

        pacientes = st.session_state.get("pacientes_db", [])
        detalles = st.session_state.get("detalles_pacientes_db", {})
        activos = sum(1 for p in pacientes if isinstance(detalles.get(p, {}), dict) and detalles[p].get("estado", "Activo") == "Activo")
        altas = sum(1 for p in pacientes if isinstance(detalles.get(p, {}), dict) and detalles[p].get("estado") == "De Alta")

        pdf.set_font("Helvetica", "", 10)
        for label, val in [("Pacientes activos", activos), ("Pacientes de alta", altas), ("Total", len(pacientes))]:
            pdf.cell(95, 7, f"{label}: {val}")
            pdf.ln(6)
        pdf.ln(4)

        # Facturacion
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Facturacion", align="L")
        pdf.ln(8)

        facturas = st.session_state.get("facturacion_db", [])
        total_fact = sum(float(f.get("monto", 0) or 0) for f in facturas)
        cobrado = sum(float(f.get("monto", 0) or 0) for f in facturas if "Cobrado" in f.get("estado", ""))
        pendiente = sum(float(f.get("monto", 0) or 0) for f in facturas if "Pendiente" in f.get("estado", ""))

        pdf.set_font("Helvetica", "", 10)
        for label, val in [("Total facturado", f"${total_fact:,.2f}"), ("Cobrado", f"${cobrado:,.2f}"), ("Pendiente", f"${pendiente:,.2f}")]:
            pdf.cell(95, 7, f"{label}: {val}")
            pdf.ln(6)
        pdf.ln(4)

        # Stock - items con stock bajo
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Inventario - Alertas de Stock", align="L")
        pdf.ln(8)

        inventario = st.session_state.get("inventario_db", [])
        stock_bajo = [i for i in inventario if int(i.get("stock", 0) or 0) <= 10]
        pdf.set_font("Helvetica", "", 10)
        if stock_bajo:
            for item in stock_bajo[:10]:
                nombre = safe_text(str(item.get("nombre", item.get("insumo", "?")))[:40])
                stock = item.get("stock", 0)
                pdf.cell(0, 6, f"  - {nombre}: {stock} unidades")
                pdf.ln(5)
            if len(stock_bajo) > 10:
                pdf.cell(0, 6, f"  ... y {len(stock_bajo) - 10} mas")
        else:
            pdf.cell(0, 6, "Sin alertas de stock.")
        pdf.ln(6)

        # Actividad reciente
        pdf.set_font("Helvetica", "B", 13)
        pdf.cell(0, 8, "Actividad Reciente (ultimas 48h)", align="L")
        pdf.ln(8)

        ahora_local = datetime.now()
        hace_48h = ahora_local - timedelta(hours=48)
        evoluciones = st.session_state.get("evoluciones_db", [])
        recientes = len(evoluciones)  # simplificado

        pdf.set_font("Helvetica", "", 10)
        pdf.cell(0, 6, f"Evoluciones registradas: {recientes}")
        pdf.ln(5)
        pdf.cell(0, 6, f"Movimientos de facturacion: {len(facturas)}")

        pdf.ln(15)
        pdf.set_font("Helvetica", "I", 8)
        pdf.cell(0, 5, "Reporte generado automaticamente por Medicare Pro", align="C")

        return pdf.output(dest="S").encode("latin-1", errors="replace")
    except Exception as exc:
        log_event("reportes", f"error_generar_reporte:{type(exc).__name__}:{exc}")
        return b""


def render_reporte_ejecutivo(mi_empresa: str):
    """Renderiza boton de descarga de reporte ejecutivo."""
    from core.export_utils import pdf_output_bytes

    st.markdown("### Reporte Ejecutivo PDF")
    st.caption("Resumen de pacientes, facturacion, stock y actividad reciente.")

    if st.button("Generar Reporte Ejecutivo PDF", width="stretch", type="primary", key="btn_reporte_ejecutivo"):
        with st.spinner("Generando reporte..."):
            pdf_bytes = generar_reporte_ejecutivo(mi_empresa)
            if pdf_bytes:
                st.download_button(
                    label="Descargar Reporte PDF",
                    data=pdf_bytes,
                    file_name=f"reporte_ejecutivo_{datetime.now().strftime('%Y%m%d')}.pdf",
                    mime="application/pdf",
                    width="stretch",
                    key="download_reporte_ejecutivo",
                )
                st.success("Reporte generado correctamente.")
            else:
                st.error("Error al generar el reporte.")
