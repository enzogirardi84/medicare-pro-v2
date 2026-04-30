"""Generacion del PDF integral de historia clinica con ReportLab."""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"

REPORTLAB_DISPONIBLE = True
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import Image as RLImage
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:
    REPORTLAB_DISPONIBLE = False
    colors = A4 = ParagraphStyle = getSampleStyleSheet = None
    RLImage = Paragraph = SimpleDocTemplate = Spacer = Table = TableStyle = None

from core._exports_helpers import collect_patient_sections
from core._exports_pdf_base import _BACKUP_SKIP_KEYS, backup_label_key
from core.export_utils import safe_text as _safe_text
from core.utils import mapa_detalles_pacientes
from features.historial.fechas import parse_registro_fecha_hora


_HISTORY_SKIP_KEYS = _BACKUP_SKIP_KEYS | frozenset(
    {
        "_id_local",
        "_fecha_dt",
        "adjunto_papel_tipo",
        "adjunto_papel_nombre",
        "fecha_iso",
    }
)

_HISTORY_PRIORITY_KEYS = [
    "fecha_hora_programada",
    "fecha_hora",
    "fecha",
    "hora",
    "fecha_programada",
    "creado_en",
    "fecha_evento",
    "hora_evento",
    "tipo",
    "tipo_evento",
    "categoria_evento",
    "accion",
    "estado",
    "estado_receta",
    "estado_clinico",
    "profesional",
    "firma",
    "firmado_por",
    "medico_nombre",
    "actor",
    "matricula",
    "med",
    "dosis",
    "frecuencia",
    "via",
    "detalle",
    "nota",
    "observaciones",
    "descripcion",
    "texto",
    "tipo_cuidado",
    "intervencion",
    "motivo",
    "motivo_estado",
    "turno",
    "escala",
    "puntaje",
    "interpretacion",
    "resultado",
    "TA",
    "FC",
    "FR",
    "Sat",
    "Temp",
    "HGT",
    "peso",
    "talla",
    "ingresos",
    "egresos",
    "balance",
    "insumo",
    "cantidad",
    "firmante",
    "vinculo",
    "dni_firmante",
]


def _history_escape_paragraph(value: Any) -> str:
    text = _safe_text(value or "-").strip() or "-"
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")


def _history_trim_value(value: Any, max_len: int = 50000) -> str:
    text = _safe_text(value).strip()
    if len(text) > max_len:
        return text[: max_len - 3] + "..."
    return text


def _history_record_datetime(record: Dict[str, Any]) -> Optional[datetime]:
    if not isinstance(record, dict):
        return None
    dt = parse_registro_fecha_hora(record)
    if dt:
        return dt
    raw = _safe_text(record.get("fecha_iso") or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        return parsed.astimezone().replace(tzinfo=None)
    return parsed


def _history_sort_records(records: Sequence[Dict[str, Any]]) -> List[Dict[str, Any]]:
    def _sort_key(record: Dict[str, Any]) -> Tuple[int, float, str]:
        dt = _history_record_datetime(record)
        if dt:
            return (0, dt.timestamp(), "")
        fallback = _safe_text(
            record.get("fecha")
            or record.get("fecha_hora")
            or record.get("fecha_hora_programada")
            or record.get("creado_en")
            or record.get("fecha_evento")
            or ""
        )
        return (1, 0.0, fallback)

    return sorted(records or [], key=_sort_key)


def _history_latest_record(records: Sequence[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    ordered = _history_sort_records(records)
    return ordered[-1] if ordered else None


def _history_record_summary(section_name: str, record: Optional[Dict[str, Any]]) -> str:
    if not record:
        return "Sin detalle."
    if section_name == "Signos Vitales":
        return (
            f"TA {_history_trim_value(record.get('TA', '-'))} | "
            f"FC {_history_trim_value(record.get('FC', '-'))} | "
            f"Sat {_history_trim_value(record.get('Sat', '-'))} | "
            f"Temp {_history_trim_value(record.get('Temp', '-'))}"
        )
    if section_name == "Balance Hidrico":
        return (
            f"Ingresos {_history_trim_value(record.get('ingresos', '-'))} | "
            f"Egresos {_history_trim_value(record.get('egresos', '-'))} | "
            f"Balance {_history_trim_value(record.get('balance', '-'))}"
        )
    if section_name == "Plan Terapeutico":
        return _history_trim_value(
            f"{record.get('med', 'Indicacion sin detalle')} | "
            f"{record.get('estado_receta', record.get('estado_clinico', 'Activa'))}",
        )
    if section_name == "Materiales Utilizados":
        return _history_trim_value(
            f"{record.get('insumo', record.get('material', 'Material'))} x {record.get('cantidad', '-')}",
        )
    if section_name == "Estudios Complementarios":
        return _history_trim_value(
            f"{record.get('tipo', 'Estudio')} | {record.get('detalle', 'Sin detalle')}",
        )
    if section_name == "Consentimientos":
        return _history_trim_value(
            f"{record.get('firmante', 'Firmante')} | {record.get('vinculo', 'Sin vinculo')} | DNI {record.get('dni_firmante', 'S/D')}",
        )

    for key in ("detalle", "nota", "observaciones", "texto", "descripcion", "motivo", "intervencion"):
        if record.get(key):
            return _history_trim_value(record.get(key))

    pieces = [
        record.get("tipo"),
        record.get("categoria_evento"),
        record.get("profesional"),
        record.get("firma"),
    ]
    summary = " | ".join(_safe_text(piece) for piece in pieces if piece not in (None, ""))
    return summary or "Registro sin resumen."


def _history_rows_from_record(record: Dict[str, Any]) -> List[Tuple[str, str]]:
    if not isinstance(record, dict):
        return []

    rows: List[Tuple[str, str]] = []
    seen = set()

    for key in _HISTORY_PRIORITY_KEYS:
        if key in record and key not in _HISTORY_SKIP_KEYS:
            value = record.get(key)
            if value not in (None, ""):
                rows.append((backup_label_key(key), _history_trim_value(value)))
                seen.add(key)

    for key, value in sorted(record.items()):
        if key in seen or key in _HISTORY_SKIP_KEYS or value in (None, ""):
            continue
        rows.append((backup_label_key(key), _history_trim_value(value)))

    if record.get("adjunto_papel_b64"):
        rows.append(("Adjunto", "Orden medica adjunta en el sistema."))
    elif record.get("adjunto_papel_nombre"):
        rows.append(("Adjunto", f"Archivo asociado: {_history_trim_value(record.get('adjunto_papel_nombre'), 180)}"))

    if record.get("imagen"):
        rows.append(("Adjunto", "Estudio o documento escaneado guardado en el sistema."))
    if record.get("base64_foto"):
        rows.append(("Adjunto", "Foto clinica guardada en el sistema."))
    if record.get("firma_b64") or record.get("firma_img"):
        rows.append(("Firma", "Firma digital registrada en el sistema."))

    return rows


def _history_record_heading(record: Dict[str, Any], fallback_index: int) -> str:
    fecha_dt = _history_record_datetime(record)
    fecha = fecha_dt.strftime("%d/%m/%Y %H:%M") if fecha_dt else _safe_text(
        record.get("fecha_hora_programada")
        or record.get("fecha_hora")
        or record.get("fecha")
        or record.get("creado_en")
        or record.get("fecha_evento")
        or f"Registro {fallback_index}"
    )
    tipo = _safe_text(record.get("tipo") or record.get("tipo_evento") or record.get("categoria_evento") or record.get("accion"))
    responsable = _safe_text(
        record.get("profesional")
        or record.get("firma")
        or record.get("firmado_por")
        or record.get("medico_nombre")
        or record.get("actor")
    )

    pieces = [fecha]
    if tipo:
        pieces.append(tipo)
    if responsable:
        pieces.append(f"Responsable: {responsable}")
    return " | ".join(piece for piece in pieces if piece)


def _history_recent_activity_rows(
    sections: Dict[str, List[Dict[str, Any]]],
    limit: int = 10,
) -> List[Tuple[str, str, str]]:
    rows: List[Tuple[datetime, str, str]] = []
    for section_name, records in sections.items():
        for record in records:
            dt = _history_record_datetime(record)
            if not dt:
                continue
            rows.append((dt, section_name, _history_record_summary(section_name, record)))

    rows.sort(key=lambda item: item[0], reverse=True)
    return [
        (dt.strftime("%d/%m/%Y %H:%M"), section_name, summary)
        for dt, section_name, summary in rows[:limit]
    ]


def _logo_cell() -> Any:
    for path in (
        ASSETS_DIR / "logo_medicare_pro.jpeg",
        ASSETS_DIR / "logo_medicare_pro.jpg",
        ASSETS_DIR / "logo_medicare_pro.png",
    ):
        if not path.exists() or RLImage is None:
            continue
        try:
            return RLImage(str(path), width=52, height=52)
        except Exception:
            continue
    return ""


def _resolve_responsable(profesional: Any, detalles: Dict[str, Any]) -> str:
    if isinstance(profesional, dict):
        value = profesional.get("nombre") or profesional.get("usuario_login") or ""
        if value:
            return _safe_text(value)
    if profesional not in (None, ""):
        return _safe_text(profesional)
    return _safe_text(
        detalles.get("medico_tratante")
        or detalles.get("medico")
        or detalles.get("medico_cabecera")
        or "Sistema"
    )


def build_history_pdf_bytes(session_state, paciente_sel, mi_empresa, profesional=None):
    if not REPORTLAB_DISPONIBLE:
        return None

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=28, leftMargin=28, topMargin=24, bottomMargin=28)
    page_width = A4[0] - doc.leftMargin - doc.rightMargin
    elements = []
    styles = getSampleStyleSheet()

    header_text_style = ParagraphStyle("HistoryHeaderText", parent=styles["Normal"], leading=18)
    normal_style = ParagraphStyle("HistoryBody", parent=styles["BodyText"], fontSize=8.6, leading=10.8, textColor=colors.HexColor("#334155"))
    label_style = ParagraphStyle("HistoryLabel", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8.2, leading=10.2, textColor=colors.HexColor("#0f172a"))
    title_style = ParagraphStyle("HistoryTitle", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=18, leading=22, alignment=1, textColor=colors.HexColor("#0f172a"), spaceAfter=4)
    subtitle_style = ParagraphStyle("HistorySubtitle", parent=styles["Heading3"], fontName="Helvetica-Bold", fontSize=10, leading=13, alignment=1, textColor=colors.HexColor("#0f766e"), spaceAfter=2)
    meta_style = ParagraphStyle("HistoryMeta", parent=styles["BodyText"], fontSize=8.3, leading=10.2, alignment=1, textColor=colors.HexColor("#64748b"), spaceAfter=10)
    section_style = ParagraphStyle("HistorySection", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=15, textColor=colors.HexColor("#0f766e"), spaceBefore=12, spaceAfter=6)
    item_title_style = ParagraphStyle("HistoryItemTitle", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=9.2, leading=11.4, textColor=colors.HexColor("#0f172a"), spaceAfter=3)
    metric_style = ParagraphStyle("HistoryMetric", parent=normal_style, alignment=1, textColor=colors.HexColor("#0f172a"), leading=13)
    table_header_style = ParagraphStyle("HistoryTableHeader", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=8, alignment=1, textColor=colors.white)

    def _section_band(title: str):
        paragraph = Paragraph(
            f'<font color="white"><b>{_history_escape_paragraph(title).upper()}</b></font>',
            ParagraphStyle("HistoryBandText", parent=styles["Normal"], fontName="Helvetica-Bold", fontSize=9, leading=14),
        )
        table = Table([[paragraph]], colWidths=[page_width])
        table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (0, 0), colors.HexColor("#162644")),
                    ("TOPPADDING", (0, 0), (0, 0), 5),
                    ("BOTTOMPADDING", (0, 0), (0, 0), 5),
                    ("LEFTPADDING", (0, 0), (0, 0), 8),
                ]
            )
        )
        return table

    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    nombre_empresa = _safe_text(detalles.get("empresa", mi_empresa) or mi_empresa or "MediCare")
    secciones = collect_patient_sections(session_state, paciente_sel)
    secciones_con_datos = {nombre: registros for nombre, registros in secciones.items() if registros}
    total_registros = sum(len(registros) for registros in secciones.values())
    total_secciones = len(secciones_con_datos)
    ultimo_global = None
    for registros in secciones.values():
        for registro in registros:
            dt = _history_record_datetime(registro)
            if dt and (ultimo_global is None or dt > ultimo_global):
                ultimo_global = dt

    nom_pac = paciente_sel.split(" - ")[0] if " - " in paciente_sel else paciente_sel
    generado = datetime.now().strftime("%d/%m/%Y %H:%M")
    responsable = _resolve_responsable(profesional, detalles)

    header_text = Paragraph(
        f'<font size="14" color="white"><b>{_history_escape_paragraph(nombre_empresa)}</b></font><br/>'
        f'<font size="9" color="#A0C8FF"><b>HISTORIA CLINICA DIGITAL INTEGRAL</b></font><br/>'
        f'<font size="7" color="#C8D2E6">Paciente: {_history_escape_paragraph(nom_pac)}   |   Generado: {generado}</font>',
        header_text_style,
    )
    header_badge = Paragraph(
        '<font size="10" color="white"><b>Historia<br/>Clinica</b></font>',
        ParagraphStyle("HistoryBadge", parent=styles["Normal"], alignment=1, leading=14),
    )
    header_table = Table([[_logo_cell(), header_text, header_badge]], colWidths=[60, max(page_width - 130, 320), 70])
    header_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#162644")),
                ("BACKGROUND", (2, 0), (2, 0), colors.HexColor("#0D5A50")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (0, 0), 8),
                ("LEFTPADDING", (1, 0), (1, 0), 12),
                ("TOPPADDING", (0, 0), (-1, -1), 10),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
            ]
        )
    )
    elements.append(header_table)
    elements.append(Spacer(1, 10))
    elements.append(Paragraph(f"<b>{_history_escape_paragraph(nombre_empresa.upper())}</b>", title_style))
    elements.append(Paragraph("HISTORIA CLINICA DIGITAL INTEGRAL", subtitle_style))
    elements.append(
        Paragraph(
            _history_escape_paragraph(
                f"Paciente: {paciente_sel} | Generado: {generado} | Responsable: {responsable}"
            ),
            meta_style,
        )
    )

    elements.append(_section_band("Datos del paciente"))
    elements.append(Spacer(1, 4))
    patient_table = Table(
        [
            [
                Paragraph("<b>Paciente</b>", label_style),
                Paragraph(_history_escape_paragraph(nom_pac), normal_style),
                Paragraph("<b>DNI</b>", label_style),
                Paragraph(_history_escape_paragraph(detalles.get("dni", "S/D")), normal_style),
            ],
            [
                Paragraph("<b>Fecha nac.</b>", label_style),
                Paragraph(_history_escape_paragraph(detalles.get("fnac", "S/D")), normal_style),
                Paragraph("<b>Sexo</b>", label_style),
                Paragraph(_history_escape_paragraph(detalles.get("sexo", "S/D")), normal_style),
            ],
            [
                Paragraph("<b>Obra social</b>", label_style),
                Paragraph(_history_escape_paragraph(detalles.get("obra_social", "S/D")), normal_style),
                Paragraph("<b>Telefono</b>", label_style),
                Paragraph(_history_escape_paragraph(detalles.get("telefono", "S/D")), normal_style),
            ],
            [
                Paragraph("<b>Domicilio</b>", label_style),
                Paragraph(_history_escape_paragraph(detalles.get("direccion", "S/D")), normal_style),
                Paragraph("<b>Estado</b>", label_style),
                Paragraph(_history_escape_paragraph(detalles.get("estado", "Activo")), normal_style),
            ],
        ],
        colWidths=[84, 170, 70, page_width - 324],
    )
    patient_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#cbd5e1")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#dbe4ee")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(patient_table)
    elements.append(Spacer(1, 8))

    risk_table = Table(
        [
            [
                Paragraph("<b>Alergias</b>", label_style),
                Paragraph(_history_escape_paragraph(detalles.get("alergias", "Sin datos")), normal_style),
            ],
            [
                Paragraph("<b>Patologias / riesgos</b>", label_style),
                Paragraph(_history_escape_paragraph(detalles.get("patologias", "Sin datos")), normal_style),
            ],
        ],
        colWidths=[120, page_width - 120],
    )
    risk_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#fff7ed")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#fdba74")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#fed7aa")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(risk_table)
    elements.append(Spacer(1, 12))

    overview_table = Table(
        [
            [
                Paragraph(f"<b>REGISTROS TOTALES</b><br/>{_history_escape_paragraph(str(total_registros))}", metric_style),
                Paragraph(f"<b>SECCIONES CON DATOS</b><br/>{_history_escape_paragraph(str(total_secciones))}", metric_style),
                Paragraph(
                    f"<b>ULTIMO EVENTO</b><br/>{_history_escape_paragraph(ultimo_global.strftime('%d/%m/%Y %H:%M') if ultimo_global else 'S/D')}",
                    metric_style,
                ),
            ]
        ],
        colWidths=[page_width / 3.0, page_width / 3.0, page_width / 3.0],
    )
    overview_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#ecfeff")),
                ("BOX", (0, 0), (-1, -1), 0.6, colors.HexColor("#67e8f9")),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#a5f3fc")),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    elements.append(overview_table)
    elements.append(Spacer(1, 12))

    if secciones_con_datos:
        elements.append(Paragraph("Indice de actividad por modulo", section_style))
        index_rows = [
            [
                Paragraph("<b>Modulo</b>", table_header_style),
                Paragraph("<b>Cantidad</b>", table_header_style),
                Paragraph("<b>Ultimo registro</b>", table_header_style),
            ]
        ]
        for section_name, records in sorted(secciones_con_datos.items(), key=lambda item: len(item[1]), reverse=True):
            ultimo = _history_latest_record(records)
            ultimo_dt = _history_record_datetime(ultimo or {})
            ultimo_txt = ultimo_dt.strftime("%d/%m/%Y %H:%M") if ultimo_dt else _safe_text((ultimo or {}).get("fecha", "S/D"))
            index_rows.append(
                [
                    Paragraph(_history_escape_paragraph(section_name), normal_style),
                    Paragraph(_history_escape_paragraph(str(len(records))), normal_style),
                    Paragraph(_history_escape_paragraph(ultimo_txt), normal_style),
                ]
            )
        index_table = Table(
            index_rows,
            colWidths=[page_width * 0.54, 72, page_width - (page_width * 0.54 + 72)],
            repeatRows=1,
        )
        index_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f766e")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 5),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ]
            )
        )
        elements.append(index_table)
        elements.append(Spacer(1, 12))

        recent_rows = _history_recent_activity_rows(secciones_con_datos, limit=10)
        if recent_rows:
            elements.append(Paragraph("Actividad reciente", section_style))
            recent_table = Table(
                [
                    [
                        Paragraph("<b>Fecha</b>", table_header_style),
                        Paragraph("<b>Seccion</b>", table_header_style),
                        Paragraph("<b>Resumen</b>", table_header_style),
                    ]
                ]
                + [
                    [
                        Paragraph(_history_escape_paragraph(fecha), normal_style),
                        Paragraph(_history_escape_paragraph(seccion), normal_style),
                        Paragraph(_history_escape_paragraph(resumen), normal_style),
                    ]
                    for fecha, seccion, resumen in recent_rows
                ],
                colWidths=[96, 144, page_width - 240],
                repeatRows=1,
            )
            recent_table.setStyle(
                TableStyle(
                    [
                        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1d4ed8")),
                        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eff6ff")]),
                        ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#bfdbfe")),
                        ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#dbeafe")),
                        ("VALIGN", (0, 0), (-1, -1), "TOP"),
                        ("TOPPADDING", (0, 0), (-1, -1), 5),
                        ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                    ]
                )
            )
            elements.append(recent_table)
            elements.append(Spacer(1, 10))

    diagnosticos_activos = [
        record
        for record in session_state.get("diagnosticos_db", [])
        if record.get("paciente") == paciente_sel
        and str(record.get("estado", "Activo")).strip().lower() not in ("resuelto", "descartado", "inactivo")
    ]
    if diagnosticos_activos:
        elements.append(Paragraph("Diagnosticos activos", section_style))
        diag_rows = [
            [
                Paragraph("<b>CIE / Codigo</b>", table_header_style),
                Paragraph("<b>Diagnostico</b>", table_header_style),
                Paragraph("<b>Tipo</b>", table_header_style),
                Paragraph("<b>Fecha</b>", table_header_style),
                Paragraph("<b>Profesional</b>", table_header_style),
            ]
        ]
        for record in diagnosticos_activos[:30]:
            diag_rows.append(
                [
                    Paragraph(_history_escape_paragraph(record.get("cie") or record.get("codigo", "-")), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("diagnostico") or record.get("descripcion", "-")), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("tipo", "-")), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("fecha", "-")), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("profesional", "-")), normal_style),
                ]
            )
        diag_table = Table(diag_rows, colWidths=[76, page_width * 0.34, 72, 82, page_width - (76 + page_width * 0.34 + 72 + 82)], repeatRows=1)
        diag_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#374151")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e5e7eb")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(diag_table)
        elements.append(Spacer(1, 10))

    meds_activas = [
        record
        for record in secciones.get("Plan Terapeutico", [])
        if str(record.get("estado_receta", record.get("estado_clinico", "Activa"))).strip().lower()
        not in ("suspendida", "cancelada", "modificada")
    ]
    if meds_activas:
        elements.append(Paragraph("Plan terapeutico activo", section_style))
        meds_rows = [
            [
                Paragraph("<b>Medicacion / Indicacion</b>", table_header_style),
                Paragraph("<b>Dosis / Posologia</b>", table_header_style),
                Paragraph("<b>Via</b>", table_header_style),
                Paragraph("<b>Fecha</b>", table_header_style),
                Paragraph("<b>Profesional</b>", table_header_style),
            ]
        ]
        for record in meds_activas[:20]:
            meds_rows.append(
                [
                    Paragraph(_history_escape_paragraph(record.get("med") or record.get("medicamento") or record.get("descripcion") or "-"), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("dosis") or record.get("posologia") or "-"), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("via") or record.get("via_administracion") or "-"), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("fecha", "-")), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("medico_nombre") or record.get("profesional", "-")), normal_style),
                ]
            )
        meds_table = Table(meds_rows, colWidths=[page_width * 0.36, 110, 60, 82, page_width - (page_width * 0.36 + 252)], repeatRows=1)
        meds_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0D5A50")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#f0fdf4"), colors.white]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#d1fae5")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(meds_table)
        elements.append(Spacer(1, 10))

    vitales_recientes = _history_sort_records(secciones.get("Signos Vitales", []))[-5:]
    if vitales_recientes:
        elements.append(Paragraph("Ultimos controles de signos vitales", section_style))
        vital_rows = [
            [
                Paragraph("<b>Fecha</b>", table_header_style),
                Paragraph("<b>TA</b>", table_header_style),
                Paragraph("<b>FC</b>", table_header_style),
                Paragraph("<b>FR</b>", table_header_style),
                Paragraph("<b>SpO2</b>", table_header_style),
                Paragraph("<b>Temp</b>", table_header_style),
                Paragraph("<b>HGT</b>", table_header_style),
                Paragraph("<b>Registrado por</b>", table_header_style),
            ]
        ]
        for record in reversed(vitales_recientes):
            vital_rows.append(
                [
                    Paragraph(_history_escape_paragraph(_history_record_heading(record, 0).split(" | ")[0]), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("TA", "-")), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("FC", "-")), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("FR", "-")), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("Sat", "-")), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("Temp", "-")), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("HGT", "-")), normal_style),
                    Paragraph(_history_escape_paragraph(record.get("registrado_por") or record.get("firma", "-")), normal_style),
                ]
            )
        vital_table = Table(vital_rows, colWidths=[96, 54, 40, 40, 46, 44, 42, page_width - 362], repeatRows=1)
        vital_table.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#162644")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f9fafb")]),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        elements.append(vital_table)
        elements.append(Spacer(1, 10))

    if not secciones_con_datos:
        elements.append(Paragraph("Resumen clinico", section_style))
        elements.append(
            Paragraph(
                _history_escape_paragraph(
                    "El paciente aun no tiene registros clinicos asociados. Este PDF conserva los datos administrativos y el estado actual del legajo."
                ),
                normal_style,
            )
        )
    else:
        for section_name, records in secciones.items():
            if not records:
                continue
            ordered_records = _history_sort_records(records)
            latest_record = ordered_records[-1]
            latest_dt = _history_record_datetime(latest_record)
            latest_text = latest_dt.strftime("%d/%m/%Y %H:%M") if latest_dt else _safe_text(
                latest_record.get("fecha")
                or latest_record.get("fecha_hora")
                or latest_record.get("fecha_hora_programada")
                or latest_record.get("fecha_evento")
                or "S/D"
            )

            elements.append(Paragraph(f"{section_name} ({len(ordered_records)})", section_style))
            elements.append(
                Paragraph(
                    _history_escape_paragraph(
                        f"Ultimo registro: {latest_text} | Resumen: {_history_record_summary(section_name, latest_record)}"
                    ),
                    normal_style,
                )
            )
            elements.append(Spacer(1, 5))

            for idx, record in enumerate(ordered_records, start=1):
                elements.append(Paragraph(_history_escape_paragraph(_history_record_heading(record, idx)), item_title_style))
                resumen = _history_record_summary(section_name, record)
                if resumen:
                    elements.append(Paragraph(_history_escape_paragraph(resumen), normal_style))
                    elements.append(Spacer(1, 3))

                rows = _history_rows_from_record(record)
                if rows:
                    detail_table = Table(
                        [
                            [
                                Paragraph(f"<b>{_history_escape_paragraph(label)}</b>", label_style),
                                Paragraph(_history_escape_paragraph(value), normal_style),
                            ]
                            for label, value in rows
                        ],
                        colWidths=[130, page_width - 130],
                    )
                    detail_table.setStyle(
                        TableStyle(
                            [
                                ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.HexColor("#f8fafc"), colors.white]),
                                ("BOX", (0, 0), (-1, -1), 0.45, colors.HexColor("#cbd5e1")),
                                ("INNERGRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#e2e8f0")),
                                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("TOPPADDING", (0, 0), (-1, -1), 5),
                                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                            ]
                        )
                    )
                    elements.append(detail_table)
                else:
                    elements.append(Paragraph("Registro sin campos legibles.", normal_style))

                elements.append(Spacer(1, 7))

    doc.build(elements)
    return buffer.getvalue()
