import base64
import io
import json
import os
import tempfile
from pathlib import Path

import pandas as pd
from fpdf import FPDF

# --- Nuevas importaciones para la Historia Clínica Avanzada ---
REPORTLAB_DISPONIBLE = True
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:
    REPORTLAB_DISPONIBLE = False
    colors = None
    A4 = None
    ParagraphStyle = None
    getSampleStyleSheet = None
    KeepTogether = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None

from core.export_utils import pdf_output_bytes, safe_text
from core.utils import decodificar_base64_seguro, mapa_detalles_pacientes

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def _patient_signature_bytes(session_state, paciente_sel):
    consentimientos = [x for x in session_state.get("consentimientos_db", []) if x.get("paciente") == paciente_sel]
    for registro in reversed(consentimientos):
        if registro.get("firma_b64"):
            firma_bytes = decodificar_base64_seguro(registro["firma_b64"])
            if firma_bytes:
                return firma_bytes

    firmas = [x for x in session_state.get("firmas_tactiles_db", []) if x.get("paciente") == paciente_sel]
    for registro in reversed(firmas):
        if registro.get("firma_img"):
            firma_bytes = decodificar_base64_seguro(registro["firma_img"])
            if firma_bytes:
                return firma_bytes
    return None


def _doctor_signature_bytes(record):
    firma_b64 = record.get("firma_b64", "")
    if not firma_b64:
        return None
    firma_bytes = decodificar_base64_seguro(firma_b64)
    return firma_bytes or None


def _order_attachment_note(record):
    nombre = record.get("adjunto_papel_nombre", "").strip()
    if not nombre:
        return ""
    return f"Orden medica adjunta en sistema: {nombre}"


def collect_patient_sections(session_state, paciente_sel):
    return {
        "Auditoria de Presencia": [x for x in session_state.get("checkin_db", []) if x.get("paciente") == paciente_sel],
        "Visitas y Agenda": [x for x in session_state.get("agenda_db", []) if x.get("paciente") == paciente_sel],
        "Emergencias y Ambulancia": [x for x in session_state.get("emergencias_db", []) if x.get("paciente") == paciente_sel],
        "Enfermeria y Plan de Cuidados": [x for x in session_state.get("cuidados_enfermeria_db", []) if x.get("paciente") == paciente_sel],
        "Escalas Clinicas": [x for x in session_state.get("escalas_clinicas_db", []) if x.get("paciente") == paciente_sel],
        "Auditoria Legal": [x for x in session_state.get("auditoria_legal_db", []) if x.get("paciente") == paciente_sel],
        "Procedimientos y Evoluciones": [x for x in session_state.get("evoluciones_db", []) if x.get("paciente") == paciente_sel],
        "Estudios Complementarios": [x for x in session_state.get("estudios_db", []) if x.get("paciente") == paciente_sel],
        "Materiales Utilizados": [x for x in session_state.get("consumos_db", []) if x.get("paciente") == paciente_sel],
        "Registro de Heridas": [x for x in session_state.get("fotos_heridas_db", []) if x.get("paciente") == paciente_sel],
        "Signos Vitales": [x for x in session_state.get("vitales_db", []) if x.get("paciente") == paciente_sel],
        "Control Pediatrico": [x for x in session_state.get("pediatria_db", []) if x.get("paciente") == paciente_sel],
        "Balance Hidrico": [x for x in session_state.get("balance_db", []) if x.get("paciente") == paciente_sel],
        "Plan Terapeutico": [x for x in session_state.get("indicaciones_db", []) if x.get("paciente") == paciente_sel],
        "Consentimientos": [x for x in session_state.get("consentimientos_db", []) if x.get("paciente") == paciente_sel],
    }


def build_patient_excel_bytes(session_state, paciente_sel):
    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    sheets = {"Paciente": pd.DataFrame([{"paciente": paciente_sel, **detalles}])}

    for section_name, records in collect_patient_sections(session_state, paciente_sel).items():
        if not records:
            continue
        df = pd.DataFrame(records).drop(columns=["paciente", "empresa"], errors="ignore")
        sheets[section_name[:31]] = df

    output = io.BytesIO()
    engine = None
    try:
        import openpyxl  # noqa: F401
        engine = "openpyxl"
    except Exception:
        try:
            import xlsxwriter  # noqa: F401
            engine = "xlsxwriter"
        except Exception:
            return None

    with pd.ExcelWriter(output, engine=engine) as writer:
        for sheet_name, df in sheets.items():
            df.to_excel(writer, index=False, sheet_name=sheet_name[:31])

    output.seek(0)
    return output.getvalue()


def build_patient_json_bytes(session_state, paciente_sel):
    payload = {
        "paciente": paciente_sel,
        "detalles": mapa_detalles_pacientes(session_state).get(paciente_sel, {}),
        "secciones": collect_patient_sections(session_state, paciente_sel),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _insert_logo(pdf_obj, y_offset: float = 8.0):
    posibles = [
        ASSETS_DIR / "logo_medicare_pro.jpeg",
        ASSETS_DIR / "logo_medicare_pro.jpg",
        ASSETS_DIR / "logo_medicare_pro.png",
    ]
    for ruta in posibles:
        if ruta.exists():
            try:
                pdf_obj.image(str(ruta), x=10, y=y_offset, w=26)
                return
            except Exception:
                pass


class RespaldoClinicoPDF(FPDF):
    """FPDF con pie de página: contexto del paciente y numeración."""

    def __init__(self, empresa_footer: str, paciente_footer: str):
        super().__init__(unit="mm", format="A4")
        self._emp_f = (empresa_footer or "")[:72]
        self._pac_f = (paciente_footer or "")[:48]

    def footer(self):
        self.set_y(-13)
        self.set_font("Arial", "I", 7)
        self.set_text_color(100, 116, 139)
        usable = self.w - self.l_margin - self.r_margin
        self.set_x(self.l_margin)
        left = safe_text(f"MediCare · {self._emp_f} · {self._pac_f}")
        if len(left) > 92:
            left = left[:89] + "..."
        self.cell(usable * 0.68, 4, left, align="L")
        self.cell(usable * 0.32, 4, safe_text(f"Pag. {self.page_no()}/{{nb}}"), align="R", ln=True)
        self.set_text_color(0, 0, 0)


def _section_title(pdf, title):
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.set_x(pdf.l_margin)
    pdf.set_fill_color(230, 238, 250)
    pdf.set_text_color(21, 37, 69)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, safe_text(title), ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)


def _usable_width(pdf):
    return max(20, getattr(pdf, "epw", pdf.w - pdf.l_margin - pdf.r_margin))


def _write_multiline_text(pdf, text, line_height=6, indent=0):
    content = safe_text(text).strip()
    if not content:
        return

    width = max(20, _usable_width(pdf) - indent)
    x_base = pdf.l_margin + indent

    for paragraph in content.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            pdf.ln(line_height)
            continue
        pdf.set_x(x_base)
        pdf.multi_cell(width, line_height, paragraph, border=0)


def _write_pairs(pdf, pairs):
    for label, value in pairs:
        if value in [None, ""]:
            continue
        label_txt = safe_text(label).strip()
        value_txt = safe_text(value).strip()
        if not value_txt:
            continue
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(0, 5, f"{label_txt}:", ln=True)
        pdf.set_font("Arial", "", 9)
        _write_multiline_text(pdf, value_txt, line_height=6, indent=4)
        pdf.ln(1)


# --- Respaldo clínico (PDF): etiquetas legibles y diseño unificado ---

_BACKUP_SKIP_KEYS = frozenset(
    {
        "paciente",
        "empresa",
        "imagen",
        "base64_foto",
        "firma_b64",
        "firma_img",
        "adjunto_papel_b64",
        "adjunto_papel_tipo",
        "contenido",
    }
)

_BACKUP_MAX_VALUE_LEN = 480

_BACKUP_FIELD_LABELS = {
    "fecha": "Fecha",
    "F": "Fecha",
    "H": "Hora",
    "fecha_evento": "Fecha del evento",
    "hora_evento": "Hora del evento",
    "tipo_evento": "Tipo de evento",
    "categoria_evento": "Categoría",
    "triage_grado": "Triage",
    "prioridad": "Prioridad",
    "motivo": "Motivo",
    "profesional": "Profesional",
    "firma": "Profesional / firma",
    "matricula": "Matrícula",
    "medico_nombre": "Médico",
    "medico_matricula": "Matrícula médico",
    "med": "Medicación / indicación",
    "estado_receta": "Estado receta",
    "estado_clinico": "Estado clínico",
    "observaciones": "Observaciones",
    "nota": "Nota",
    "tipo_cuidado": "Tipo de cuidado",
    "intervencion": "Intervención",
    "turno": "Turno",
    "escala": "Escala",
    "puntaje": "Puntaje",
    "interpretacion": "Interpretación",
    "detalle": "Detalle",
    "insumo": "Insumo / material",
    "cantidad": "Cantidad",
    "TA": "Tensión arterial",
    "FC": "Frecuencia cardíaca",
    "FR": "Frecuencia respiratoria",
    "Sat": "Saturación O2",
    "Temp": "Temperatura",
    "HGT": "Glucemia",
    "ingresos": "Ingresos",
    "egresos": "Egresos",
    "balance": "Balance",
    "fecha_registro": "Fecha registro",
    "accion": "Acción",
    "detalle_aud": "Detalle",
    "firmante": "Firmante",
    "vinculo": "Vínculo",
    "dni_firmante": "DNI firmante",
    "telefono": "Teléfono",
    "obra_social": "Obra social",
    "direccion": "Domicilio",
    "direccion_evento": "Domicilio del evento",
}


_BACKUP_PRIORITY_KEYS = [
    "fecha",
    "F",
    "H",
    "fecha_evento",
    "hora_evento",
    "categoria_evento",
    "tipo_evento",
    "triage_grado",
    "prioridad",
    "profesional",
    "firma",
    "medico_nombre",
    "matricula",
    "med",
    "estado_receta",
    "estado_clinico",
    "tipo_cuidado",
    "turno",
    "escala",
    "puntaje",
    "motivo",
    "observaciones",
    "nota",
    "detalle",
    "tipo",
    "insumo",
    "cantidad",
    "TA",
    "FC",
    "FR",
    "Sat",
    "Temp",
    "HGT",
    "ingresos",
    "egresos",
    "balance",
    "accion",
]


def _backup_label_key(key: str) -> str:
    if key in _BACKUP_FIELD_LABELS:
        return _BACKUP_FIELD_LABELS[key]
    return str(key).replace("_", " ").strip().title()


def _backup_sort_key_record(rec: dict) -> str:
    for k in ("fecha", "fecha_evento", "F", "fecha_registro", "fecha_suspension", "hora_evento"):
        v = rec.get(k)
        if v not in (None, ""):
            return str(v)
    return ""


def _backup_sorted_records(records: list) -> list:
    if not records:
        return []
    return sorted(records, key=_backup_sort_key_record)


def _backup_latest_record(records: list) -> dict | None:
    s = _backup_sorted_records(records)
    return s[-1] if s else None


def _backup_trim_value(val) -> str:
    t = safe_text(val).strip()
    if len(t) > _BACKUP_MAX_VALUE_LEN:
        return t[: _BACKUP_MAX_VALUE_LEN - 3] + "..."
    return t


def _backup_rows_from_record(record: dict) -> list[tuple[str, str]]:
    if not record:
        return []
    rows: list[tuple[str, str]] = []
    seen: set[str] = set()
    for pk in _BACKUP_PRIORITY_KEYS:
        if pk in record and pk not in _BACKUP_SKIP_KEYS:
            val = record.get(pk)
            if val not in (None, ""):
                rows.append((_backup_label_key(pk), _backup_trim_value(val)))
                seen.add(pk)
    for k, v in sorted(record.items()):
        if k in seen or k in _BACKUP_SKIP_KEYS or v in (None, ""):
            continue
        rows.append((_backup_label_key(k), _backup_trim_value(v)))
    return rows[:18]


def _section_title_backup(pdf: FPDF, title: str) -> None:
    if pdf.get_y() > 248:
        pdf.add_page()
    pdf.set_x(pdf.l_margin)
    pdf.set_fill_color(236, 253, 245)
    pdf.set_text_color(15, 118, 110)
    pdf.set_draw_color(13, 148, 136)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, safe_text(title), ln=True, fill=True)
    pdf.set_line_width(0.25)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(3)
    pdf.set_text_color(0, 0, 0)


def _backup_split_paciente_sel(paciente_sel: str) -> tuple[str, str]:
    s = (paciente_sel or "").strip()
    if " - " in s:
        a, b = s.split(" - ", 1)
        return a.strip(), b.strip()
    return s, ""


def _backup_draw_module_index(pdf: FPDF, session_state, paciente_sel: str) -> None:
    sections = collect_patient_sections(session_state, paciente_sel)
    usable = pdf.w - pdf.l_margin - pdf.r_margin
    w_mod = usable * 0.71
    w_cnt = usable - w_mod

    pdf.set_font("Arial", "B", 8)
    pdf.set_fill_color(51, 65, 85)
    pdf.set_text_color(255, 255, 255)
    pdf.set_x(pdf.l_margin)
    pdf.cell(w_mod, 6, safe_text("Modulo"), border=1, fill=True, ln=0)
    pdf.cell(w_cnt, 6, safe_text("Cantidad"), border=1, fill=True, ln=True, align="R")

    pdf.set_text_color(30, 41, 59)
    pdf.set_font("Arial", "", 8)
    for i, (name, recs) in enumerate(sections.items()):
        if pdf.get_y() > 268:
            pdf.add_page()
        n = len(recs)
        if i % 2 == 0:
            pdf.set_fill_color(248, 250, 252)
        else:
            pdf.set_fill_color(255, 255, 255)
        pdf.set_x(pdf.l_margin)
        pdf.cell(w_mod, 5, safe_text(name)[:64], border=1, fill=True, ln=0)
        pdf.set_font("Arial", "B" if n else "", 8)
        pdf.cell(w_cnt, 5, safe_text(str(n)), border=1, fill=True, ln=True, align="R")
        pdf.set_font("Arial", "", 8)
    pdf.ln(4)


# =====================================================================
# MOTOR REPORTLAB: HISTORIA CLÍNICA INTEGRAL (CORREGIDA)
# =====================================================================
def build_history_pdf_bytes(session_state, paciente_sel, mi_empresa, profesional=None):
    if not REPORTLAB_DISPONIBLE:
        return None

    # La historia clinica integral depende de ReportLab; si falta, la vista muestra un fallback amigable.
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=40, bottomMargin=40)
    elements = []
    styles = getSampleStyleSheet()

    # --- Estilos base ---
    title_style = styles['Heading1']
    title_style.alignment = 1  
    subtitle_style = styles['Heading3']
    subtitle_style.alignment = 1
    
    section_style = ParagraphStyle(
        'Section', parent=styles['Heading2'], 
        textColor=colors.HexColor("#1E3A8A"), 
        spaceAfter=10, spaceBefore=15
    )
    
    normal_style = styles['Normal']
    normal_style.fontSize = 9

    # --- Helper para evitar que ReportLab se rompa con caracteres y forzar saltos ---
    def _limpiar_texto(texto):
        if texto in [None, ""]: return "-"
        t = str(texto).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        return t.replace("\n", "<br/>")

    # --- 1. Cabecera Institucional ---
    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    nombre_empresa = detalles.get("empresa", mi_empresa)
    
    elements.append(Paragraph(f"<b>{_limpiar_texto(nombre_empresa).upper()}</b>", title_style))
    elements.append(Paragraph("HISTORIA CLÍNICA DIGITAL INTEGRAL", subtitle_style))
    elements.append(Spacer(1, 15))

    # --- 2. Panel de Datos Demográficos ---
    datos_paciente = [
        ["Paciente:", Paragraph(_limpiar_texto(paciente_sel.split(" - ")[0]), normal_style), "DNI:", Paragraph(_limpiar_texto(detalles.get("dni")), normal_style)],
        ["Fecha Nac.:", Paragraph(_limpiar_texto(detalles.get("fnac")), normal_style), "Sexo:", Paragraph(_limpiar_texto(detalles.get("sexo")), normal_style)],
        ["Obra Social:", Paragraph(_limpiar_texto(detalles.get("obra_social")), normal_style), "Teléfono:", Paragraph(_limpiar_texto(detalles.get("telefono")), normal_style)],
        ["Domicilio:", Paragraph(_limpiar_texto(detalles.get("direccion")), normal_style), "Estado:", Paragraph(_limpiar_texto(detalles.get("estado", "Activo")), normal_style)]
    ]
    
    t_paciente = Table(datos_paciente, colWidths=[70, 180, 70, 120])
    t_paciente.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#F3F4F6")),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME', (2, 0), (2, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    elements.append(t_paciente)
    
    riesgos_data = [
        ["Alergias:", Paragraph(_limpiar_texto(detalles.get("alergias", "Sin datos")), normal_style)],
        ["Riesgos/Patologías:", Paragraph(_limpiar_texto(detalles.get("patologias", "Sin datos")), normal_style)]
    ]
    t_riesgos = Table(riesgos_data, colWidths=[100, 340])
    t_riesgos.setStyle(TableStyle([
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor("#991B1B")), 
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
    ]))
    elements.append(t_riesgos)
    elements.append(Spacer(1, 20))

    # --- Función Auxiliar Blindada para Tablas ---
    def _crear_tabla_seccion(titulo, cabeceras, claves_datos, registros, anchos_columnas):
        if not registros:
            return
        elements.append(Paragraph(titulo, section_style))
        
        # Estilos específicos para celdas de tablas
        header_style = ParagraphStyle('Header', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.whitesmoke, alignment=1)
        cell_center = ParagraphStyle('CellCenter', parent=styles['Normal'], fontSize=8, alignment=1)
        cell_left = ParagraphStyle('CellLeft', parent=styles['Normal'], fontSize=8, alignment=0)
        
        datos_tabla = [[Paragraph(c, header_style) for c in cabeceras]]
        
        for reg in registros:
            fila = []
            for clave in claves_datos:
                valor = _limpiar_texto(reg.get(clave, "-"))
                # Los textos largos se alinean a la izquierda, los números/fechas al centro
                estilo = cell_left if clave in ["med", "insumo"] else cell_center
                fila.append(Paragraph(valor, estilo))
            datos_tabla.append(fila)
            
        t = Table(datos_tabla, colWidths=anchos_columnas, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#374151")),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#F9FAFB")]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(t)
        elements.append(Spacer(1, 15))

    # --- 3. Renderizado de Secciones ---
    
    # Evoluciones y Enfermería
    evoluciones = session_state.get("evoluciones_db", [])
    cuidados = session_state.get("cuidados_enfermeria_db", [])
    registros_clinicos = [r for r in evoluciones + cuidados if r.get("paciente") == paciente_sel]
    
    if registros_clinicos:
        elements.append(Paragraph("Evoluciones Clínicas y Enfermería", section_style))
        for reg in sorted(registros_clinicos, key=lambda x: x.get("fecha", "")):
            fecha = _limpiar_texto(reg.get("fecha", "S/D"))
            firma = _limpiar_texto(reg.get("firma", reg.get("profesional", "S/D")))
            nota = _limpiar_texto(reg.get("nota", reg.get("observaciones", "Sin detalle")))
            
            bloque = []
            bloque.append(Paragraph(f"<b>{fecha}</b> | Profesional: {firma}", styles['Italic']))
            bloque.append(Spacer(1, 3))
            bloque.append(Paragraph(nota, normal_style))
            bloque.append(Spacer(1, 10))
            elements.append(KeepTogether(bloque))

    # Signos Vitales
    vits = [v for v in session_state.get("vitales_db", []) if v.get("paciente") == paciente_sel]
    _crear_tabla_seccion(
        "Control de Signos Vitales",
        ["Fecha", "T.A.", "F.C.", "F.R.", "SatO2", "Temp", "HGT"],
        ["fecha", "TA", "FC", "FR", "Sat", "Temp", "HGT"],
        vits, [95, 60, 50, 50, 50, 50, 50] # Ancho de fecha expandido a 95
    )

    # Balance Hídrico
    balances = [b for b in session_state.get("balance_db", []) if b.get("paciente") == paciente_sel]
    _crear_tabla_seccion(
        "Balance Hídrico",
        ["Fecha", "Turno", "Ingresos", "Egresos", "Balance Total", "Firma"],
        ["fecha", "turno", "ingresos", "egresos", "balance", "firma"],
        balances, [95, 100, 55, 55, 65, 100] # Ancho de fecha expandido
    )

    # Plan Terapéutico
    meds = [m for m in session_state.get("indicaciones_db", []) if m.get("paciente") == paciente_sel]
    _crear_tabla_seccion(
        "Plan Terapéutico (Histórico y Activo)",
        ["Fecha", "Medicación e Indicación", "Estado", "Profesional"],
        ["fecha", "med", "estado_receta", "medico_nombre"],
        meds, [95, 230, 60, 100] # Ancho de fecha expandido, medicacion a 230
    )

    # Materiales Utilizados
    materiales = [m for m in session_state.get("consumos_db", []) if m.get("paciente") == paciente_sel]
    _crear_tabla_seccion(
        "Materiales e Insumos Utilizados",
        ["Fecha", "Insumo / Descripción", "Cantidad", "Firma"],
        ["fecha", "insumo", "cantidad", "firma"],
        materiales, [95, 220, 60, 100]
    )

    doc.build(elements)
    return buffer.getvalue()


# =====================================================================
# EXPORTACIONES RESTANTES (MANTIENEN FPDF)
# =====================================================================
def build_backup_pdf_bytes(session_state, paciente_sel, mi_empresa, profesional=None):
    from datetime import datetime

    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    empresa = detalles.get("empresa", mi_empresa)
    generado = datetime.now().strftime("%d/%m/%Y %H:%M")
    nom_pac, dni_del_id = _backup_split_paciente_sel(paciente_sel)
    dni_final = (detalles.get("dni") or dni_del_id or "").strip() or "S/D"
    pie_paciente = f"{nom_pac} (DNI {dni_final})" if dni_final != "S/D" else nom_pac

    pdf = RespaldoClinicoPDF(empresa, pie_paciente)
    try:
        pdf.alias_nb_pages()
    except Exception:
        pass
    pdf.set_auto_page_break(auto=True, margin=20)
    pdf.set_left_margin(14)
    pdf.set_right_margin(14)
    pdf.add_page()

    band_h = 38.0
    pdf.set_fill_color(240, 253, 250)
    pdf.rect(0, 0, 210, band_h, "F")
    pdf.set_draw_color(13, 148, 136)
    pdf.set_line_width(0.55)
    pdf.line(0, band_h, 210, band_h)

    _insert_logo(pdf, 9.0)

    pdf.set_xy(40, 6)
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 5, safe_text(empresa), ln=True)
    pdf.set_x(40)
    pdf.set_text_color(13, 148, 136)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 5, safe_text("Respaldo clinico del paciente"), ln=True)
    pdf.set_x(40)
    pdf.set_text_color(30, 41, 59)
    pdf.set_font("Arial", "B", 10)
    sub_nom = safe_text(nom_pac)
    if dni_final != "S/D":
        sub_nom += safe_text(f"  ·  DNI: {dni_final}")
    pdf.cell(0, 5, sub_nom, ln=True)
    pdf.set_x(40)
    pdf.set_text_color(100, 116, 139)
    pdf.set_font("Arial", "", 8)
    pdf.cell(0, 4, safe_text(f"Generado: {generado}  ·  Documento para archivo, impresion o auditoria"), ln=True)
    pdf.set_text_color(0, 0, 0)
    pdf.set_y(band_h + 5)

    _section_title_backup(pdf, "1. Datos demograficos y alertas")
    _write_pairs(
        pdf,
        [
            ("Nombre (legajo)", nom_pac),
            ("DNI", dni_final),
            ("Fecha de nacimiento", detalles.get("fnac", "S/D")),
            ("Sexo", detalles.get("sexo", "S/D")),
            ("Domicilio", detalles.get("direccion", "S/D")),
            ("Obra social", detalles.get("obra_social", "S/D")),
            ("Telefono", detalles.get("telefono", "S/D")),
            ("Estado del legajo", detalles.get("estado", "Activo")),
            ("Alergias", detalles.get("alergias", "Sin datos")),
            ("Patologias / riesgos", detalles.get("patologias", "Sin datos")),
        ],
    )

    _section_title_backup(pdf, "2. Indice de actividad por modulo")
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(71, 85, 105)
    _write_multiline_text(
        pdf,
        "Vista rapida del volumen de informacion cargada. Los modulos sin registros no se repiten en el detalle (seccion 3).",
        line_height=4,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)
    _backup_draw_module_index(pdf, session_state, paciente_sel)

    _section_title_backup(pdf, "3. Detalle por modulo (ultimo registro por fecha)")
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(71, 85, 105)
    _write_multiline_text(
        pdf,
        "Solo modulos con al menos un registro. Se muestran campos del movimiento mas reciente (orden por fecha cuando existe).",
        line_height=4,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(2)

    for section_name, records in collect_patient_sections(session_state, paciente_sel).items():
        if not records:
            continue

        if pdf.get_y() > 250:
            pdf.add_page()

        pdf.set_font("Arial", "B", 10)
        pdf.set_text_color(15, 118, 110)
        pdf.cell(0, 6, safe_text(section_name), ln=True)
        pdf.set_font("Arial", "", 9)
        pdf.set_text_color(71, 85, 105)
        pdf.cell(0, 5, safe_text(f"{len(records)} registro(s) en este modulo"), ln=True)
        pdf.set_text_color(0, 0, 0)

        ultimo = _backup_latest_record(records)
        if not ultimo:
            pdf.ln(2)
            continue

        ref_fecha = ""
        for fk in ("fecha", "fecha_evento", "F"):
            if ultimo.get(fk) not in (None, ""):
                ref_fecha = str(ultimo.get(fk))
                break
        if ref_fecha:
            pdf.set_font("Arial", "I", 8)
            pdf.set_text_color(100, 116, 139)
            pdf.cell(0, 4, safe_text(f"Ultimo registro (referencia temporal): {ref_fecha}"), ln=True)
            pdf.set_text_color(0, 0, 0)

        filas = _backup_rows_from_record(ultimo)
        pdf.set_font("Arial", "", 9)
        _write_pairs(pdf, filas)

        nota_adjunto = _order_attachment_note(ultimo)
        if nota_adjunto:
            pdf.set_font("Arial", "I", 8)
            _write_pairs(pdf, [("Adjunto en sistema", nota_adjunto)])

        pdf.ln(2)
        pdf.set_draw_color(226, 232, 240)
        y_sep = pdf.get_y()
        pdf.line(pdf.l_margin, y_sep, pdf.w - pdf.r_margin, y_sep)
        pdf.ln(5)

    pdf.ln(3)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(71, 85, 105)
    _write_multiline_text(
        pdf,
        "Resumen operativo MediCare: no sustituye la exportacion Historia clinica integral (PDF) cuando se requiere el detalle completo de todos los eventos.",
        line_height=4,
    )
    pdf.set_text_color(0, 0, 0)

    y_base = max(pdf.get_y() + 8, 232)
    if y_base > 255:
        pdf.add_page()
        y_base = 235

    lm = pdf.l_margin
    rm = pdf.w - pdf.r_margin
    mid = lm + (rm - lm) / 2

    pdf.set_draw_color(100, 116, 139)
    pdf.line(lm, y_base, mid - 4, y_base)
    pdf.line(mid + 4, y_base, rm, y_base)

    pdf.set_xy(lm, y_base + 2)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(mid - lm - 4, 4, safe_text("Profesional (genera / valida)"), ln=True, align="C")
    pdf.set_x(lm)
    pdf.set_font("Arial", "", 8)
    pdf.cell(mid - lm - 4, 4, safe_text((profesional or {}).get("nombre", "S/D")), ln=True, align="C")
    pdf.set_x(lm)
    pdf.cell(mid - lm - 4, 4, safe_text(f"Mat.: {(profesional or {}).get('matricula', 'S/D')}"), ln=True, align="C")

    pdf.set_xy(mid + 4, y_base + 2)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(rm - mid - 4, 4, safe_text("Paciente / familiar"), ln=True, align="C")
    pdf.set_x(mid + 4)
    pdf.set_font("Arial", "", 8)
    pdf.cell(rm - mid - 4, 4, safe_text(nom_pac), ln=True, align="C")
    pdf.set_x(mid + 4)
    pdf.cell(rm - mid - 4, 4, safe_text("Firma y aclaracion"), ln=True, align="C")

    return pdf_output_bytes(pdf)


def build_consent_pdf_bytes(session_state, paciente_sel, mi_empresa, profesional=None):
    consentimientos = [x for x in session_state.get("consentimientos_db", []) if x.get("paciente") == paciente_sel]
    if not consentimientos:
        return None

    consentimiento = consentimientos[-1]
    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    _insert_logo(pdf)
    pdf.set_xy(40, 12)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 8, safe_text(detalles.get("empresa", mi_empresa)), ln=True)
    pdf.set_x(40)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, safe_text("Consentimiento Informado para Atencion y Terapia en Domicilio"), ln=True)
    pdf.ln(10)

    texto = (
        "Por medio del presente, dejo constancia de que he recibido informacion clara, suficiente y comprensible "
        "respecto de la modalidad de atencion y/o terapia en domicilio propuesta para el paciente. "
        "Se me explicaron los objetivos asistenciales, la frecuencia estimada de controles, el alcance de las "
        "prestaciones, los cuidados generales esperables, las pautas de alarma clinica y la necesidad de mantener "
        "condiciones adecuadas de acceso, higiene y seguridad para el desarrollo de la atencion. "
        "\n\n"
        "En consecuencia, en mi caracter de paciente y/o familiar responsable, presto conformidad para recibir "
        "atencion sanitaria, controles, curaciones, seguimiento clinico y/o terapia en el domicilio informado, "
        "autorizando asimismo el registro clinico, administrativo y documental correspondiente dentro del sistema."
        "\n\n"
        "Declaro que los datos aportados son veridicos y que he podido realizar preguntas, recibiendo respuesta "
        "satisfactoria por parte del profesional interviniente."
    )
    pdf.set_font("Arial", "", 11)
    _write_multiline_text(pdf, texto, line_height=7)
    pdf.ln(6)

    _write_pairs(
        pdf,
        [
            ("Paciente", paciente_sel),
            ("DNI paciente", detalles.get("dni", "S/D")),
            ("Domicilio", detalles.get("direccion", "S/D")),
            ("Fecha", consentimiento.get("fecha", "S/D")),
            ("Firmante", consentimiento.get("firmante", paciente_sel)),
            ("DNI firmante", consentimiento.get("dni_firmante", detalles.get("dni", "S/D"))),
            ("Vinculo", consentimiento.get("vinculo", "Paciente")),
            ("Telefono", consentimiento.get("telefono", detalles.get("telefono", "S/D"))),
            ("Observaciones", consentimiento.get("observaciones", "")),
            ("Profesional responsable", (profesional or {}).get("nombre", "S/D")),
            ("Matricula", (profesional or {}).get("matricula", "S/D")),
        ],
    )

    pdf.ln(6)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 6, safe_text("Clausulas de conformidad"), ln=True)
    pdf.set_font("Arial", "", 9)
    clausulas = [
        "1. El firmante acepta la atencion domiciliaria en el domicilio consignado.",
        "2. El firmante se compromete a informar cambios clinicos relevantes y dificultades de acceso.",
        "3. La firma acredita conformidad con la modalidad de prestacion y con el registro documental.",
    ]
    for clausula in clausulas:
        _write_multiline_text(pdf, clausula, line_height=5)

    firma_bytes = None
    if consentimiento.get("firma_b64"):
        firma_bytes = decodificar_base64_seguro(consentimiento["firma_b64"]) or None
    if firma_bytes:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(firma_bytes)
                tmp_path = tmp.name
            pdf.image(tmp_path, x=30, y=210, w=60)
        except Exception:
            pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    y_firma = max(pdf.get_y() + 24, 240)
    if y_firma > 262:
        pdf.add_page()
        y_firma = 230

    pdf.line(25, y_firma, 90, y_firma)
    pdf.set_xy(25, y_firma + 2)
    pdf.set_font("Arial", "", 9)
    pdf.cell(65, 5, safe_text("Firma paciente / familiar"), align="C")

    pdf.line(120, y_firma, 185, y_firma)
    pdf.set_xy(120, y_firma + 2)
    pdf.cell(65, 5, safe_text("Firma y sello profesional"), align="C")

    return pdf_output_bytes(pdf)


def build_prescription_pdf_bytes(session_state, paciente_sel, mi_empresa, record, profesional=None):
    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    estado_actual = record.get("estado_receta") or record.get("estado_clinico") or "Activa"
    medico_indicante = record.get("medico_nombre") or (profesional or {}).get("nombre", "S/D")
    matricula_indicante = record.get("medico_matricula") or (profesional or {}).get("matricula", "S/D")

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    _insert_logo(pdf)

    pdf.set_xy(40, 12)
    pdf.set_font("Arial", "B", 15)
    pdf.cell(0, 8, safe_text(detalles.get("empresa", mi_empresa)), ln=True)
    pdf.set_x(40)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, safe_text("Prescripcion y Acta Legal de Medicacion"), ln=True)
    pdf.set_x(40)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, safe_text("Documento imprimible con trazabilidad clinica y legal"), ln=True)
    pdf.ln(8)

    _section_title(pdf, "Datos del paciente")
    _write_pairs(
        pdf,
        [
            ("Paciente", paciente_sel),
            ("DNI", detalles.get("dni", "S/D")),
            ("Fecha de nacimiento", detalles.get("fnac", "S/D")),
            ("Obra social", detalles.get("obra_social", "S/D")),
            ("Domicilio", detalles.get("direccion", "S/D")),
            ("Telefono", detalles.get("telefono", "S/D")),
            ("Alergias", detalles.get("alergias", "Sin datos")),
        ],
    )

    _section_title(pdf, "Indicacion medica")
    _write_pairs(
        pdf,
        [
            ("Fecha de indicacion", record.get("fecha", "S/D")),
            ("Medicacion / Indicacion", record.get("med", "S/D")),
            ("Estado actual", estado_actual),
            ("Origen del registro", record.get("origen_registro", "Prescripcion digital")),
            ("Medico indicante", medico_indicante),
            ("Matricula profesional", matricula_indicante),
            ("Registrado por", record.get("firmado_por", "S/D")),
        ],
    )
    nota_adjunto = _order_attachment_note(record)
    if nota_adjunto:
        _write_pairs(pdf, [("Adjunto legal", nota_adjunto)])

    if estado_actual != "Activa":
        _section_title(pdf, "Acta de cambio terapeutico")
        _write_pairs(
            pdf,
            [
                ("Tipo de accion", estado_actual),
                ("Fecha y hora del cambio", record.get("fecha_estado") or record.get("fecha_suspension", "S/D")),
                ("Profesional interviniente", record.get("profesional_estado", "S/D")),
                ("Matricula del interviniente", record.get("matricula_estado", "S/D")),
                ("Motivo medico / legal", record.get("motivo_estado", "Sin detalle consignado")),
            ],
        )
        pdf.ln(2)
        pdf.set_font("Arial", "B", 10)
        _write_multiline_text(
            pdf,
            (
                "La presente constancia deja asentado el cambio de estado de la indicacion farmacologica dentro del "
                "registro clinico institucional, con fecha, hora y profesional responsable."
            ),
            line_height=6,
        )

    firma_medica = _doctor_signature_bytes(record)
    if firma_medica:
        _section_title(pdf, "Firma del profesional")
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(firma_medica)
                tmp_path = tmp.name
            y_img = pdf.get_y() + 2
            pdf.image(tmp_path, x=20, y=y_img, w=60)
            pdf.set_xy(90, y_img + 8)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 6, safe_text(medico_indicante), ln=True)
            pdf.set_x(90)
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 6, safe_text(f"Matricula: {matricula_indicante}"), ln=True)
            pdf.set_x(90)
            pdf.cell(0, 6, safe_text(f"Fecha de firma: {record.get('fecha', 'S/D')}"), ln=True)
            pdf.ln(34)
        except Exception:
            pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)
    else:
        _section_title(pdf, "Firma del profesional")
        _write_pairs(
            pdf,
            [
                ("Profesional", medico_indicante),
                ("Matricula", matricula_indicante),
                ("Firma digital", "No disponible en el registro"),
            ],
        )

    pdf.ln(8)
    y_base = max(pdf.get_y() + 12, 240)
    if y_base > 262:
        pdf.add_page()
        y_base = 235

    pdf.line(20, y_base, 90, y_base)
    pdf.set_xy(20, y_base + 2)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(70, 5, safe_text(medico_indicante), ln=True, align="C")
    pdf.set_x(20)
    pdf.set_font("Arial", "", 9)
    pdf.cell(70, 5, safe_text(f"Matricula: {matricula_indicante}"), ln=True, align="C")

    pdf.line(120, y_base, 190, y_base)
    pdf.set_xy(120, y_base + 2)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(70, 5, safe_text("Paciente / Familiar notificado"), ln=True, align="C")
    pdf.set_x(120)
    pdf.set_font("Arial", "", 9)
    pdf.cell(70, 5, safe_text(f"Aclaracion: {paciente_sel.split(' - ')[0]}"), ln=True, align="C")
    pdf.set_x(120)
    pdf.cell(70, 5, safe_text(f"DNI: {detalles.get('dni', 'S/D')}"), ln=True, align="C")

    return pdf_output_bytes(pdf)


def build_emergency_pdf_bytes(session_state, paciente_sel, mi_empresa, record, profesional=None):
    """PDF compacto de emergencia — diseñado para caber en 1 pagina A4."""
    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    firma_b64 = record.get("firma_b64", "")
    firma_bytes = decodificar_base64_seguro(firma_b64) or None if firma_b64 else None
    prof_nombre = record.get("profesional") or (profesional or {}).get("nombre", "")
    prof_mat = record.get("matricula") or (profesional or {}).get("matricula", "")

    _SKIP = {"", None, "S/D", "Sin traslado confirmado", "0", 0}

    def _v(val, fallback=""):
        return str(val).strip() if val not in _SKIP else fallback

    def _row(pdf, label, value, lw=48, lh=5):
        """Label + valor en la misma linea. Omite si valor esta vacio."""
        txt = _v(value)
        if not txt:
            return
        pdf.set_font("Arial", "B", 8)
        pdf.set_x(pdf.l_margin)
        pdf.cell(lw, lh, safe_text(label) + ":", border=0)
        pdf.set_font("Arial", "", 8)
        remaining = pdf.w - pdf.l_margin - pdf.r_margin - lw
        pdf.multi_cell(remaining, lh, safe_text(txt), border=0)

    def _inline_pairs(pdf, pairs, cols=2):
        """Imprime pares label:valor en columnas horizontales."""
        usable = pdf.w - pdf.l_margin - pdf.r_margin
        col_w = usable / cols
        items = [(l, _v(v)) for l, v in pairs if _v(v)]
        for i in range(0, len(items), cols):
            row_items = items[i:i + cols]
            x_start = pdf.l_margin
            for j, (lbl, val) in enumerate(row_items):
                pdf.set_xy(x_start + j * col_w, pdf.get_y())
                pdf.set_font("Arial", "B", 8)
                pdf.cell(28, 5, safe_text(lbl) + ":", border=0)
                pdf.set_font("Arial", "", 8)
                pdf.cell(col_w - 28, 5, safe_text(val[:38]), border=0)
            pdf.ln(5)

    def _sec(pdf, title):
        if pdf.get_y() > 260:
            pdf.add_page()
        pdf.set_fill_color(220, 230, 245)
        pdf.set_text_color(15, 30, 65)
        pdf.set_font("Arial", "B", 9)
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 6, safe_text(title), ln=True, fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(1)

    pdf = FPDF()
    pdf.set_margins(14, 12, 14)
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    _insert_logo(pdf)

    # --- Cabecera compacta ---
    pdf.set_xy(42, 12)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 6, safe_text(detalles.get("empresa", mi_empresa)), ln=True)
    pdf.set_x(42)
    pdf.set_font("Arial", "B", 10)
    pdf.cell(0, 5, "Acta de Emergencia y Traslado", ln=True)
    pdf.set_x(42)
    pdf.set_font("Arial", "", 8)
    pdf.cell(0, 5, safe_text(
        f"Fecha: {record.get('fecha_evento','')} {record.get('hora_evento','')}  |  "
        f"Triage: {_v(record.get('triage_grado',''))}  |  Prioridad: {_v(record.get('prioridad',''))}"
    ), ln=True)
    pdf.ln(3)

    # --- Paciente (1 fila) ---
    _sec(pdf, "Paciente")
    _inline_pairs(pdf, [
        ("Paciente", paciente_sel.split(" - ")[0] if " - " in paciente_sel else paciente_sel),
        ("DNI", detalles.get("dni", "")),
        ("F.Nac", detalles.get("fnac", "")),
        ("Obra Social", detalles.get("obra_social", "")),
        ("Domicilio", record.get("direccion_evento") or detalles.get("direccion", "")),
        ("Telefono", detalles.get("telefono", "")),
    ], cols=2)

    # --- Evento ---
    _sec(pdf, "Evento critico")
    _inline_pairs(pdf, [
        ("Categoria", record.get("categoria_evento", "")),
        ("Tipo", record.get("tipo_evento", "")),
        ("Profesional", prof_nombre),
        ("Matricula", prof_mat),
    ], cols=2)
    motivo_txt = _v(record.get("motivo", ""))
    if motivo_txt:
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", "B", 8)
        pdf.cell(28, 5, "Motivo:", border=0)
        pdf.set_font("Arial", "", 8)
        pdf.multi_cell(pdf.w - pdf.l_margin - pdf.r_margin - 28, 5, safe_text(motivo_txt), border=0)
        pdf.ln(1)

    # --- Signos vitales (1 fila si hay datos) ---
    vitales = [
        ("TA", record.get("presion_arterial", "")),
        ("FC", record.get("fc", "")),
        ("SaO2", record.get("saturacion", "")),
        ("Temp", record.get("temperatura", "")),
        ("Glucemia", record.get("glucemia", "")),
        ("EVA", record.get("dolor", "")),
        ("Conciencia", record.get("conciencia", "")),
    ]
    vitales_con_dato = [(l, v) for l, v in vitales if _v(v)]
    if vitales_con_dato:
        _sec(pdf, "Signos vitales")
        _inline_pairs(pdf, vitales_con_dato, cols=4)

    # --- Ambulancia ---
    amb_data = [
        ("Ambulancia", "Si" if record.get("ambulancia_solicitada") else "No"),
        ("Movil", record.get("movil", "")),
        ("Destino", record.get("destino", "")),
        ("Tipo traslado", record.get("tipo_traslado", "")),
        ("Solicitud", record.get("hora_solicitud", "")),
        ("Arribo", record.get("hora_arribo", "")),
        ("Salida", record.get("hora_salida", "")),
        ("Receptor", record.get("receptor", "")),
        ("Familiar", record.get("familiar_notificado", "")),
    ]
    if any(_v(v) for _, v in amb_data):
        _sec(pdf, "Ambulancia y traslado")
        _inline_pairs(pdf, amb_data, cols=3)

    # --- Parte asistencial (solo si tiene datos) ---
    asist = [
        ("Procedimientos", record.get("procedimientos", "")),
        ("Medicacion", record.get("medicacion_administrada", "")),
        ("Respuesta", record.get("respuesta", "")),
        ("Obs. legales", record.get("observaciones_legales", "")),
    ]
    if any(_v(v) for _, v in asist):
        _sec(pdf, "Parte asistencial")
        for lbl, val in asist:
            _row(pdf, lbl, val)

    # --- Firma ---
    if firma_bytes:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(firma_bytes)
                tmp_path = tmp.name
            if pdf.get_y() > 240:
                pdf.add_page()
            _sec(pdf, "Firma profesional")
            y_img = pdf.get_y()
            pdf.image(tmp_path, x=14, y=y_img, w=50)
            pdf.set_xy(70, y_img + 4)
            pdf.set_font("Arial", "B", 8)
            pdf.cell(0, 5, safe_text(prof_nombre), ln=True)
            pdf.set_x(70)
            pdf.set_font("Arial", "", 8)
            pdf.cell(0, 5, safe_text(f"Mat: {prof_mat}"), ln=True)
            pdf.ln(20)
        except Exception:
            pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    # --- Pie de firma ---
    y_base = max(pdf.get_y() + 8, 250)
    if y_base > 270:
        pdf.add_page()
        y_base = 250
    pdf.line(14, y_base, 80, y_base)
    pdf.set_xy(14, y_base + 1)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(66, 4, safe_text(prof_nombre), align="C", ln=True)
    pdf.set_x(14)
    pdf.set_font("Arial", "", 8)
    pdf.cell(66, 4, safe_text(f"Mat: {prof_mat}"), align="C", ln=True)

    pdf.line(110, y_base, 196, y_base)
    pdf.set_xy(110, y_base + 1)
    pdf.set_font("Arial", "B", 8)
    pdf.cell(86, 4, "Recepcion / conformidad", align="C", ln=True)
    pdf.set_x(110)
    pdf.set_font("Arial", "", 8)
    familiar = _v(record.get("familiar_notificado", "")) or "_______________"
    pdf.cell(86, 4, safe_text(familiar), align="C", ln=True)

    return pdf_output_bytes(pdf)
