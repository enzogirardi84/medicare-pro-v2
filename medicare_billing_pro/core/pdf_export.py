"""Exportacion a PDF para Medicare Billing Pro."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Sequence

from core.utils import fmt_fecha, fmt_moneda, safe_text

FPDF_DISPONIBLE = False
try:
    from fpdf import FPDF

    FPDF_DISPONIBLE = True
except ImportError:
    pass

BLUE = (15, 38, 68)
BLUE_2 = (30, 64, 104)
TEAL = (20, 184, 166)
INK = (15, 23, 42)
MUTED = (100, 116, 139)
LINE = (203, 213, 225)
SOFT = (248, 250, 252)


class BillingPDF(FPDF):
    def footer(self):
        self.set_y(-14)
        self.set_font("Arial", "", 7)
        self.set_text_color(*MUTED)
        self.cell(0, 5, safe_text(f"Medicare Billing Pro | Pagina {self.page_no()}"), align="C")


def _build_pdf(orientation: str = "P") -> "BillingPDF":
    pdf = BillingPDF(orientation=orientation, unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(14, 14, 14)
    return pdf


def _pdf_bytes(pdf: "BillingPDF") -> bytes:
    data = pdf.output()
    if isinstance(data, bytes):
        return data
    if isinstance(data, bytearray):
        return bytes(data)
    if isinstance(data, str):
        return data.encode("latin-1")
    return bytes(data or b"")


def _header(pdf: "BillingPDF", titulo: str, empresa: str, subtitulo: str = "") -> None:
    page_w = pdf.w
    pdf.set_fill_color(*BLUE)
    pdf.rect(0, 0, page_w, 27, "F")
    pdf.set_fill_color(*TEAL)
    pdf.rect(0, 27, page_w, 1.2, "F")
    pdf.set_xy(14, 7)
    pdf.set_font("Arial", "B", 15)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, safe_text(titulo), ln=True)
    pdf.set_x(14)
    pdf.set_font("Arial", "", 8)
    line = f"{empresa} | Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}"
    if subtitulo:
        line = f"{line} | {subtitulo}"
    pdf.cell(0, 5, safe_text(line), ln=True)
    pdf.set_y(36)
    pdf.set_text_color(*INK)


def _section_title(pdf: "BillingPDF", text: str) -> None:
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*BLUE)
    pdf.cell(0, 6, safe_text(text), ln=True)
    pdf.set_text_color(*INK)


def _info_grid(pdf: "BillingPDF", pairs: Sequence[tuple[str, Any]], cols: int = 2) -> None:
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = usable / cols
    label_h = 4
    value_h = 6
    for idx, (label, value) in enumerate(pairs):
        if idx % cols == 0 and idx:
            pdf.ln(label_h + value_h + 2)
        x = pdf.l_margin + (idx % cols) * col_w
        y = pdf.get_y()
        pdf.set_xy(x, y)
        pdf.set_font("Arial", "B", 7)
        pdf.set_text_color(*MUTED)
        pdf.cell(col_w - 3, label_h, safe_text(str(label).upper()), ln=True)
        pdf.set_xy(x, y + label_h)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(*INK)
        pdf.cell(col_w - 3, value_h, safe_text(str(value or "-"))[:58], border=1)
    pdf.ln(label_h + value_h + 5)


def _table_header(pdf: "BillingPDF", headers: Sequence[str], widths: Sequence[float]) -> None:
    pdf.set_fill_color(*BLUE_2)
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Arial", "B", 8)
    for header, width in zip(headers, widths):
        pdf.cell(width, 7, safe_text(header), border=1, align="C", fill=True)
    pdf.ln()
    pdf.set_text_color(*INK)


def _table_row(pdf: "BillingPDF", values: Sequence[Any], widths: Sequence[float], aligns: Sequence[str], fill: bool = False) -> None:
    pdf.set_fill_color(*SOFT)
    pdf.set_font("Arial", "", 8)
    for value, width, align in zip(values, widths, aligns):
        pdf.cell(width, 6, safe_text(str(value or "-"))[:42], border=1, align=align, fill=fill)
    pdf.ln()


def _total_box(pdf: "BillingPDF", label: str, value: float) -> None:
    pdf.ln(3)
    pdf.set_x(pdf.w - pdf.r_margin - 70)
    pdf.set_fill_color(220, 252, 231)
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(*INK)
    pdf.cell(38, 9, safe_text(label), border=1, align="R", fill=True)
    pdf.cell(32, 9, safe_text(fmt_moneda(value)), border=1, align="R", fill=True)
    pdf.ln(12)


def _notes(pdf: "BillingPDF", text: str) -> None:
    if not text:
        return
    _section_title(pdf, "Notas")
    pdf.set_font("Arial", "", 8)
    pdf.multi_cell(0, 5, safe_text(text))
    pdf.ln(2)


def exportar_presupuesto_pdf(presupuesto: Dict[str, Any], empresa: str, items: List[Dict]) -> bytes:
    if not FPDF_DISPONIBLE:
        return b""
    pdf = _build_pdf()
    pdf.add_page()
    _header(pdf, "Presupuesto", empresa, str(presupuesto.get("numero", "")))
    _info_grid(
        pdf,
        [
            ("Numero", presupuesto.get("numero", "-")),
            ("Estado", presupuesto.get("estado", "Borrador")),
            ("Cliente", presupuesto.get("cliente_nombre", "-")),
            ("Fecha", fmt_fecha(presupuesto.get("fecha", ""))),
            ("Valido hasta", fmt_fecha(presupuesto.get("valido_hasta", ""))),
            ("Documento", "Presupuesto no fiscal"),
        ],
    )
    _section_title(pdf, "Conceptos")
    widths = [92, 20, 33, 33]
    _table_header(pdf, ["Concepto", "Cant.", "Precio Unit.", "Subtotal"], widths)
    total = 0.0
    for idx, item in enumerate(items):
        cantidad = float(item.get("cantidad", 1) or 1)
        precio = float(item.get("precio_unitario", 0) or 0)
        subtotal = cantidad * precio
        total += subtotal
        _table_row(
            pdf,
            [item.get("concepto", ""), f"{cantidad:g}", fmt_moneda(precio), fmt_moneda(subtotal)],
            widths,
            ["L", "C", "R", "R"],
            fill=idx % 2 == 1,
        )
    _total_box(pdf, "TOTAL", total)
    _notes(pdf, str(presupuesto.get("notas", "") or ""))
    return _pdf_bytes(pdf)


def exportar_prefactura_pdf(prefactura: Dict[str, Any], empresa: str, items: List[Dict]) -> bytes:
    if not FPDF_DISPONIBLE:
        return b""
    pdf = _build_pdf()
    pdf.add_page()
    _header(pdf, "Pre-factura", empresa, str(prefactura.get("numero", "")))
    _info_grid(
        pdf,
        [
            ("Numero", prefactura.get("numero", "-")),
            ("Estado", prefactura.get("estado", "Pendiente")),
            ("Cliente", prefactura.get("cliente_nombre", "-")),
            ("DNI / CUIT", prefactura.get("cliente_dni", "-")),
            ("Fecha", fmt_fecha(prefactura.get("fecha", ""))),
            ("Cobrado", fmt_moneda(prefactura.get("cobrado", 0))),
            ("Saldo", fmt_moneda(prefactura.get("saldo", prefactura.get("total", 0)))),
            ("Documento", "Pre-factura"),
        ],
    )
    _section_title(pdf, "Conceptos")
    widths = [92, 20, 33, 33]
    _table_header(pdf, ["Concepto", "Cant.", "Precio Unit.", "Subtotal"], widths)
    total = 0.0
    for idx, item in enumerate(items):
        cantidad = float(item.get("cantidad", 1) or 1)
        precio = float(item.get("precio_unitario", 0) or 0)
        subtotal = cantidad * precio
        total += subtotal
        _table_row(
            pdf,
            [item.get("concepto", ""), f"{cantidad:g}", fmt_moneda(precio), fmt_moneda(subtotal)],
            widths,
            ["L", "C", "R", "R"],
            fill=idx % 2 == 1,
        )
    _total_box(pdf, "TOTAL", total)
    _notes(pdf, str(prefactura.get("notas", "") or ""))
    return _pdf_bytes(pdf)


def exportar_reporte_cobros_pdf(cobros: List[Dict], empresa: str, desde: str, hasta: str) -> bytes:
    if not FPDF_DISPONIBLE:
        return b""
    pdf = _build_pdf("L")
    pdf.add_page()
    _header(pdf, "Reporte de cobros", empresa, f"{fmt_fecha(desde)} al {fmt_fecha(hasta)}")
    total = sum(float(c.get("monto", 0) or 0) for c in cobros)
    _info_grid(pdf, [("Registros", len(cobros)), ("Total cobrado", fmt_moneda(total)), ("Desde", fmt_fecha(desde)), ("Hasta", fmt_fecha(hasta))], cols=4)
    widths = [24, 58, 70, 34, 34, 28]
    _table_header(pdf, ["Fecha", "Cliente", "Concepto", "Metodo", "Monto", "Estado"], widths)
    for idx, cobro in enumerate(cobros):
        _table_row(
            pdf,
            [
                fmt_fecha(cobro.get("fecha", "")),
                cobro.get("cliente_nombre", ""),
                cobro.get("concepto", ""),
                cobro.get("metodo_pago", ""),
                fmt_moneda(float(cobro.get("monto", 0) or 0)),
                cobro.get("estado", ""),
            ],
            widths,
            ["L", "L", "L", "L", "R", "L"],
            fill=idx % 2 == 1,
        )
    _total_box(pdf, "TOTAL", total)
    return _pdf_bytes(pdf)


def exportar_recibo_cobro_pdf(
    cobro: Dict[str, Any],
    empresa: str,
    prefactura: Dict[str, Any] | None = None,
    saldo_restante: float | None = None,
) -> bytes:
    if not FPDF_DISPONIBLE:
        return b""
    pdf = _build_pdf()
    pdf.add_page()
    numero = str(cobro.get("numero") or cobro.get("id") or "")[:16].upper()
    _header(pdf, "Recibo de cobro", empresa, numero)
    _info_grid(
        pdf,
        [
            ("Recibo", numero or "-"),
            ("Fecha", fmt_fecha(cobro.get("fecha", ""))),
            ("Cliente", cobro.get("cliente_nombre", "-")),
            ("Metodo", cobro.get("metodo_pago", "-")),
            ("Concepto", cobro.get("concepto", "-")),
            ("Estado", cobro.get("estado", "Cobrado")),
            ("Pre-factura", (prefactura or {}).get("numero", cobro.get("prefactura_id", "-"))),
            ("Saldo restante", fmt_moneda(saldo_restante if saldo_restante is not None else 0)),
        ],
    )
    _section_title(pdf, "Detalle del pago")
    widths = [74, 42, 42]
    _table_header(pdf, ["Descripcion", "Metodo", "Importe"], widths)
    _table_row(
        pdf,
        [
            cobro.get("concepto", "Cobro"),
            cobro.get("metodo_pago", ""),
            fmt_moneda(float(cobro.get("monto", 0) or 0)),
        ],
        widths,
        ["L", "L", "R"],
    )
    _total_box(pdf, "RECIBIDO", float(cobro.get("monto", 0) or 0))
    _notes(pdf, str(cobro.get("notas", "") or "Documento no fiscal. Comprobante interno de recepcion de pago."))
    return _pdf_bytes(pdf)


def exportar_estado_cuenta_pdf(
    cliente: Dict[str, Any],
    empresa: str,
    movimientos: List[Dict[str, Any]],
    total_debe: float,
    total_haber: float,
    saldo: float,
) -> bytes:
    if not FPDF_DISPONIBLE:
        return b""
    pdf = _build_pdf("L")
    pdf.add_page()
    _header(pdf, "Estado de cuenta", empresa, str(cliente.get("nombre", "")))
    _info_grid(
        pdf,
        [
            ("Cliente", cliente.get("nombre", "-")),
            ("DNI / CUIT", cliente.get("dni", "-")),
            ("Email", cliente.get("email", "-")),
            ("Telefono", cliente.get("telefono", "-")),
            ("Debe", fmt_moneda(total_debe)),
            ("Haber", fmt_moneda(total_haber)),
            ("Saldo", fmt_moneda(saldo)),
            ("Registros", len(movimientos)),
        ],
        cols=4,
    )
    widths = [24, 30, 42, 76, 30, 30, 30]
    _table_header(pdf, ["Fecha", "Tipo", "Numero", "Detalle", "Debe", "Haber", "Saldo"], widths)
    for idx, mov in enumerate(movimientos[:34]):
        _table_row(
            pdf,
            [
                fmt_fecha(mov.get("fecha", "")),
                mov.get("tipo", ""),
                mov.get("numero", ""),
                mov.get("detalle", ""),
                fmt_moneda(mov.get("debe", 0)) if mov.get("debe") else "",
                fmt_moneda(mov.get("haber", 0)) if mov.get("haber") else "",
                fmt_moneda(mov.get("saldo", 0)),
            ],
            widths,
            ["L", "L", "L", "L", "R", "R", "R"],
            fill=idx % 2 == 1,
        )
    if len(movimientos) > 34:
        pdf.set_font("Arial", "I", 8)
        pdf.set_text_color(*MUTED)
        pdf.cell(0, 6, safe_text(f"Se muestran 34 de {len(movimientos)} movimientos. El Excel incluye el detalle completo."), ln=True)
        pdf.set_text_color(*INK)
    return _pdf_bytes(pdf)


def exportar_factura_arca_pdf(factura: Dict[str, Any], empresa: str, items: List[Dict], config: Dict[str, Any] | None = None) -> bytes:
    if not FPDF_DISPONIBLE:
        return b""
    config = config or {}
    pdf = _build_pdf()
    pdf.add_page()
    tipo = str(factura.get("tipo_comprobante", "C") or "C")
    _header(pdf, f"Factura {tipo}", empresa, str(factura.get("numero", "")))
    _info_grid(
        pdf,
        [
            ("Razon social", config.get("razon_social") or empresa),
            ("CUIT emisor", config.get("cuit", "-")),
            ("Domicilio fiscal", config.get("domicilio_fiscal", "-")),
            ("Condicion IVA", config.get("condicion_iva", "-")),
            ("Numero", factura.get("numero", "-")),
            ("Punto de venta", str(factura.get("punto_venta", 1)).zfill(4)),
            ("Cliente", factura.get("cliente_nombre", "-")),
            ("CUIT/DNI cliente", factura.get("cliente_dni", "-")),
            ("Fecha", fmt_fecha(factura.get("fecha", ""))),
            ("Estado", factura.get("estado", "Borrador")),
            ("CAE", factura.get("cae") or "Pendiente"),
            ("Vto CAE", fmt_fecha(factura.get("cae_vencimiento", "")) if factura.get("cae_vencimiento") else "-"),
        ],
    )
    _section_title(pdf, "Conceptos")
    widths = [92, 20, 33, 33]
    _table_header(pdf, ["Concepto", "Cant.", "Precio Unit.", "Subtotal"], widths)
    total_items = 0.0
    for idx, item in enumerate(items):
        cantidad = float(item.get("cantidad", 1) or 1)
        precio = float(item.get("precio_unitario", 0) or 0)
        subtotal = cantidad * precio
        total_items += subtotal
        _table_row(pdf, [item.get("concepto", ""), f"{cantidad:g}", fmt_moneda(precio), fmt_moneda(subtotal)], widths, ["L", "C", "R", "R"], fill=idx % 2 == 1)

    pdf.ln(3)
    widths2 = [46, 42]
    pdf.set_x(pdf.w - pdf.r_margin - sum(widths2))
    _table_header(pdf, ["Resumen", "Importe"], widths2)
    for idx, (label, amount) in enumerate([
        ("Neto", float(factura.get("neto", total_items) or 0)),
        ("IVA", float(factura.get("iva", 0) or 0)),
        ("Total", float(factura.get("total", total_items) or 0)),
    ]):
        pdf.set_x(pdf.w - pdf.r_margin - sum(widths2))
        _table_row(pdf, [label, fmt_moneda(amount)], widths2, ["L", "R"], fill=idx % 2 == 1)
    _notes(pdf, str(factura.get("notas") or config.get("leyenda_factura") or "Comprobante interno preparado para emision ARCA."))
    return _pdf_bytes(pdf)


def exportar_reporte_contable_pdf(
    empresa: str,
    mes: str,
    presupuestos: List[Dict],
    prefacturas: List[Dict],
    cobros: List[Dict],
) -> bytes:
    if not FPDF_DISPONIBLE:
        return b""
    pdf = _build_pdf()
    pdf.add_page()
    _header(pdf, "Reporte contable", empresa, mes)

    total_presupuestado = sum(float(p.get("total", 0) or 0) for p in presupuestos)
    total_facturado = sum(float(p.get("total", 0) or 0) for p in prefacturas)
    total_cobrado = sum(float(c.get("monto", 0) or 0) for c in cobros)
    pendiente = total_facturado - total_cobrado

    _section_title(pdf, "Resumen")
    widths = [70, 42, 28]
    _table_header(pdf, ["Indicador", "Monto", "Cantidad"], widths)
    rows = [
        ("Presupuestado", total_presupuestado, len(presupuestos)),
        ("Pre-facturado", total_facturado, len(prefacturas)),
        ("Cobrado", total_cobrado, len(cobros)),
        ("Pendiente", pendiente, "-"),
    ]
    for idx, (label, amount, count) in enumerate(rows):
        _table_row(pdf, [label, fmt_moneda(amount), count], widths, ["L", "R", "C"], fill=idx % 2 == 1)

    if cobros:
        pdf.ln(4)
        _section_title(pdf, "Cobros del mes")
        widths = [24, 58, 48, 30, 28]
        _table_header(pdf, ["Fecha", "Cliente", "Concepto", "Metodo", "Monto"], widths)
        for idx, cobro in enumerate(cobros[:24]):
            _table_row(
                pdf,
                [
                    fmt_fecha(cobro.get("fecha", "")),
                    cobro.get("cliente_nombre", ""),
                    cobro.get("concepto", ""),
                    cobro.get("metodo_pago", ""),
                    fmt_moneda(float(cobro.get("monto", 0) or 0)),
                ],
                widths,
                ["L", "L", "L", "L", "R"],
                fill=idx % 2 == 1,
            )
        if len(cobros) > 24:
            pdf.set_font("Arial", "I", 8)
            pdf.set_text_color(*MUTED)
            pdf.cell(0, 6, safe_text(f"Se muestran 24 de {len(cobros)} cobros. El Excel incluye el detalle completo."), ln=True)
            pdf.set_text_color(*INK)

    return _pdf_bytes(pdf)
