"""Generación de PDFs para el módulo APS/Dispensario."""

from __future__ import annotations

from datetime import datetime

from core.export_utils import pdf_output_bytes, safe_text

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF
    FPDF_DISPONIBLE = True
except ImportError:
    pass


def generar_pdf_historial_paciente(paciente_id, registros, fd, fh, centro_salud_id):
    """Genera un PDF portrait con el historial APS del paciente."""
    if not FPDF_DISPONIBLE:
        return None

    class HistorialPDF(FPDF):
        def header(self):
            self.set_fill_color(25, 55, 95)
            self.rect(0, 0, 210, 18, "F")
            self.set_font("Arial", "B", 16)
            self.set_text_color(255, 255, 255)
            self.cell(0, 10, "HISTORIAL APS  |  MEDICARE PRO", ln=True, align="C")
            self.set_font("Arial", "", 9)
            self.cell(0, 5, safe_text(f"Centro: {centro_salud_id}  |  Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"), ln=True, align="C")
            self.ln(2)

        def footer(self):
            self.set_y(-15)
            self.set_font("Arial", "I", 8)
            self.set_text_color(128, 128, 128)
            self.cell(0, 10, safe_text(f"Pagina {self.page_no()} / {{nb}}"), align="C")

    pdf = HistorialPDF(orientation="P")
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.set_fill_color(240, 245, 250)
    pdf.set_draw_color(200, 210, 220)
    pdf.rect(10, 28, 190, 22, "DF")
    pdf.set_xy(14, 30)
    pdf.set_font("Arial", "B", 12)
    pdf.set_text_color(25, 55, 95)
    pdf.cell(0, 6, safe_text(f"Paciente: {paciente_id}"), ln=True)
    pdf.set_xy(14, 37)
    pdf.set_font("Arial", "", 10)
    pdf.set_text_color(60, 60, 60)
    pdf.cell(0, 5, safe_text(f"Periodo del reporte: {fd}  al  {fh}"), ln=True)
    pdf.ln(10)

    if not registros:
        pdf.set_font("Arial", "", 11)
        pdf.set_text_color(180, 60, 60)
        pdf.cell(0, 10, "No hay registros para el filtro y periodo seleccionados.", ln=True, align="C")
        return pdf_output_bytes(pdf)

    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(25, 55, 95)
    pdf.cell(0, 6, safe_text(f"Total de registros: {len(registros)}"), ln=True)
    pdf.ln(3)

    for i, item in enumerate(registros[:300], 1):
        y_start = pdf.get_y()
        if y_start > 260:
            pdf.add_page()
            y_start = pdf.get_y()
        if i % 2 == 0:
            pdf.set_fill_color(248, 250, 252)
            pdf.rect(10, y_start, 190, 22, "F")
        pdf.set_xy(14, y_start + 1)
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(25, 55, 95)
        pdf.cell(0, 5, safe_text(f"#{i}  [{item.get('tipo', '-')}]  {item.get('titulo', '-')}"), ln=True)
        pdf.set_xy(14, y_start + 6)
        pdf.set_font("Arial", "", 8)
        pdf.set_text_color(80, 80, 80)
        pdf.cell(0, 4, safe_text(f"Fecha: {item.get('fecha', '-')}    |    Registrado por: {item.get('registrado_por', '-')}"), ln=True)
        detalle = item.get("detalle", "")
        if detalle and detalle.strip():
            pdf.set_xy(14, y_start + 10)
            pdf.set_font("Arial", "", 8)
            pdf.set_text_color(60, 60, 60)
            pdf.multi_cell(182, 4, safe_text(f"Detalle: {detalle}"))
        pdf.set_draw_color(200, 210, 220)
        pdf.line(10, y_start + 22, 200, y_start + 22)
        pdf.set_xy(10, y_start + 22)

    return pdf_output_bytes(pdf)


def generar_pdf_reporte_aps(titulo, registros, periodo, centro_salud_id):
    """Genera un PDF landscape con los registros del reporte APS."""
    if not FPDF_DISPONIBLE:
        return None
    pdf = FPDF(orientation="L")
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 10, safe_text(titulo), ln=True, align="C")
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 8, safe_text(f"Periodo: {periodo}  |  Centro: {centro_salud_id}"), ln=True, align="C")
    pdf.ln(4)
    for i, r in enumerate(registros[:250], 1):
        pdf.set_font("Arial", "B", 9)
        pdf.cell(0, 6, safe_text(f"Registro #{i}"), ln=True)
        pdf.set_font("Arial", "", 8)
        for k, v in sorted(r.items()):
            pdf.multi_cell(0, 5, safe_text(f"  {k}: {v}"))
        pdf.ln(1)
    return pdf_output_bytes(pdf)
