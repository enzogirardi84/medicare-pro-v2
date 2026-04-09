import base64
import io
import json
import os
import tempfile
from pathlib import Path

import pandas as pd
from fpdf import FPDF

from core.export_utils import pdf_output_bytes, safe_text


ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


def _patient_signature_bytes(session_state, paciente_sel):
    consentimientos = [x for x in session_state.get("consentimientos_db", []) if x.get("paciente") == paciente_sel]
    for registro in reversed(consentimientos):
        if registro.get("firma_b64"):
            try:
                return base64.b64decode(registro["firma_b64"])
            except Exception:
                pass

    firmas = [x for x in session_state.get("firmas_tactiles_db", []) if x.get("paciente") == paciente_sel]
    for registro in reversed(firmas):
        if registro.get("firma_img"):
            try:
                return base64.b64decode(registro["firma_img"])
            except Exception:
                pass
    return None


def _doctor_signature_bytes(record):
    firma_b64 = record.get("firma_b64", "")
    if not firma_b64:
        return None
    try:
        return base64.b64decode(firma_b64)
    except Exception:
        return None


def _order_attachment_note(record):
    nombre = record.get("adjunto_papel_nombre", "").strip()
    if not nombre:
        return ""
    return f"Orden medica adjunta en sistema: {nombre}"


def collect_patient_sections(session_state, paciente_sel):
    return {
        "Auditoria de Presencia": [x for x in session_state.get("checkin_db", []) if x.get("paciente") == paciente_sel],
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
    detalles = session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
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
        "detalles": session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {}),
        "secciones": collect_patient_sections(session_state, paciente_sel),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def _insert_logo(pdf_obj):
    posibles = [
        ASSETS_DIR / "logo_medicare_pro.jpeg",
        ASSETS_DIR / "logo_medicare_pro.jpg",
        ASSETS_DIR / "logo_medicare_pro.png",
    ]
    for ruta in posibles:
        if ruta.exists():
            try:
                pdf_obj.image(str(ruta), x=10, y=10, w=24)
                return
            except Exception:
                pass


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
        x_inicio = pdf.get_x()
        y_inicio = pdf.get_y()
        label_w = 46
        value_w = max(30, _usable_width(pdf) - label_w - 2)
        pdf.set_font("Arial", "B", 9)
        pdf.multi_cell(label_w, 6, f"{label_txt}:", border=0)
        y_fin_label = pdf.get_y()
        pdf.set_xy(x_inicio + label_w + 2, y_inicio)
        pdf.set_font("Arial", "", 9)
        pdf.multi_cell(value_w, 6, value_txt, border=0)
        pdf.set_y(max(pdf.get_y(), y_fin_label))
        pdf.ln(1)


def build_history_pdf_bytes(session_state, paciente_sel, mi_empresa, profesional=None):
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    _insert_logo(pdf)

    detalles = session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    nombre_prof = (profesional or {}).get("nombre", "")
    matricula_prof = (profesional or {}).get("matricula", "")
    dni_prof = (profesional or {}).get("dni", "")

    pdf.set_xy(40, 12)
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 8, safe_text(detalles.get("empresa", mi_empresa)), ln=True)
    pdf.set_x(40)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, safe_text("Historia Clinica Digital Integral"), ln=True)
    pdf.ln(8)

    _section_title(pdf, f"Paciente: {paciente_sel}")
    _write_pairs(
        pdf,
        [
            ("DNI", detalles.get("dni", "S/D")),
            ("Fecha de nacimiento", detalles.get("fnac", "S/D")),
            ("Sexo", detalles.get("sexo", "S/D")),
            ("Telefono", detalles.get("telefono", "S/D")),
            ("Obra social", detalles.get("obra_social", "S/D")),
            ("Domicilio", detalles.get("direccion", "S/D")),
            ("Estado", detalles.get("estado", "Activo")),
            ("Alergias", detalles.get("alergias", "Sin datos")),
            ("Patologias / Riesgos", detalles.get("patologias", "Sin datos")),
        ],
    )
    pdf.ln(2)

    for section_name, records in collect_patient_sections(session_state, paciente_sel).items():
        if not records:
            continue
        _section_title(pdf, section_name)
        for idx, record in enumerate(records, start=1):
            if pdf.get_y() > 260:
                pdf.add_page()
            pdf.set_font("Arial", "B", 9)
            pdf.cell(0, 6, safe_text(f"Registro {idx}"), ln=True)
            pdf.set_font("Arial", "", 8)
            for key, value in record.items():
                if key in {
                    "paciente",
                    "imagen",
                    "base64_foto",
                    "firma_b64",
                    "firma_img",
                    "adjunto_papel_b64",
                    "adjunto_papel_tipo",
                }:
                    continue
                if value in [None, ""]:
                    continue
                _write_pairs(pdf, [(key, value)])
            nota_adjunto = _order_attachment_note(record)
            if nota_adjunto:
                _write_pairs(pdf, [("Adjunto legal", nota_adjunto)])
            firma_medica = _doctor_signature_bytes(record)
            if firma_medica:
                tmp_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                        tmp.write(firma_medica)
                        tmp_path = tmp.name
                    pdf.image(tmp_path, x=150, y=max(pdf.get_y() - 18, 20), w=35)
                    pdf.ln(18)
                except Exception:
                    pass
                finally:
                    if tmp_path and os.path.exists(tmp_path):
                        os.remove(tmp_path)
            pdf.ln(1)

    consentimientos = [x for x in session_state.get("consentimientos_db", []) if x.get("paciente") == paciente_sel]
    if consentimientos:
        ultimo = consentimientos[-1]
        _section_title(pdf, "Consentimiento de Atencion Domiciliaria")
        _write_pairs(
            pdf,
            [
                ("Fecha", ultimo.get("fecha", "S/D")),
                ("Firmante", ultimo.get("firmante", paciente_sel)),
                ("DNI firmante", ultimo.get("dni_firmante", detalles.get("dni", "S/D"))),
                ("Vinculo", ultimo.get("vinculo", "Paciente")),
                ("Aceptacion", "Acepta recibir terapia en domicilio"),
                ("Observaciones", ultimo.get("observaciones", "")),
            ],
        )

    y_base = max(pdf.get_y() + 14, 235)
    if y_base > 260:
        pdf.add_page()
        y_base = 235

    pdf.line(15, y_base, 85, y_base)
    pdf.set_xy(15, y_base + 2)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(70, 5, safe_text(f"Profesional: {nombre_prof or 'S/D'}"), ln=True)
    pdf.set_x(15)
    pdf.set_font("Arial", "", 9)
    pdf.cell(70, 5, safe_text(f"Matricula: {matricula_prof or 'S/D'} | DNI: {dni_prof or 'S/D'}"), ln=True)

    pdf.line(120, y_base, 190, y_base)
    pdf.set_xy(120, y_base + 2)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(70, 5, safe_text("Paciente / Familiar"), ln=True)
    pdf.set_x(120)
    pdf.set_font("Arial", "", 9)
    pdf.cell(70, 5, safe_text(f"Aclaracion: {paciente_sel.split(' - ')[0]}"), ln=True)
    pdf.set_x(120)
    pdf.cell(70, 5, safe_text(f"DNI: {detalles.get('dni', 'S/D')}"), ln=True)

    firma_bytes = _patient_signature_bytes(session_state, paciente_sel)
    if firma_bytes:
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(firma_bytes)
                tmp_path = tmp.name
            pdf.image(tmp_path, x=125, y=y_base - 20, w=50)
        except Exception:
            pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    return pdf_output_bytes(pdf)


def build_backup_pdf_bytes(session_state, paciente_sel, mi_empresa, profesional=None):
    detalles = session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    _insert_logo(pdf)

    pdf.set_xy(40, 12)
    pdf.set_font("Arial", "B", 15)
    pdf.cell(0, 8, safe_text(detalles.get("empresa", mi_empresa)), ln=True)
    pdf.set_x(40)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, safe_text("Respaldo Clinico Imprimible del Paciente"), ln=True)
    pdf.ln(10)

    _section_title(pdf, "Identificacion del paciente")
    _write_pairs(
        pdf,
        [
            ("Paciente", paciente_sel),
            ("DNI", detalles.get("dni", "S/D")),
            ("Fecha de nacimiento", detalles.get("fnac", "S/D")),
            ("Domicilio", detalles.get("direccion", "S/D")),
            ("Obra social", detalles.get("obra_social", "S/D")),
            ("Telefono", detalles.get("telefono", "S/D")),
            ("Alergias", detalles.get("alergias", "Sin datos")),
            ("Patologias / Riesgos", detalles.get("patologias", "Sin datos")),
        ],
    )

    _section_title(pdf, "Resumen de registros")
    for section_name, records in collect_patient_sections(session_state, paciente_sel).items():
        pdf.set_font("Arial", "B", 10)
        pdf.cell(0, 7, safe_text(f"{section_name}: {len(records)} registro(s)"), ln=True)
        if records:
            ultimo = records[-1]
            pdf.set_font("Arial", "", 9)
            for key, value in ultimo.items():
                if key in {
                    "paciente",
                    "imagen",
                    "base64_foto",
                    "firma_b64",
                    "firma_img",
                    "adjunto_papel_b64",
                    "adjunto_papel_tipo",
                } or value in [None, ""]:
                    continue
                _write_pairs(pdf, [(key, value)])
            nota_adjunto = _order_attachment_note(ultimo)
            if nota_adjunto:
                _write_pairs(pdf, [("Adjunto legal", nota_adjunto)])
            pdf.ln(1)

    pdf.ln(8)
    pdf.set_font("Arial", "B", 10)
    _write_multiline_text(
        pdf,
        (
            "Este respaldo resume la informacion clinica y administrativa registrada en el sistema para su archivo, "
            "impresion y presentacion institucional cuando resulte necesario."
        ),
        line_height=6,
    )

    y_base = max(pdf.get_y() + 16, 240)
    if y_base > 262:
        pdf.add_page()
        y_base = 240

    pdf.line(15, y_base, 85, y_base)
    pdf.set_xy(15, y_base + 2)
    pdf.set_font("Arial", "", 9)
    pdf.cell(70, 5, safe_text(f"Profesional: {(profesional or {}).get('nombre', 'S/D')}"), ln=True)
    pdf.set_x(15)
    pdf.cell(70, 5, safe_text(f"Matricula: {(profesional or {}).get('matricula', 'S/D')}"), ln=True)

    pdf.line(120, y_base, 190, y_base)
    pdf.set_xy(120, y_base + 2)
    pdf.cell(70, 5, safe_text("Paciente / Familiar"), ln=True)
    pdf.set_x(120)
    pdf.cell(70, 5, safe_text(f"Aclaracion: {paciente_sel.split(' - ')[0]}"), ln=True)

    return pdf_output_bytes(pdf)


def build_consent_pdf_bytes(session_state, paciente_sel, mi_empresa, profesional=None):
    consentimientos = [x for x in session_state.get("consentimientos_db", []) if x.get("paciente") == paciente_sel]
    if not consentimientos:
        return None

    consentimiento = consentimientos[-1]
    detalles = session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})

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
        try:
            firma_bytes = base64.b64decode(consentimiento["firma_b64"])
        except Exception:
            firma_bytes = None
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
    detalles = session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
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
    detalles = session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    firma_b64 = record.get("firma_b64", "")
    firma_bytes = None
    if firma_b64:
        try:
            firma_bytes = base64.b64decode(firma_b64)
        except Exception:
            firma_bytes = None

    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    _insert_logo(pdf)

    pdf.set_xy(40, 12)
    pdf.set_font("Arial", "B", 15)
    pdf.cell(0, 8, safe_text(detalles.get("empresa", mi_empresa)), ln=True)
    pdf.set_x(40)
    pdf.set_font("Arial", "B", 12)
    pdf.cell(0, 7, safe_text("Acta de Emergencia, Ambulancia y Traslado"), ln=True)
    pdf.set_x(40)
    pdf.set_font("Arial", "", 10)
    pdf.cell(0, 6, safe_text("Registro prehospitalario, clinico y legal"), ln=True)
    pdf.ln(8)

    _section_title(pdf, "Paciente")
    _write_pairs(
        pdf,
        [
            ("Paciente", paciente_sel),
            ("DNI", detalles.get("dni", "S/D")),
            ("Fecha de nacimiento", detalles.get("fnac", "S/D")),
            ("Obra social", detalles.get("obra_social", "S/D")),
            ("Domicilio", record.get("direccion_evento") or detalles.get("direccion", "S/D")),
            ("Telefono", detalles.get("telefono", "S/D")),
        ],
    )

    _section_title(pdf, "Evento critico")
    _write_pairs(
        pdf,
        [
            ("Fecha del evento", record.get("fecha_evento", "S/D")),
            ("Hora del evento", record.get("hora_evento", "S/D")),
            ("Categoria", record.get("categoria_evento", "S/D")),
            ("Tipo de evento", record.get("tipo_evento", "S/D")),
            ("Clasificacion de triage", record.get("triage_grado", "S/D")),
            ("Prioridad", record.get("prioridad", "S/D")),
            ("Codigo / alerta", record.get("codigo_alerta", "S/D")),
            ("Motivo principal", record.get("motivo", "S/D")),
            ("Profesional a cargo", record.get("profesional", (profesional or {}).get("nombre", "S/D"))),
            ("Matricula", record.get("matricula", (profesional or {}).get("matricula", "S/D"))),
        ],
    )

    _section_title(pdf, "Triage inicial")
    _write_pairs(
        pdf,
        [
            ("Presion arterial", record.get("presion_arterial", "")),
            ("Frecuencia cardiaca", record.get("fc", "")),
            ("Saturacion O2", record.get("saturacion", "")),
            ("Temperatura", record.get("temperatura", "")),
            ("Glucemia", record.get("glucemia", "")),
            ("Dolor EVA", record.get("dolor", "")),
            ("Conciencia", record.get("conciencia", "")),
            ("Observaciones", record.get("observaciones", "")),
        ],
    )

    _section_title(pdf, "Ambulancia y traslado")
    _write_pairs(
        pdf,
        [
            ("Ambulancia solicitada", "Si" if record.get("ambulancia_solicitada") else "No"),
            ("Tipo de traslado", record.get("tipo_traslado", "")),
            ("Movil / empresa", record.get("movil", "")),
            ("Hora de solicitud", record.get("hora_solicitud", "")),
            ("Hora de arribo", record.get("hora_arribo", "")),
            ("Hora de salida", record.get("hora_salida", "")),
            ("Destino", record.get("destino", "")),
            ("Profesional receptor", record.get("receptor", "")),
            ("Familiar notificado", record.get("familiar_notificado", "")),
        ],
    )

    _section_title(pdf, "Parte asistencial")
    _write_pairs(
        pdf,
        [
            ("Procedimientos realizados", record.get("procedimientos", "")),
            ("Medicacion administrada", record.get("medicacion_administrada", "")),
            ("Respuesta del paciente", record.get("respuesta", "")),
            ("Observaciones legales", record.get("observaciones_legales", "")),
        ],
    )

    if firma_bytes:
        _section_title(pdf, "Firma profesional")
        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                tmp.write(firma_bytes)
                tmp_path = tmp.name
            y_img = pdf.get_y() + 2
            pdf.image(tmp_path, x=20, y=y_img, w=60)
            pdf.set_xy(90, y_img + 8)
            pdf.set_font("Arial", "B", 10)
            pdf.cell(0, 6, safe_text(record.get("profesional", (profesional or {}).get("nombre", "S/D"))), ln=True)
            pdf.set_x(90)
            pdf.set_font("Arial", "", 10)
            pdf.cell(0, 6, safe_text(f"Matricula: {record.get('matricula', (profesional or {}).get('matricula', 'S/D'))}"), ln=True)
            pdf.ln(34)
        except Exception:
            pass
        finally:
            if tmp_path and os.path.exists(tmp_path):
                os.remove(tmp_path)

    y_base = max(pdf.get_y() + 12, 240)
    if y_base > 262:
        pdf.add_page()
        y_base = 235

    pdf.line(20, y_base, 90, y_base)
    pdf.set_xy(20, y_base + 2)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(70, 5, safe_text(record.get("profesional", (profesional or {}).get("nombre", "S/D"))), ln=True, align="C")
    pdf.set_x(20)
    pdf.set_font("Arial", "", 9)
    pdf.cell(70, 5, safe_text(f"Matricula: {record.get('matricula', (profesional or {}).get('matricula', 'S/D'))}"), ln=True, align="C")

    pdf.line(120, y_base, 190, y_base)
    pdf.set_xy(120, y_base + 2)
    pdf.set_font("Arial", "B", 9)
    pdf.cell(70, 5, safe_text("Recepcion / conformidad"), ln=True, align="C")
    pdf.set_x(120)
    pdf.set_font("Arial", "", 9)
    pdf.cell(70, 5, safe_text(f"Familiar notificado: {record.get('familiar_notificado', 'S/D')}"), ln=True, align="C")

    return pdf_output_bytes(pdf)
