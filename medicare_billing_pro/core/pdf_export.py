"""Exportación a PDF para Medicare Billing Pro."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from core.utils import safe_text, fmt_moneda, fmt_fecha, sanitize_filename

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    pass


def _build_pdf() -> "FPDF":
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=18)
    return pdf


def _header(pdf: "FPDF", titulo: str, empresa: str) -> None:
    pdf.set_fill_color(15, 38, 68)
    pdf.rect(0, 0, 210, 20, "F")
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.set_y(5)
    pdf.cell(0, 10, safe_text(titulo), ln=True, align="C")
    pdf.set_font("Arial", "", 8)
    pdf.cell(0, 4, safe_text(f"{empresa}  |  Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"), ln=True, align="C")
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(24)


def exportar_presupuesto_pdf(presupuesto: Dict[str, Any], empresa: str, items: List[Dict]) -> bytes:
    if not FPDF_DISPONIBLE:
        return b""
    pdf = _build_pdf()
    pdf.add_page()
    _header(pdf, "PRESUPUESTO", empresa)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, safe_text(f"N°: {presupuesto.get('numero', '—')}"), ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, safe_text(f"Cliente: {presupuesto.get('cliente_nombre', '—')}"), ln=True)
    pdf.cell(0, 6, safe_text(f"Fecha: {fmt_fecha(presupuesto.get('fecha', ''))}  |  Válido hasta: {fmt_fecha(presupuesto.get('valido_hasta', ''))}"), ln=True)
    pdf.ln(4)

    # Tabla de items
    pdf.set_fill_color(226, 232, 240)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(90, 7, "Concepto", border=1, fill=True)
    pdf.cell(25, 7, "Cantidad", border=1, fill=True, align="C")
    pdf.cell(30, 7, "Precio Unit.", border=1, fill=True, align="C")
    pdf.cell(30, 7, "Subtotal", border=1, fill=True, align="C")
    pdf.ln()

    total = 0.0
    pdf.set_font("Arial", "", 9)
    for item in items:
        subtotal = float(item.get("cantidad", 1)) * float(item.get("precio_unitario", 0))
        total += subtotal
        pdf.cell(90, 6, safe_text(str(item.get("concepto", ""))[:60]), border=1)
        pdf.cell(25, 6, str(item.get("cantidad", 1)), border=1, align="C")
        pdf.cell(30, 6, fmt_moneda(item.get("precio_unitario", 0)), border=1, align="R")
        pdf.cell(30, 6, fmt_moneda(subtotal), border=1, align="R")
        pdf.ln()

    pdf.set_font("Arial", "B", 11)
    pdf.cell(145, 8, "TOTAL", border=1, align="R")
    pdf.cell(30, 8, fmt_moneda(total), border=1, align="R")
    pdf.ln(8)

    if presupuesto.get("notas"):
        pdf.set_font("Arial", "I", 8)
        pdf.multi_cell(0, 5, safe_text(f"Notas: {presupuesto.get('notas', '')}"))

    return pdf.output()


def exportar_prefactura_pdf(prefactura: Dict[str, Any], empresa: str, items: List[Dict]) -> bytes:
    if not FPDF_DISPONIBLE:
        return b""
    pdf = _build_pdf()
    pdf.add_page()
    _header(pdf, "PRE-FACTURA", empresa)

    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 7, safe_text(f"N°: {prefactura.get('numero', '—')}"), ln=True)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, safe_text(f"Cliente: {prefactura.get('cliente_nombre', '—')}  |  CUIT/DNI: {prefactura.get('cliente_dni', '—')}"), ln=True)
    pdf.cell(0, 6, safe_text(f"Fecha: {fmt_fecha(prefactura.get('fecha', ''))}  |  Estado: {prefactura.get('estado', 'Pendiente')}"), ln=True)
    pdf.ln(4)

    pdf.set_fill_color(226, 232, 240)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(90, 7, "Concepto", border=1, fill=True)
    pdf.cell(25, 7, "Cantidad", border=1, fill=True, align="C")
    pdf.cell(30, 7, "Precio Unit.", border=1, fill=True, align="C")
    pdf.cell(30, 7, "Subtotal", border=1, fill=True, align="C")
    pdf.ln()

    total = 0.0
    pdf.set_font("Arial", "", 9)
    for item in items:
        subtotal = float(item.get("cantidad", 1)) * float(item.get("precio_unitario", 0))
        total += subtotal
        pdf.cell(90, 6, safe_text(str(item.get("concepto", ""))[:60]), border=1)
        pdf.cell(25, 6, str(item.get("cantidad", 1)), border=1, align="C")
        pdf.cell(30, 6, fmt_moneda(item.get("precio_unitario", 0)), border=1, align="R")
        pdf.cell(30, 6, fmt_moneda(subtotal), border=1, align="R")
        pdf.ln()

    pdf.set_font("Arial", "B", 11)
    pdf.cell(145, 8, "TOTAL", border=1, align="R")
    pdf.cell(30, 8, fmt_moneda(total), border=1, align="R")
    pdf.ln(8)

    if prefactura.get("notas"):
        pdf.set_font("Arial", "I", 8)
        pdf.multi_cell(0, 5, safe_text(f"Notas: {prefactura.get('notas', '')}"))

    return pdf.output()


def exportar_reporte_cobros_pdf(cobros: List[Dict], empresa: str, desde: str, hasta: str) -> bytes:
    if not FPDF_DISPONIBLE:
        return b""
    pdf = _build_pdf()
    pdf.add_page(orientation="L")
    _header(pdf, "REPORTE DE COBROS", empresa)

    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, safe_text(f"Periodo: {fmt_fecha(desde)} al {fmt_fecha(hasta)}  |  Registros: {len(cobros)}"), ln=True)
    pdf.ln(4)

    pdf.set_fill_color(226, 232, 240)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(28, 7, "Fecha", border=1, fill=True)
    pdf.cell(55, 7, "Cliente", border=1, fill=True)
    pdf.cell(50, 7, "Concepto", border=1, fill=True)
    pdf.cell(28, 7, "Método", border=1, fill=True)
    pdf.cell(28, 7, "Monto", border=1, fill=True, align="R")
    pdf.cell(28, 7, "Estado", border=1, fill=True)
    pdf.ln()

    total = 0.0
    pdf.set_font("Arial", "", 8)
    for c in cobros:
        monto = float(c.get("monto", 0) or 0)
        total += monto
        pdf.cell(28, 6, safe_text(fmt_fecha(c.get("fecha", ""))), border=1)
        pdf.cell(55, 6, safe_text(str(c.get("cliente_nombre", ""))[:35]), border=1)
        pdf.cell(50, 6, safe_text(str(c.get("concepto", ""))[:30]), border=1)
        pdf.cell(28, 6, safe_text(str(c.get("metodo_pago", ""))[:15]), border=1)
        pdf.cell(28, 6, fmt_moneda(monto), border=1, align="R")
        pdf.cell(28, 6, safe_text(str(c.get("estado", ""))[:15]), border=1)
        pdf.ln()

    pdf.set_font("Arial", "B", 10)
    pdf.cell(189, 8, "TOTAL COBRADO", border=1, align="R")
    pdf.cell(28, 8, fmt_moneda(total), border=1, align="R")

    return pdf.output()


def exportar_reporte_contable_pdf(
    empresa: str, mes: str,
    presupuestos: List[Dict], prefacturas: List[Dict], cobros: List[Dict]
) -> bytes:
    if not FPDF_DISPONIBLE:
        return b""
    pdf = _build_pdf()
    pdf.add_page()
    _header(pdf, f"REPORTE CONTABLE — {mes}", empresa)

    # Resumen
    total_presupuestado = sum(float(p.get("total", 0) or 0) for p in presupuestos)
    total_facturado = sum(float(p.get("total", 0) or 0) for p in prefacturas)
    total_cobrado = sum(float(c.get("monto", 0) or 0) for c in cobros)
    pendiente = total_facturado - total_cobrado

    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 8, "RESUMEN DEL MES", ln=True)
    pdf.ln(2)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, safe_text(f"Total presupuestado: {fmt_moneda(total_presupuestado)}  ({len(presupuestos)} presupuestos)"), ln=True)
    pdf.cell(0, 6, safe_text(f"Total facturado:     {fmt_moneda(total_facturado)}  ({len(prefacturas)} pre-facturas)"), ln=True)
    pdf.cell(0, 6, safe_text(f"Total cobrado:       {fmt_moneda(total_cobrado)}  ({len(cobros)} cobros)"), ln=True)
    pdf.cell(0, 6, safe_text(f"Pendiente de cobro:  {fmt_moneda(pendiente)}"), ln=True)
    pdf.ln(6)

    # Detalle de cobros
    if cobros:
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 7, "DETALLE DE COBROS", ln=True)
        pdf.set_fill_color(226, 232, 240)
        pdf.set_font("Arial", "B", 8)
        pdf.cell(28, 6, "Fecha", border=1, fill=True)
        pdf.cell(55, 6, "Cliente", border=1, fill=True)
        pdf.cell(40, 6, "Método", border=1, fill=True)
        pdf.cell(28, 6, "Monto", border=1, fill=True, align="R")
        pdf.ln()
        pdf.set_font("Arial", "", 8)
        for c in cobros:
            pdf.cell(28, 5, safe_text(fmt_fecha(c.get("fecha", ""))), border=1)
            pdf.cell(55, 5, safe_text(str(c.get("cliente_nombre", ""))[:35]), border=1)
            pdf.cell(40, 5, safe_text(str(c.get("metodo_pago", ""))[:22]), border=1)
            pdf.cell(28, 5, fmt_moneda(c.get("monto", 0)), border=1, align="R")
            pdf.ln()

    return pdf.output()
