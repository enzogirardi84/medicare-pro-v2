"""Clases y helpers base para generación de PDFs clínicos.

Extraído de core/clinical_exports.py.
Contiene: _insert_logo, _pdf_header_oscuro, RespaldoClinicoPDF, helpers de escritura,
tablas de etiquetas y helpers del respaldo clínico.
"""
from pathlib import Path

from fpdf import FPDF

from core.export_utils import safe_text
from core._exports_helpers import collect_patient_sections

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


# ---------------------------------------------------------------------------
# Logo e header
# ---------------------------------------------------------------------------

def insert_logo(pdf_obj, y_offset: float = 8.0):
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


def pdf_header_oscuro(pdf, empresa, titulo, subtitulo="", badge_txt="", badge_rgb=(60, 80, 120)):
    header_h = 36
    pdf.set_fill_color(22, 38, 68)
    pdf.rect(0, 0, pdf.w, header_h, "F")
    pdf.set_fill_color(*badge_rgb)
    pdf.rect(0, 0, 5, header_h, "F")
    for ruta in [ASSETS_DIR / "logo_medicare_pro.jpeg", ASSETS_DIR / "logo_medicare_pro.jpg", ASSETS_DIR / "logo_medicare_pro.png"]:
        if ruta.exists():
            try:
                pdf.image(str(ruta), x=8, y=5, w=26)
            except Exception:
                pass
            break
    pdf.set_xy(38, 7)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, safe_text(empresa), ln=True)
    pdf.set_x(38)
    pdf.set_font("Arial", "B", 8)
    pdf.set_text_color(160, 200, 255)
    pdf.cell(0, 5, safe_text(titulo), ln=True)
    if subtitulo:
        pdf.set_x(38)
        pdf.set_font("Arial", "", 7)
        pdf.set_text_color(200, 210, 230)
        pdf.cell(0, 5, safe_text(subtitulo), ln=True)
    if badge_txt:
        badge_w = 52
        badge_x = pdf.w - badge_w - 6
        pdf.set_fill_color(*badge_rgb)
        pdf.rect(badge_x, 10, badge_w, 16, "F")
        pdf.set_font("Arial", "B", 9)
        pdf.set_text_color(255, 255, 255)
        pdf.set_xy(badge_x, 15)
        pdf.cell(badge_w, 6, safe_text(badge_txt), align="C", border=0)
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(pdf.l_margin, header_h + 4)
    return header_h + 4


# ---------------------------------------------------------------------------
# Clase base PDF con footer
# ---------------------------------------------------------------------------

class RespaldoClinicoPDF(FPDF):
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


# ---------------------------------------------------------------------------
# Helpers de escritura PDF
# ---------------------------------------------------------------------------

def section_title(pdf, title):
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.set_x(pdf.l_margin)
    pdf.set_fill_color(230, 238, 250)
    pdf.set_text_color(21, 37, 69)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(0, 8, safe_text(title), ln=True, fill=True)
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)


def usable_width(pdf):
    return max(20, getattr(pdf, "epw", pdf.w - pdf.l_margin - pdf.r_margin))


def write_multiline_text(pdf, text, line_height=6, indent=0):
    content = safe_text(text).strip()
    if not content:
        return
    width = max(20, usable_width(pdf) - indent)
    x_base = pdf.l_margin + indent
    for paragraph in content.split("\n"):
        paragraph = paragraph.strip()
        if not paragraph:
            pdf.ln(line_height)
            continue
        pdf.set_x(x_base)
        pdf.multi_cell(width, line_height, paragraph, border=0)


def write_pairs(pdf, pairs):
    for label, value in pairs:
        if value in [None, ""]:
            continue
        label_txt = safe_text(label).strip()
        value_txt = safe_text(value).strip()
        if not value_txt:
            continue
        pdf.set_x(pdf.l_margin)
        pdf.set_font("Arial", "B", 9)
        pdf.cell(0, 5, safe_text(f"{label_txt}:"), ln=True)
        pdf.set_font("Arial", "", 9)
        write_multiline_text(pdf, value_txt, line_height=6, indent=4)
        pdf.ln(1)


# ---------------------------------------------------------------------------
# Tablas de etiquetas y helpers del respaldo clínico (backup)
# ---------------------------------------------------------------------------

_BACKUP_SKIP_KEYS = frozenset({
    "paciente", "empresa", "imagen", "base64_foto", "firma_b64",
    "firma_img", "adjunto_papel_b64", "adjunto_papel_tipo", "contenido",
})
_BACKUP_MAX_VALUE_LEN = 480

_BACKUP_FIELD_LABELS = {
    "fecha": "Fecha", "F": "Fecha", "H": "Hora",
    "fecha_evento": "Fecha del evento", "hora_evento": "Hora del evento",
    "tipo_evento": "Tipo de evento", "categoria_evento": "Categoría",
    "triage_grado": "Triage", "prioridad": "Prioridad", "motivo": "Motivo",
    "profesional": "Profesional", "firma": "Profesional / firma",
    "matricula": "Matrícula", "medico_nombre": "Médico",
    "medico_matricula": "Matrícula médico", "med": "Medicación / indicación",
    "estado_receta": "Estado receta", "estado_clinico": "Estado clínico",
    "observaciones": "Observaciones", "nota": "Nota",
    "tipo_cuidado": "Tipo de cuidado", "intervencion": "Intervención",
    "turno": "Turno", "escala": "Escala", "puntaje": "Puntaje",
    "interpretacion": "Interpretación", "detalle": "Detalle",
    "insumo": "Insumo / material", "cantidad": "Cantidad",
    "TA": "Tensión arterial", "FC": "Frecuencia cardíaca",
    "FR": "Frecuencia respiratoria", "Sat": "Saturación O2",
    "Temp": "Temperatura", "HGT": "Glucemia",
    "ingresos": "Ingresos", "egresos": "Egresos", "balance": "Balance",
    "fecha_registro": "Fecha registro", "accion": "Acción",
    "detalle_aud": "Detalle", "firmante": "Firmante", "vinculo": "Vínculo",
    "dni_firmante": "DNI firmante", "telefono": "Teléfono",
    "obra_social": "Obra social", "direccion": "Domicilio",
    "direccion_evento": "Domicilio del evento",
}

_BACKUP_PRIORITY_KEYS = [
    "fecha", "F", "H", "fecha_evento", "hora_evento", "categoria_evento",
    "tipo_evento", "triage_grado", "prioridad", "profesional", "firma",
    "medico_nombre", "matricula", "med", "estado_receta", "estado_clinico",
    "tipo_cuidado", "turno", "escala", "puntaje", "motivo", "observaciones",
    "nota", "detalle", "tipo", "insumo", "cantidad",
    "TA", "FC", "FR", "Sat", "Temp", "HGT", "ingresos", "egresos", "balance", "accion",
]


def backup_label_key(key: str) -> str:
    if key in _BACKUP_FIELD_LABELS:
        return _BACKUP_FIELD_LABELS[key]
    return str(key).replace("_", " ").strip().title()


def backup_sort_key_record(rec: dict) -> str:
    for k in ("fecha", "fecha_evento", "F", "fecha_registro", "fecha_suspension", "hora_evento"):
        v = rec.get(k)
        if v not in (None, ""):
            return str(v)
    return ""


def backup_sorted_records(records: list) -> list:
    if not records:
        return []
    return sorted(records, key=backup_sort_key_record)


def backup_latest_record(records: list):
    s = backup_sorted_records(records)
    return s[-1] if s else None


def backup_trim_value(val) -> str:
    t = safe_text(val).strip()
    if len(t) > _BACKUP_MAX_VALUE_LEN:
        return t[:_BACKUP_MAX_VALUE_LEN - 3] + "..."
    return t


def backup_rows_from_record(record: dict) -> list:
    if not record:
        return []
    rows = []
    seen: set = set()
    for pk in _BACKUP_PRIORITY_KEYS:
        if pk in record and pk not in _BACKUP_SKIP_KEYS:
            val = record.get(pk)
            if val not in (None, ""):
                rows.append((backup_label_key(pk), backup_trim_value(val)))
                seen.add(pk)
    for k, v in sorted(record.items()):
        if k in seen or k in _BACKUP_SKIP_KEYS or v in (None, ""):
            continue
        rows.append((backup_label_key(k), backup_trim_value(v)))
    return rows[:18]


def section_title_backup(pdf: FPDF, title: str) -> None:
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


def backup_split_paciente_sel(paciente_sel: str) -> tuple:
    s = (paciente_sel or "").strip()
    if " - " in s:
        a, b = s.split(" - ", 1)
        return a.strip(), b.strip()
    return s, ""


def backup_draw_module_index(pdf: FPDF, session_state, paciente_sel: str) -> None:
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
        pdf.set_fill_color(248, 250, 252) if i % 2 == 0 else pdf.set_fill_color(255, 255, 255)
        pdf.set_x(pdf.l_margin)
        pdf.cell(w_mod, 5, safe_text(name)[:64], border=1, fill=True, ln=0)
        pdf.set_font("Arial", "B" if n else "", 8)
        pdf.cell(w_cnt, 5, safe_text(str(n)), border=1, fill=True, ln=True, align="R")
        pdf.set_font("Arial", "", 8)
    pdf.ln(4)
