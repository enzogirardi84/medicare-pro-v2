import base64
import io
import json
import os
import tempfile
import time
from pathlib import Path

import pandas as pd
from fpdf import FPDF

# --- Nuevas importaciones para la Historia Clínica Avanzada ---
REPORTLAB_DISPONIBLE = True
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.platypus import KeepTogether, Image as RLImage, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
except ImportError:
    REPORTLAB_DISPONIBLE = False
    colors = None
    A4 = None
    ParagraphStyle = None
    getSampleStyleSheet = None
    KeepTogether = None
    RLImage = None
    Paragraph = None
    SimpleDocTemplate = None
    Spacer = None
    Table = None
    TableStyle = None

from core.export_utils import pdf_output_bytes, safe_text
from core.utils import decodificar_base64_seguro, mapa_detalles_pacientes

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
_HISTORIAL_SQL_TTL_SECONDS = 20


def _patient_signature_bytes(session_state, paciente_sel):
    consentimientos = collect_patient_sections(session_state, paciente_sel).get("Consentimientos", [])
    for registro in reversed(consentimientos):
        if registro.get("firma_b64"):
            firma_bytes = decodificar_base64_seguro(registro["firma_b64"])
            if firma_bytes:
                return firma_bytes

    ctx = _patient_context(session_state, paciente_sel)
    firmas = [
        x
        for x in session_state.get("firmas_tactiles_db", [])
        if isinstance(x, dict) and _record_matches_patient(x, paciente_sel, ctx)
    ]
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


def _split_patient_visual_id(paciente_sel):
    texto = str(paciente_sel or "").strip()
    if " - " not in texto:
        return texto, ""
    nombre, dni = texto.rsplit(" - ", 1)
    return nombre.strip(), dni.strip()


def _normalize_patient_name(nombre):
    return " ".join(str(nombre or "").strip().lower().split())


def _format_sql_datetime(valor, *, default=""):
    if valor in (None, ""):
        return default
    try:
        dt = pd.to_datetime(valor, errors="coerce")
    except Exception:
        dt = None
    if dt is None or pd.isna(dt):
        return str(valor).replace("T", " ").strip()
    if isinstance(valor, str) and len(valor.strip()) <= 10 and dt.hour == 0 and dt.minute == 0:
        return dt.strftime("%d/%m/%Y")
    return dt.strftime("%d/%m/%Y %H:%M")


def _patient_context(session_state, paciente_sel):
    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    nombre_visual, dni_visual = _split_patient_visual_id(paciente_sel)
    nombre = str(detalles.get("nombre") or nombre_visual).strip()
    dni = str(detalles.get("dni") or dni_visual).strip()
    empresa = str(
        detalles.get("empresa")
        or session_state.get("u_actual", {}).get("empresa")
        or session_state.get("user", {}).get("empresa")
        or ""
    ).strip()
    empresa_id = None
    paciente_uuid = None
    if dni and empresa:
        try:
            from core.nextgen_sync import _obtener_uuid_empresa, _obtener_uuid_paciente

            empresa_id = _obtener_uuid_empresa(empresa)
            paciente_uuid = _obtener_uuid_paciente(dni, empresa_id) if empresa_id else None
        except Exception:
            empresa_id = None
            paciente_uuid = None
    return {
        "nombre": nombre,
        "dni": dni,
        "empresa": empresa,
        "empresa_id": empresa_id,
        "paciente_uuid": paciente_uuid,
        "detalles": detalles,
    }


def _record_matches_patient(record, paciente_sel, ctx):
    if not isinstance(record, dict):
        return False

    candidatos = []
    for clave in ("paciente", "paciente_id", "dni"):
        valor = record.get(clave)
        if valor not in (None, ""):
            candidatos.append(str(valor).strip())

    if paciente_sel and any(valor == paciente_sel for valor in candidatos):
        return True

    dni_ref = str(ctx.get("dni") or "").strip()
    if dni_ref:
        for valor in candidatos:
            _, dni_valor = _split_patient_visual_id(valor)
            if dni_valor and dni_valor == dni_ref:
                return True
            if valor == dni_ref:
                return True

    nombre_ref = _normalize_patient_name(ctx.get("nombre"))
    if not nombre_ref:
        return False

    for valor in candidatos:
        nombre_valor, dni_valor = _split_patient_visual_id(valor)
        if dni_ref and dni_valor and dni_valor != dni_ref:
            continue
        if _normalize_patient_name(nombre_valor) == nombre_ref:
            return True
    return False


def _local_section_records(session_state, session_key, paciente_sel, ctx):
    return [
        dict(registro)
        for registro in session_state.get(session_key, [])
        if isinstance(registro, dict) and _record_matches_patient(registro, paciente_sel, ctx)
    ]


def _record_fingerprint(record):
    importantes = []
    for clave in (
        "id",
        "id_sql",
        "_id_local",
        "fecha",
        "fecha_evento",
        "fecha_hora_programada",
        "tipo",
        "tipo_cuidado",
        "tipo_estudio",
        "med",
        "medicamento",
        "nota",
        "detalle",
        "descripcion",
        "motivo",
        "puntaje",
        "firma",
        "profesional",
        "observaciones",
        "archivo_url",
    ):
        valor = record.get(clave)
        if valor not in (None, "", [], {}):
            importantes.append((clave, json.dumps(valor, ensure_ascii=False, sort_keys=True, default=str)))

    if importantes:
        return tuple(importantes)

    return tuple(
        sorted(
            (str(clave), json.dumps(valor, ensure_ascii=False, sort_keys=True, default=str))
            for clave, valor in record.items()
            if valor not in (None, "", [], {})
        )
    )


def _merge_records(*groups):
    vistos = set()
    merged = []
    for group in groups:
        for record in group or []:
            if not isinstance(record, dict):
                continue
            normalized = dict(record)
            fp = _record_fingerprint(normalized)
            if fp in vistos:
                continue
            vistos.add(fp)
            merged.append(normalized)
    return merged


def _map_sql_user_name(record):
    usuario = record.get("usuarios")
    if isinstance(usuario, dict):
        return usuario.get("nombre", "")
    return ""


def _sql_sections_empty():
    return {
        "Visitas y Agenda": [],
        "Emergencias y Ambulancia": [],
        "Enfermeria y Plan de Cuidados": [],
        "Escalas Clinicas": [],
        "Auditoria Legal": [],
        "Procedimientos y Evoluciones": [],
        "Estudios Complementarios": [],
        "Signos Vitales": [],
        "Control Pediatrico": [],
        "Plan Terapeutico": [],
        "Consentimientos": [],
    }


def _collect_sql_sections(session_state, paciente_sel, ctx):
    sections = _sql_sections_empty()
    paciente_uuid = ctx.get("paciente_uuid")
    if not paciente_uuid:
        return sections

    cache_key = f"_historial_sql_sections_{paciente_uuid}"
    cache_payload = session_state.get(cache_key, {})
    cache_age = time.monotonic() - cache_payload.get("ts", 0)
    local_ts = session_state.get("_ultimo_guardado_ts", 0)
    if cache_payload and cache_payload.get("local_ts") == local_ts and cache_age < _HISTORIAL_SQL_TTL_SECONDS:
        return {nombre: [dict(r) for r in regs] for nombre, regs in cache_payload.get("sections", {}).items()}

    try:
        from core.db_sql import (
            get_consentimientos_by_paciente,
            get_cuidados_enfermeria,
            get_emergencias_by_paciente,
            get_escalas_by_paciente,
            get_estudios_by_paciente,
            get_evoluciones_by_paciente,
            get_indicaciones_activas,
            get_pediatria_by_paciente,
            get_signos_vitales,
        )

        empresa = ctx.get("empresa") or ""
        fecha_inicio = (pd.Timestamp.now() - pd.Timedelta(days=365 * 3)).isoformat()
        fecha_fin = (pd.Timestamp.now() + pd.Timedelta(days=30)).isoformat()

        for row in get_evoluciones_by_paciente(paciente_uuid):
            sections["Procedimientos y Evoluciones"].append(
                {
                    "id_sql": row.get("id"),
                    "paciente": paciente_sel,
                    "empresa": empresa,
                    "fecha": _format_sql_datetime(row.get("fecha_registro")),
                    "nota": row.get("nota", ""),
                    "firma": row.get("firma_medico") or _map_sql_user_name(row) or "Sistema",
                    "plantilla": row.get("plantilla", "Libre"),
                }
            )

        for row in get_cuidados_enfermeria(paciente_uuid, fecha_inicio, fecha_fin):
            sections["Enfermeria y Plan de Cuidados"].append(
                {
                    "id_sql": row.get("id"),
                    "paciente": paciente_sel,
                    "empresa": empresa,
                    "fecha": _format_sql_datetime(row.get("fecha_registro")),
                    "tipo_cuidado": row.get("tipo_cuidado", ""),
                    "intervencion": row.get("descripcion", ""),
                    "observaciones": row.get("descripcion", ""),
                    "profesional": _map_sql_user_name(row) or "Desconocido",
                    "turno": "S/D",
                    "prioridad": "S/D",
                    "riesgo_caidas": "S/D",
                    "riesgo_upp": "S/D",
                    "dolor": "S/D",
                    "objetivo": "S/D",
                    "respuesta": "S/D",
                    "incidente": False,
                    "zona": "",
                    "aspecto": "",
                }
            )

        for row in get_estudios_by_paciente(paciente_uuid):
            archivo_url = row.get("archivo_url", "")
            sections["Estudios Complementarios"].append(
                {
                    "id_sql": row.get("id"),
                    "paciente": paciente_sel,
                    "empresa": empresa,
                    "fecha": _format_sql_datetime(row.get("fecha_realizacion")),
                    "tipo": row.get("tipo_estudio", ""),
                    "detalle": row.get("informe", ""),
                    "archivo_url": archivo_url,
                    "firma": row.get("medico_solicitante") or _map_sql_user_name(row) or "Sistema",
                    "extension": "pdf" if ".pdf" in str(archivo_url).lower() else "jpg",
                }
            )

        for row in get_signos_vitales(paciente_uuid):
            sections["Signos Vitales"].append(
                {
                    "id_sql": row.get("id"),
                    "paciente": paciente_sel,
                    "empresa": empresa,
                    "fecha": _format_sql_datetime(row.get("fecha_registro")),
                    "TA": row.get("tension_arterial", ""),
                    "FC": row.get("frecuencia_cardiaca", ""),
                    "FR": row.get("frecuencia_respiratoria", ""),
                    "Sat": row.get("saturacion_oxigeno", ""),
                    "Temp": row.get("temperatura", ""),
                    "HGT": row.get("glucemia", ""),
                    "observaciones": row.get("observaciones", ""),
                    "registrado_por": _map_sql_user_name(row),
                }
            )

        for row in get_indicaciones_activas(paciente_uuid):
            extra = row.get("datos_extra", {}) or {}
            med = row.get("medicamento") or extra.get("solucion") or extra.get("detalle_infusion") or ""
            sections["Plan Terapeutico"].append(
                {
                    "id_sql": row.get("id"),
                    "paciente": paciente_sel,
                    "empresa": empresa,
                    "fecha": _format_sql_datetime(row.get("fecha_indicacion")),
                    "med": med,
                    "estado_receta": row.get("estado", "Activa"),
                    "estado_clinico": row.get("estado", "Activa"),
                    "via": row.get("via_administracion", ""),
                    "frecuencia": row.get("frecuencia", ""),
                    "tipo_indicacion": row.get("tipo_indicacion", ""),
                    "dias_duracion": extra.get("dias_duracion", ""),
                    "medico_nombre": extra.get("medico_nombre", ""),
                    "medico_matricula": extra.get("medico_matricula", ""),
                    "hora_inicio": extra.get("hora_inicio", ""),
                    "horarios_programados": extra.get("horarios_programados", []),
                    "solucion": extra.get("solucion", ""),
                    "volumen_ml": extra.get("volumen_ml", 0),
                    "velocidad_ml_h": extra.get("velocidad_ml_h", None),
                    "alternar_con": extra.get("alternar_con", ""),
                    "detalle_infusion": extra.get("detalle_infusion", ""),
                    "plan_hidratacion": extra.get("plan_hidratacion", []),
                }
            )

        for row in get_consentimientos_by_paciente(paciente_uuid):
            sections["Consentimientos"].append(
                {
                    "id_sql": row.get("id"),
                    "paciente": paciente_sel,
                    "empresa": empresa,
                    "fecha": _format_sql_datetime(row.get("fecha_firma")),
                    "tipo_documento": row.get("tipo_documento", ""),
                    "observaciones": row.get("observaciones", ""),
                    "profesional": _map_sql_user_name(row),
                    "archivo_url": row.get("archivo_url"),
                }
            )

        for row in get_pediatria_by_paciente(paciente_uuid):
            talla = row.get("talla_cm") or 0
            peso = row.get("peso_kg") or 0
            imc = round(peso / ((talla / 100) ** 2), 2) if talla else 0
            sections["Control Pediatrico"].append(
                {
                    "id_sql": row.get("id"),
                    "paciente": paciente_sel,
                    "empresa": empresa,
                    "fecha": _format_sql_datetime(row.get("fecha_registro")),
                    "peso": peso,
                    "talla": talla,
                    "pc": row.get("perimetro_cefalico_cm", ""),
                    "imc": imc,
                    "percentil_sug": row.get("percentilo_peso") or row.get("percentilo_talla", ""),
                    "nota": row.get("observaciones", ""),
                    "firma": _map_sql_user_name(row),
                }
            )

        for row in get_escalas_by_paciente(paciente_uuid):
            sections["Escalas Clinicas"].append(
                {
                    "id_sql": row.get("id"),
                    "paciente": paciente_sel,
                    "empresa": empresa,
                    "fecha": _format_sql_datetime(row.get("fecha_registro")),
                    "escala": row.get("tipo_escala", ""),
                    "puntaje": row.get("puntaje_total", ""),
                    "interpretacion": row.get("interpretacion", ""),
                    "observaciones": row.get("observaciones", ""),
                    "profesional": _map_sql_user_name(row),
                }
            )

        for row in get_emergencias_by_paciente(paciente_uuid):
            resolucion = row.get("resolucion", "")
            sections["Emergencias y Ambulancia"].append(
                {
                    "id_sql": row.get("id"),
                    "paciente": paciente_sel,
                    "empresa": empresa,
                    "fecha_evento": _format_sql_datetime(row.get("fecha_llamado")),
                    "categoria_evento": row.get("prioridad", ""),
                    "tipo": row.get("estado", ""),
                    "motivo": row.get("motivo", ""),
                    "destino": resolucion,
                    "profesional": _map_sql_user_name(row),
                    "observaciones": resolucion,
                }
            )
    except Exception:
        sections = sections or _sql_sections_empty()

    session_state[cache_key] = {
        "ts": time.monotonic(),
        "local_ts": local_ts,
        "sections": {nombre: [dict(r) for r in regs] for nombre, regs in sections.items()},
    }
    return sections


def collect_patient_sections(session_state, paciente_sel):
    ctx = _patient_context(session_state, paciente_sel)
    local_sections = {
        "Auditoria de Presencia": _local_section_records(session_state, "checkin_db", paciente_sel, ctx),
        "Visitas y Agenda": _local_section_records(session_state, "agenda_db", paciente_sel, ctx),
        "Emergencias y Ambulancia": _local_section_records(session_state, "emergencias_db", paciente_sel, ctx),
        "Enfermeria y Plan de Cuidados": _local_section_records(session_state, "cuidados_enfermeria_db", paciente_sel, ctx),
        "Escalas Clinicas": _local_section_records(session_state, "escalas_clinicas_db", paciente_sel, ctx),
        "Auditoria Legal": _local_section_records(session_state, "auditoria_legal_db", paciente_sel, ctx),
        "Procedimientos y Evoluciones": _local_section_records(session_state, "evoluciones_db", paciente_sel, ctx),
        "Estudios Complementarios": _local_section_records(session_state, "estudios_db", paciente_sel, ctx),
        "Materiales Utilizados": _local_section_records(session_state, "consumos_db", paciente_sel, ctx),
        "Registro de Heridas": _local_section_records(session_state, "fotos_heridas_db", paciente_sel, ctx),
        "Signos Vitales": _local_section_records(session_state, "vitales_db", paciente_sel, ctx),
        "Control Pediatrico": _local_section_records(session_state, "pediatria_db", paciente_sel, ctx),
        "Balance Hidrico": _local_section_records(session_state, "balance_db", paciente_sel, ctx),
        "Plan Terapeutico": _local_section_records(session_state, "indicaciones_db", paciente_sel, ctx),
        "Consentimientos": _local_section_records(session_state, "consentimientos_db", paciente_sel, ctx),
        "Cobros y Facturacion": _local_section_records(session_state, "facturacion_db", paciente_sel, ctx),
    }
    sql_sections = _collect_sql_sections(session_state, paciente_sel, ctx)
    return {
        nombre: _merge_records(local_sections.get(nombre, []), sql_sections.get(nombre, []))
        for nombre in (
            "Auditoria de Presencia",
            "Visitas y Agenda",
            "Emergencias y Ambulancia",
            "Enfermeria y Plan de Cuidados",
            "Escalas Clinicas",
            "Auditoria Legal",
            "Procedimientos y Evoluciones",
            "Estudios Complementarios",
            "Materiales Utilizados",
            "Registro de Heridas",
            "Signos Vitales",
            "Control Pediatrico",
            "Balance Hidrico",
            "Plan Terapeutico",
            "Consentimientos",
            "Cobros y Facturacion",
        )
    }


def build_patient_excel_bytes(session_state, paciente_sel):
    from datetime import datetime as _dt

    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    nom_pac = paciente_sel.split(" - ")[0] if " - " in paciente_sel else paciente_sel

    output = io.BytesIO()
    try:
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
        engine = "openpyxl"
    except Exception:
        try:
            import xlsxwriter  # noqa: F401
            engine = "xlsxwriter"
        except Exception:
            return None

    # Hojas a generar
    sheets = {}
    for section_name, records in collect_patient_sections(session_state, paciente_sel).items():
        if not records:
            continue
        df = pd.DataFrame(records).drop(columns=["paciente", "empresa", "firma_b64"], errors="ignore")
        sheets[section_name[:31]] = df

    if not sheets:
        sheets["Sin registros"] = pd.DataFrame([{"mensaje": "No hay registros clinicos para este paciente."}])

    with pd.ExcelWriter(output, engine=engine) as writer:
        # Hoja resumen al inicio
        resumen_rows = [
            {"Seccion": sec, "Registros": len(df)}
            for sec, df in sheets.items()
        ]
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
                # Estilo header
                fill = _hdr_fill_green if ws.title == "Resumen" else _hdr_fill_navy
                for cell in ws[1]:
                    cell.font = _hdr_font
                    cell.fill = fill
                    cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    cell.border = _border
                ws.row_dimensions[1].height = 22

                # Auto-ancho columnas
                for col in ws.columns:
                    max_len = max(
                        (len(str(c.value)) if c.value is not None else 0)
                        for c in col
                    )
                    ws.column_dimensions[col[0].column_letter].width = min(max(max_len + 3, 10), 50)

                # Celdas de datos
                alt_fill = PatternFill("solid", fgColor="F3F4F6")
                for i, row in enumerate(ws.iter_rows(min_row=2), start=2):
                    row_fill = alt_fill if i % 2 == 0 else None
                    for cell in row:
                        cell.border = _border
                        cell.alignment = Alignment(wrap_text=True, vertical="top")
                        if row_fill:
                            cell.fill = row_fill
                ws.freeze_panes = "A2"

            # Portada en hoja Resumen
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


def _pdf_header_oscuro(pdf, empresa, titulo, subtitulo="", badge_txt="", badge_rgb=(60, 80, 120)):
    """Cabecera oscura unificada para todos los PDFs del sistema."""
    header_h = 36
    pdf.set_fill_color(22, 38, 68)
    pdf.rect(0, 0, pdf.w, header_h, "F")
    pdf.set_fill_color(*badge_rgb)
    pdf.rect(0, 0, 5, header_h, "F")
    for ruta in [
        ASSETS_DIR / "logo_medicare_pro.jpeg",
        ASSETS_DIR / "logo_medicare_pro.jpg",
        ASSETS_DIR / "logo_medicare_pro.png",
    ]:
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

    from datetime import datetime as _dt
    buffer = io.BytesIO()
    _PAGE_W = A4[0] - 60  # usable width (margins 30+30)
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=30, leftMargin=30, topMargin=20, bottomMargin=30)
    elements = []
    styles = getSampleStyleSheet()

    normal_style = ParagraphStyle('NormalHC', parent=styles['Normal'], fontSize=9, leading=12)
    italic_style = ParagraphStyle('ItalicHC', parent=styles['Normal'], fontSize=9, leading=12, fontName='Helvetica-Oblique')

    def _limpiar(texto):
        if texto in [None, '', '-', 'S/D', 'Sin datos']: return '-'
        t = str(texto).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
        return t.replace('\n', '<br/>')

    def _sec_hdr(titulo):
        p = Paragraph(
            f'<font color="white"><b>  {_limpiar(titulo).upper()}</b></font>',
            ParagraphStyle('SH', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=9, leading=14)
        )
        t = Table([[p]], colWidths=[_PAGE_W])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, 0), colors.HexColor('#162644')),
            ('TOPPADDING', (0, 0), (0, 0), 5),
            ('BOTTOMPADDING', (0, 0), (0, 0), 5),
        ]))
        return t

    def _tabla_sec(titulo, cabeceras, claves, registros, anchos):
        if not registros:
            return
        hdr_s = ParagraphStyle('TH', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8, textColor=colors.white, alignment=1)
        cel_c = ParagraphStyle('TC', parent=styles['Normal'], fontSize=8, alignment=1)
        cel_l = ParagraphStyle('TL', parent=styles['Normal'], fontSize=8, alignment=0)
        datos = [[Paragraph(c, hdr_s) for c in cabeceras]]
        for reg in registros:
            fila = []
            for clave in claves:
                estilo = cel_l if clave in ('med', 'insumo', 'nota', 'observaciones') else cel_c
                fila.append(Paragraph(_limpiar(reg.get(clave, '-')), estilo))
            datos.append(fila)
        t = Table(datos, colWidths=anchos, repeatRows=1)
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#374151')),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#D1D5DB')),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#F9FAFB')]),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
            ('TOPPADDING', (0, 0), (-1, -1), 4),
        ]))
        elements.append(_sec_hdr(titulo))
        elements.append(Spacer(1, 3))
        elements.append(t)
        elements.append(Spacer(1, 10))

    # ── Cabecera navy con logo ────────────────────────────────────────
    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    sections = collect_patient_sections(session_state, paciente_sel)
    nombre_empresa = detalles.get('empresa', mi_empresa)
    nom_pac = paciente_sel.split(' - ')[0] if ' - ' in paciente_sel else paciente_sel
    fecha_gen = _dt.now().strftime('%d/%m/%Y %H:%M')

    logo_cell = ''
    for ruta in [ASSETS_DIR/'logo_medicare_pro.jpeg', ASSETS_DIR/'logo_medicare_pro.jpg', ASSETS_DIR/'logo_medicare_pro.png']:
        if ruta.exists() and RLImage is not None:
            try:
                logo_cell = RLImage(str(ruta), width=52, height=52)
            except Exception:
                pass
            break

    hdr_txt = Paragraph(
        f'<font size="14" color="white"><b>{_limpiar(nombre_empresa)}</b></font><br/>'
        f'<font size="9" color="#A0C8FF"><b>HISTORIA CLINICA DIGITAL INTEGRAL</b></font><br/>'
        f'<font size="7" color="#C8D2E6">Paciente: {_limpiar(nom_pac)}   |   Generado: {fecha_gen}</font>',
        ParagraphStyle('HdrTxt', parent=styles['Normal'], leading=18)
    )
    badge_txt = Paragraph(
        '<font size="10" color="white"><b>Historia<br/>Clinica</b></font>',
        ParagraphStyle('Badge', parent=styles['Normal'], alignment=1, leading=14)
    )
    hdr_table = Table([[logo_cell, hdr_txt, badge_txt]], colWidths=[60, 410, 70])
    hdr_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#162644')),
        ('BACKGROUND', (2, 0), (2, 0), colors.HexColor('#0D5A50')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('LEFTPADDING', (0, 0), (0, 0), 8),
        ('LEFTPADDING', (1, 0), (1, 0), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 10),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
    ]))
    elements.append(hdr_table)
    elements.append(Spacer(1, 10))

    # ── Datos demográficos ────────────────────────────────────────────
    lbl_s = ParagraphStyle('Lbl', parent=styles['Normal'], fontName='Helvetica-Bold', fontSize=8)
    val_s = ParagraphStyle('Val', parent=styles['Normal'], fontSize=8)

    def _lbl(t): return Paragraph(t, lbl_s)
    def _val(t): return Paragraph(_limpiar(t), val_s)

    datos_pac = [
        [_lbl('Paciente'), _val(nom_pac), _lbl('DNI'), _val(detalles.get('dni'))],
        [_lbl('Fecha Nac.'), _val(detalles.get('fnac')), _lbl('Sexo'), _val(detalles.get('sexo'))],
        [_lbl('Obra Social'), _val(detalles.get('obra_social')), _lbl('Telefono'), _val(detalles.get('telefono'))],
        [_lbl('Domicilio'), _val(detalles.get('direccion')), _lbl('Estado'), _val(detalles.get('estado', 'Activo'))],
    ]
    t_pac = Table(datos_pac, colWidths=[70, 180, 70, 220])
    t_pac.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F3F4F6')),
        ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#D1D5DB')),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
    ]))
    elements.append(_sec_hdr('Datos del paciente'))
    elements.append(Spacer(1, 3))
    elements.append(t_pac)

    alergias_txt = detalles.get('alergias', '') or detalles.get('patologias', '')
    if alergias_txt and alergias_txt not in ('-', 'Sin datos'):
        alerg_data = [[_lbl('Alergias / Riesgos'), _val(alergias_txt)]]
        t_al = Table(alerg_data, colWidths=[120, 420])
        t_al.setStyle(TableStyle([
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#991B1B')),
            ('GRID', (0, 0), (-1, -1), 0.4, colors.HexColor('#FCA5A5')),
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#FEF2F2')),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        elements.append(t_al)
    elements.append(Spacer(1, 12))

    # ── Evoluciones y enfermería ──────────────────────────────────────
    registros_clinicos = sections.get('Procedimientos y Evoluciones', []) + sections.get('Enfermeria y Plan de Cuidados', [])
    if registros_clinicos:
        elements.append(_sec_hdr('Evoluciones clinicas y enfermeria'))
        elements.append(Spacer(1, 4))
        for reg in sorted(registros_clinicos, key=lambda x: x.get('fecha', '')):
            fecha = _limpiar(reg.get('fecha', 'S/D'))
            firma = _limpiar(reg.get('firma', reg.get('profesional', 'S/D')))
            nota = _limpiar(
                reg.get('nota')
                or reg.get('intervencion')
                or reg.get('descripcion')
                or reg.get('observaciones')
                or 'Sin detalle'
            )
            bloque = [
                Paragraph(f'<b>{fecha}</b>  |  {firma}', italic_style),
                Spacer(1, 2),
                Paragraph(nota, normal_style),
                Spacer(1, 8),
            ]
            elements.append(KeepTogether(bloque))

    # ── Tablas de módulos ─────────────────────────────────────────────
    vits = sections.get('Signos Vitales', [])
    _tabla_sec('Signos vitales', ['Fecha', 'T.A.', 'F.C.', 'F.R.', 'SatO2', 'Temp', 'HGT'],
               ['fecha', 'TA', 'FC', 'FR', 'Sat', 'Temp', 'HGT'], vits, [95, 60, 50, 50, 50, 50, 50])

    balances = sections.get('Balance Hidrico', [])
    _tabla_sec('Balance hidrico', ['Fecha', 'Turno', 'Ingresos', 'Egresos', 'Balance', 'Firma'],
               ['fecha', 'turno', 'ingresos', 'egresos', 'balance', 'firma'], balances, [90, 90, 60, 60, 65, 100])

    meds = sections.get('Plan Terapeutico', [])
    _tabla_sec('Plan terapeutico', ['Fecha', 'Medicacion / Indicacion', 'Estado', 'Profesional'],
               ['fecha', 'med', 'estado_receta', 'medico_nombre'], meds, [80, 240, 70, 75])

    materiales = sections.get('Materiales Utilizados', [])
    _tabla_sec('Materiales e insumos', ['Fecha', 'Insumo / Descripcion', 'Cantidad', 'Firma'],
               ['fecha', 'insumo', 'cantidad', 'firma'], materiales, [90, 240, 60, 75])

    emergencias = sections.get('Emergencias y Ambulancia', [])
    _tabla_sec('Emergencias y traslados', ['Fecha', 'Triage', 'Motivo', 'Profesional', 'Destino'],
               ['fecha_evento', 'triage_grado', 'motivo', 'profesional', 'destino'], emergencias, [80, 80, 200, 90, 85])

    estudios = sections.get('Estudios Complementarios', [])
    _tabla_sec('Estudios complementarios', ['Fecha', 'Tipo', 'Detalle / Informe', 'Profesional'],
               ['fecha', 'tipo', 'detalle', 'firma'], estudios, [80, 100, 240, 75])

    pediatria = sections.get('Control Pediatrico', [])
    _tabla_sec('Control pediatrico', ['Fecha', 'Peso (kg)', 'Talla (cm)', 'PC (cm)', 'IMC', 'Percentil', 'Profesional'],
               ['fecha', 'peso', 'talla', 'pc', 'imc', 'percentil_sug', 'firma'],
               pediatria, [80, 55, 55, 55, 45, 65, 140])

    escalas = sections.get('Escalas Clinicas', [])
    _tabla_sec('Escalas clinicas', ['Fecha', 'Escala', 'Puntaje', 'Interpretacion', 'Profesional'],
               ['fecha', 'escala', 'puntaje', 'interpretacion', 'profesional'],
               escalas, [80, 120, 60, 170, 75])

    consentimientos = sections.get('Consentimientos', [])
    _tabla_sec('Consentimientos informados', ['Fecha', 'Tipo documento', 'Observaciones', 'Profesional'],
               ['fecha', 'tipo_documento', 'observaciones', 'profesional'],
               consentimientos, [80, 140, 225, 75])

    if not (registros_clinicos or vits or balances or meds or materiales or emergencias
            or estudios or pediatria or escalas or consentimientos):
        elements.append(Spacer(1, 20))
        elements.append(Paragraph('<i>No hay registros clinicos cargados para este paciente.</i>', normal_style))

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

    _pdf_header_oscuro(
        pdf, empresa,
        "RESPALDO CLINICO DEL PACIENTE",
        subtitulo=safe_text(f"{nom_pac}  ·  DNI: {dni_final}  ·  Generado: {generado}"),
        badge_txt="Historia Clinica",
        badge_rgb=(13, 90, 80),
    )

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
    pdf.set_margins(14, 12, 14)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    _pdf_header_oscuro(
        pdf, detalles.get("empresa", mi_empresa),
        "CONSENTIMIENTO INFORMADO",
        subtitulo="Atencion y Terapia en Domicilio",
        badge_txt="Consentimiento",
        badge_rgb=(13, 90, 80),
    )
    pdf.ln(4)

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

    _estado_colors = {
        "Activa": (13, 90, 80),
        "Suspendida": (180, 60, 20),
        "Completada": (60, 80, 120),
        "Modificada": (130, 100, 0),
    }
    _badge_color = _estado_colors.get(estado_actual, (60, 80, 120))

    pdf = FPDF()
    pdf.set_margins(14, 12, 14)
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    _pdf_header_oscuro(
        pdf, detalles.get("empresa", mi_empresa),
        "PRESCRIPCION Y ACTA LEGAL DE MEDICACION",
        subtitulo=safe_text(f"Paciente: {paciente_sel.split(' - ')[0]}  ·  Medico: {medico_indicante}  ·  Mat: {matricula_indicante}"),
        badge_txt=estado_actual,
        badge_rgb=_badge_color,
    )

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
    _triage_colors = {
        "Grado 1 - Rojo":    (192, 38,  38),
        "Grado 2 - Amarillo":(180, 120,  0),
        "Grado 3 - Verde":   ( 22, 120, 60),
    }
    triage_grado = record.get("triage_grado", "")
    triage_rgb = _triage_colors.get(triage_grado, (60, 80, 120))

    def _v(val, fallback=""):
        return str(val).strip() if val not in _SKIP else fallback

    def _row(pdf, label, value, lw=48, lh=5):
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
        usable = pdf.w - pdf.l_margin - pdf.r_margin
        col_w = usable / cols
        items = [(l, _v(v)) for l, v in pairs if _v(v)]
        for i in range(0, len(items), cols):
            row_items = items[i:i + cols]
            x_start = pdf.l_margin
            for j, (lbl, val) in enumerate(row_items):
                pdf.set_xy(x_start + j * col_w, pdf.get_y())
                pdf.set_font("Arial", "B", 8)
                pdf.set_text_color(80, 80, 100)
                pdf.cell(28, 5, safe_text(lbl) + ":", border=0)
                pdf.set_font("Arial", "", 8)
                pdf.set_text_color(20, 20, 20)
                pdf.cell(col_w - 28, 5, safe_text(val[:40]), border=0)
            pdf.ln(5)
        pdf.set_text_color(0, 0, 0)

    def _sec(pdf, title):
        if pdf.get_y() > 262:
            pdf.add_page()
        pdf.ln(2)
        pdf.set_fill_color(35, 55, 90)
        pdf.set_text_color(255, 255, 255)
        pdf.set_font("Arial", "B", 8)
        pdf.set_x(pdf.l_margin)
        pdf.cell(0, 6, safe_text("  " + title.upper()), ln=True, fill=True)
        pdf.set_text_color(0, 0, 0)
        pdf.ln(2)

    pdf = FPDF()
    pdf.set_margins(14, 12, 14)
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()

    # ── Cabecera: bloque oscuro completo ──────────────────────────────
    header_h = 36
    # Fondo principal azul oscuro
    pdf.set_fill_color(22, 38, 68)
    pdf.rect(0, 0, pdf.w, header_h, "F")
    # Franja de color de triage en el margen izquierdo
    pdf.set_fill_color(*triage_rgb)
    pdf.rect(0, 0, 5, header_h, "F")

    # Logo dentro del header
    logo_y = 5
    logo_w = 26
    for ruta in [
        ASSETS_DIR / "logo_medicare_pro.jpeg",
        ASSETS_DIR / "logo_medicare_pro.jpg",
        ASSETS_DIR / "logo_medicare_pro.png",
    ]:
        if ruta.exists():
            try:
                pdf.image(str(ruta), x=8, y=logo_y, w=logo_w)
            except Exception:
                pass
            break

    # Empresa + título en blanco
    pdf.set_xy(38, 7)
    pdf.set_font("Arial", "B", 14)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 7, safe_text(detalles.get("empresa", mi_empresa)), ln=True)
    pdf.set_x(38)
    pdf.set_font("Arial", "B", 8)
    pdf.set_text_color(160, 200, 255)
    pdf.cell(0, 5, "ACTA DE EMERGENCIA Y TRASLADO", ln=True)
    pdf.set_x(38)
    pdf.set_font("Arial", "", 7)
    pdf.set_text_color(200, 210, 230)
    pdf.cell(0, 5, safe_text(
        f"Fecha: {record.get('fecha_evento','')} {record.get('hora_evento','')}   "
        f"Profesional: {prof_nombre}   Mat: {prof_mat}"
    ), ln=True)

    # Badge de triage (esquina superior derecha dentro del header)
    badge_w = 52
    badge_x = pdf.w - badge_w - 6
    pdf.set_fill_color(*triage_rgb)
    pdf.rect(badge_x, 10, badge_w, 16, "F")
    pdf.set_font("Arial", "B", 10)
    pdf.set_text_color(255, 255, 255)
    pdf.set_xy(badge_x, 12)
    pdf.cell(badge_w, 6, safe_text(triage_grado or "Sin triage"), align="C", border=0, ln=True)
    pdf.set_font("Arial", "", 7)
    pdf.set_xy(badge_x, 19)
    pdf.cell(badge_w, 5, safe_text(_v(record.get("prioridad", ""))), align="C", border=0)

    # Resetear colores y posicion
    pdf.set_text_color(0, 0, 0)
    pdf.set_xy(pdf.l_margin, header_h + 4)

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
