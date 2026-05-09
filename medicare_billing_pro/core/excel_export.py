"""Exportación a Excel para Medicare Billing Pro."""
from __future__ import annotations

from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List

from core.utils import fmt_fecha, fmt_moneda, sanitize_filename

XLSX_DISPONIBLE = False
try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
    XLSX_DISPONIBLE = True
except ImportError:
    pass


def _style_header(ws, headers: List[str], row: int = 1) -> None:
    fill = PatternFill(start_color="0F2644", end_color="0F2644", fill_type="solid")
    font = Font(name="Arial", bold=True, color="FFFFFF", size=10)
    alignment = Alignment(horizontal="center", vertical="center")
    for col, h in enumerate(headers, 1):
        cell = ws.cell(row=row, column=col, value=h)
        cell.fill = fill
        cell.font = font
        cell.alignment = alignment


def _auto_width(ws, min_width: int = 10, max_width: int = 45) -> None:
    for col_cells in ws.columns:
        max_len = 0
        col_letter = get_column_letter(col_cells[0].column)
        for cell in col_cells:
            if cell.value:
                max_len = max(max_len, len(str(cell.value)))
        ws.column_dimensions[col_letter].width = max(min_width, min(max_len + 2, max_width))


def exportar_clientes_excel(clientes: List[Dict], empresa: str) -> bytes:
    if not XLSX_DISPONIBLE:
        return b""
    wb = Workbook()
    ws = wb.active
    ws.title = "Clientes"
    headers = ["Nombre", "DNI/CUIT", "Email", "Teléfono", "Dirección", "Condición Fiscal", "Notas"]
    _style_header(ws, headers)
    for i, c in enumerate(clientes, 2):
        ws.cell(row=i, column=1, value=c.get("nombre", ""))
        ws.cell(row=i, column=2, value=c.get("dni", ""))
        ws.cell(row=i, column=3, value=c.get("email", ""))
        ws.cell(row=i, column=4, value=c.get("telefono", ""))
        ws.cell(row=i, column=5, value=c.get("direccion", ""))
        ws.cell(row=i, column=6, value=c.get("condicion_fiscal", ""))
        ws.cell(row=i, column=7, value=c.get("notas", ""))
    _auto_width(ws)
    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def exportar_cobros_excel(cobros: List[Dict], empresa: str) -> bytes:
    if not XLSX_DISPONIBLE:
        return b""
    wb = Workbook()
    ws = wb.active
    ws.title = "Cobros"
    headers = ["Fecha", "Cliente", "Concepto", "Método de Pago", "Monto", "Estado", "Notas"]
    _style_header(ws, headers)
    for i, c in enumerate(cobros, 2):
        ws.cell(row=i, column=1, value=fmt_fecha(c.get("fecha", "")))
        ws.cell(row=i, column=2, value=c.get("cliente_nombre", ""))
        ws.cell(row=i, column=3, value=c.get("concepto", ""))
        ws.cell(row=i, column=4, value=c.get("metodo_pago", ""))
        ws.cell(row=i, column=5, value=float(c.get("monto", 0) or 0))
        ws.cell(row=i, column=6, value=c.get("estado", ""))
        ws.cell(row=i, column=7, value=c.get("notas", ""))
    _auto_width(ws)
    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def exportar_presupuestos_excel(presupuestos: List[Dict], empresa: str) -> bytes:
    if not XLSX_DISPONIBLE:
        return b""
    wb = Workbook()
    ws = wb.active
    ws.title = "Presupuestos"
    headers = ["Número", "Fecha", "Cliente", "Total", "Estado", "Válido hasta"]
    _style_header(ws, headers)
    for i, p in enumerate(presupuestos, 2):
        ws.cell(row=i, column=1, value=p.get("numero", ""))
        ws.cell(row=i, column=2, value=fmt_fecha(p.get("fecha", "")))
        ws.cell(row=i, column=3, value=p.get("cliente_nombre", ""))
        ws.cell(row=i, column=4, value=float(p.get("total", 0) or 0))
        ws.cell(row=i, column=5, value=p.get("estado", ""))
        ws.cell(row=i, column=6, value=fmt_fecha(p.get("valido_hasta", "")))
    _auto_width(ws)
    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def exportar_prefacturas_excel(prefacturas: List[Dict], empresa: str) -> bytes:
    if not XLSX_DISPONIBLE:
        return b""
    wb = Workbook()
    ws = wb.active
    ws.title = "Pre-facturas"
    headers = ["Número", "Fecha", "Cliente", "DNI/CUIT", "Total", "Estado"]
    _style_header(ws, headers)
    for i, p in enumerate(prefacturas, 2):
        ws.cell(row=i, column=1, value=p.get("numero", ""))
        ws.cell(row=i, column=2, value=fmt_fecha(p.get("fecha", "")))
        ws.cell(row=i, column=3, value=p.get("cliente_nombre", ""))
        ws.cell(row=i, column=4, value=p.get("cliente_dni", ""))
        ws.cell(row=i, column=5, value=float(p.get("total", 0) or 0))
        ws.cell(row=i, column=6, value=p.get("estado", ""))
    _auto_width(ws)
    output = BytesIO()
    wb.save(output)
    return output.getvalue()


def exportar_reporte_contable_excel(
    empresa: str, mes: str,
    presupuestos: List[Dict], prefacturas: List[Dict], cobros: List[Dict]
) -> bytes:
    if not XLSX_DISPONIBLE:
        return b""
    wb = Workbook()

    # Hoja resumen
    ws = wb.active
    ws.title = "Resumen"
    total_presupuestado = sum(float(p.get("total", 0) or 0) for p in presupuestos)
    total_facturado = sum(float(p.get("total", 0) or 0) for p in prefacturas)
    total_cobrado = sum(float(c.get("monto", 0) or 0) for c in cobros)
    pendiente = total_facturado - total_cobrado

    ws.cell(row=1, column=1, value=f"REPORTE CONTABLE — {mes}").font = Font(bold=True, size=14)
    ws.cell(row=3, column=1, value="Concepto").font = Font(bold=True)
    ws.cell(row=3, column=2, value="Monto").font = Font(bold=True)
    for i, (label, val) in enumerate([
        ("Total Presupuestado", total_presupuestado),
        ("Total Facturado", total_facturado),
        ("Total Cobrado", total_cobrado),
        ("Pendiente de Cobro", pendiente),
    ], 4):
        ws.cell(row=i, column=1, value=label)
        ws.cell(row=i, column=2, value=val)
    _auto_width(ws)

    # Hoja cobros
    ws2 = wb.create_sheet("Cobros")
    headers = ["Fecha", "Cliente", "Concepto", "Método", "Monto", "Estado"]
    _style_header(ws2, headers)
    for i, c in enumerate(cobros, 2):
        ws2.cell(row=i, column=1, value=fmt_fecha(c.get("fecha", "")))
        ws2.cell(row=i, column=2, value=c.get("cliente_nombre", ""))
        ws2.cell(row=i, column=3, value=c.get("concepto", ""))
        ws2.cell(row=i, column=4, value=c.get("metodo_pago", ""))
        ws2.cell(row=i, column=5, value=float(c.get("monto", 0) or 0))
        ws2.cell(row=i, column=6, value=c.get("estado", ""))
    _auto_width(ws2)

    # Hoja prefacturas
    ws3 = wb.create_sheet("Pre-facturas")
    headers3 = ["Número", "Fecha", "Cliente", "Total", "Estado"]
    _style_header(ws3, headers3)
    for i, p in enumerate(prefacturas, 2):
        ws3.cell(row=i, column=1, value=p.get("numero", ""))
        ws3.cell(row=i, column=2, value=fmt_fecha(p.get("fecha", "")))
        ws3.cell(row=i, column=3, value=p.get("cliente_nombre", ""))
        ws3.cell(row=i, column=4, value=float(p.get("total", 0) or 0))
        ws3.cell(row=i, column=5, value=p.get("estado", ""))
    _auto_width(ws3)

    output = BytesIO()
    wb.save(output)
    return output.getvalue()
