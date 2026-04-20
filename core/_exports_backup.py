"""Generación del PDF de Respaldo Clínico del paciente (FPDF).

Extraído de core/clinical_exports.py.
"""
from core.export_utils import pdf_output_bytes, safe_text
from core.utils import mapa_detalles_pacientes
from core._exports_helpers import collect_patient_sections, order_attachment_note
from core._exports_pdf_base import (
    RespaldoClinicoPDF,
    backup_draw_module_index,
    backup_latest_record,
    backup_rows_from_record,
    backup_split_paciente_sel,
    pdf_header_oscuro,
    section_title_backup,
    write_multiline_text,
    write_pairs,
)


def build_backup_pdf_bytes(session_state, paciente_sel, mi_empresa, profesional=None):
    from datetime import datetime

    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    empresa = detalles.get("empresa", mi_empresa)
    generado = datetime.now().strftime("%d/%m/%Y %H:%M")
    nom_pac, dni_del_id = backup_split_paciente_sel(paciente_sel)
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

    pdf_header_oscuro(
        pdf, empresa,
        "RESPALDO CLINICO DEL PACIENTE",
        subtitulo=safe_text(f"{nom_pac}  ·  DNI: {dni_final}  ·  Generado: {generado}"),
        badge_txt="Historia Clinica",
        badge_rgb=(13, 90, 80),
    )

    section_title_backup(pdf, "1. Datos demograficos y alertas")
    write_pairs(pdf, [
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
    ])

    section_title_backup(pdf, "2. Indice de actividad por modulo")
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(71, 85, 105)
    write_multiline_text(
        pdf,
        "Vista rapida del volumen de informacion cargada. Los modulos sin registros no se repiten en el detalle (seccion 3).",
        line_height=4,
    )
    pdf.set_text_color(0, 0, 0)
    pdf.ln(1)
    backup_draw_module_index(pdf, session_state, paciente_sel)

    section_title_backup(pdf, "3. Detalle por modulo (ultimo registro por fecha)")
    pdf.set_font("Arial", "", 8)
    pdf.set_text_color(71, 85, 105)
    write_multiline_text(
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

        ultimo = backup_latest_record(records)
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

        filas = backup_rows_from_record(ultimo)
        pdf.set_font("Arial", "", 9)
        write_pairs(pdf, filas)

        nota_adjunto = order_attachment_note(ultimo)
        if nota_adjunto:
            pdf.set_font("Arial", "I", 8)
            write_pairs(pdf, [("Adjunto en sistema", nota_adjunto)])

        pdf.ln(2)
        pdf.set_draw_color(226, 232, 240)
        y_sep = pdf.get_y()
        pdf.line(pdf.l_margin, y_sep, pdf.w - pdf.r_margin, y_sep)
        pdf.ln(5)

    pdf.ln(3)
    pdf.set_font("Arial", "I", 8)
    pdf.set_text_color(71, 85, 105)
    write_multiline_text(
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
