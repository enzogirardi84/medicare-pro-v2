"""Exportación a Excel y JSON del historial del paciente.

Extraído de core/clinical_exports.py.
"""
import io
import json

import pandas as pd

from core.utils import mapa_detalles_pacientes
from core._exports_helpers import collect_patient_sections


def build_patient_excel_bytes(session_state, paciente_sel):
    from datetime import datetime as _dt

    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    nom_pac = paciente_sel.split(" - ")[0] if " - " in paciente_sel else paciente_sel

    output = io.BytesIO()
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        engine = "openpyxl"
    except Exception as e_openpyxl:
        try:
            import xlsxwriter  # noqa: F401
            engine = "xlsxwriter"
        except Exception as e_xlsx:
            # MEJORA: Registro explícito del fallo de las librerías
            from core.app_logging import log_event
            log_event("export_error", f"Fallo motores Excel. openpyxl: {e_openpyxl} | xlsxwriter: {e_xlsx}")
            return None

    sheets = {}
    for section_name, records in collect_patient_sections(session_state, paciente_sel).items():
        if not records:
            continue
        df = pd.DataFrame(records).drop(columns=["paciente", "empresa", "firma_b64"], errors="ignore")
        sheets[section_name[:31]] = df

    if not sheets:
        sheets["Sin registros"] = pd.DataFrame([{"mensaje": "No hay registros clinicos para este paciente."}])

    with pd.ExcelWriter(output, engine=engine) as writer:
        resumen_rows = [{"Seccion": sec, "Registros": len(df)} for sec, df in sheets.items()]
        pd.DataFrame(resumen_rows).to_excel(writer, index=False, sheet_name="Resumen")
        for sheet_name, df in sheets.items():
            df.to_excel(writer, index=False, sheet_name=sheet_name)

        if engine == "openpyxl":
            wb = writer.book
            _navy = "162644"
            _green = "0D5A50"
            _hdr_font = Font(bold=True, color="FFFFFF", size=10)
            _hdr_fill_navy = PatternFill("solid", fgColor=_navy)
            _hdr_fill_green = PatternFill("solid", fgColor=_green)
            _thin = Side(style="thin", color="D1D5DB")
            _border = Border(left=_thin, right=_thin, top=_thin, bottom=_thin)

            for ws in wb.worksheets:
                fill = _hdr_fill_green if ws.title == "Resumen" else _hdr_fill_navy
                for cell in ws[1]:
                    cell.font = _hdr_font
                    cell.fill = fill
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    cell.border = _border
                ws.row_dimensions[1].height = 22
                for col in ws.columns:
                    max_len = max((len(str(c.value)) if c.value is not None else 0) for c in col)
                    ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 3, 10), 50)
                alt_fill = PatternFill("solid", fgColor="F3F4F6")
                for i, row in enumerate(ws.iter_rows(min_row=2), start=2):
                    row_fill = alt_fill if i % 2 == 0 else None
                    for cell in row:
                        cell.border = _border
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
                        if row_fill:
                            cell.fill = row_fill
                ws.freeze_panes = "A2"

            ws_res = wb["Resumen"]
            ws_res.insert_rows(1, amount=4)
            ws_res["A1"] = detalles.get("empresa", "")
            ws_res["A1"].font = Font(bold=True, size=14, color=_navy)
            ws_res["A2"] = "HISTORIA CLINICA DIGITAL - EXPORTACION COMPLETA"
            ws_res["A2"].font = Font(bold=True, size=11, color=_navy)
            ws_res["A3"] = f"Paciente: {nom_pac}   |   DNI: {detalles.get('dni', 'S/D')}   |   Generado: {_dt.now().strftime('%d/%m/%Y %H:%M')}"
            ws_res["A3"].font = Font(size=9, color="64748B")
            ws_res["A4"] = ""

    output.seek(0)
    return output.getvalue()


def build_patient_json_bytes(session_state, paciente_sel):
    payload = {
        "paciente": paciente_sel,
        "detalles": mapa_detalles_pacientes(session_state).get(paciente_sel, {}),
        "secciones": collect_patient_sections(session_state, paciente_sel),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")
