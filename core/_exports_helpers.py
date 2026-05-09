"""Helpers internos de clinical_exports: contexto de paciente, SQL sections, merge, fingerprint.

Extraído de core/clinical_exports.py para mantenerlo manejable.
"""
import json
import time
from pathlib import Path

import pandas as pd

from core.export_utils import safe_text
from core.utils import decodificar_base64_seguro, mapa_detalles_pacientes
from core.app_logging import log_event

_HISTORIAL_SQL_TTL_SECONDS = 120
ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"


# ---------------------------------------------------------------------------
# Helpers de identidad de paciente
# ---------------------------------------------------------------------------

def split_patient_visual_id(paciente_sel):
    texto = str(paciente_sel or "").strip()
    if " - " not in texto:
        return texto, ""
    nombre, dni = texto.rsplit(" - ", 1)
    return nombre.strip(), dni.strip()


def normalize_patient_name(nombre):
    return " ".join(str(nombre or "").strip().lower().split())


def format_sql_datetime(valor, *, default=""):
    if valor in (None, ""):
        return default
    try:
        dt = pd.to_datetime(valor, errors="coerce")
    except Exception as _exc:
        log_event("exports_helpers", f"format_sql_datetime_falla:{type(_exc).__name__}")
        dt = None
    if dt is None or pd.isna(dt):
        return str(valor).replace("T", " ").strip()
    if isinstance(valor, str) and len(valor.strip()) <= 10 and dt.hour == 0 and dt.minute == 0:
        return dt.strftime("%d/%m/%Y")
    return dt.strftime("%d/%m/%Y %H:%M")


# ---------------------------------------------------------------------------
# Contexto del paciente (cacheado en session_state)
# ---------------------------------------------------------------------------

def patient_context(session_state, paciente_sel):
    _ck_ctx = f"_ce_ctx_{paciente_sel}"
    cached = session_state.get(_ck_ctx)
    if cached is not None:
        return cached
    detalles = mapa_detalles_pacientes(session_state).get(paciente_sel, {})
    nombre_visual, dni_visual = split_patient_visual_id(paciente_sel)
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
        except Exception as _exc:
            log_event("exports_helpers", f"uuid_resolution_falla:{type(_exc).__name__}")
            empresa_id = None
            paciente_uuid = None
    result = {
        "nombre": nombre,
        "dni": dni,
        "empresa": empresa,
        "empresa_id": empresa_id,
        "paciente_uuid": paciente_uuid,
        "detalles": detalles,
    }
    try:
        session_state[_ck_ctx] = result
    except Exception as _exc:
        log_event("exports_helpers", f"fallo_cache_contexto:{type(_exc).__name__}")
    return result


def record_matches_patient(record, paciente_sel, ctx):
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
            _, dni_valor = split_patient_visual_id(valor)
            if dni_valor and dni_valor == dni_ref:
                return True
            if valor == dni_ref:
                return True
    nombre_ref = normalize_patient_name(ctx.get("nombre"))
    if not nombre_ref:
        return False
    for valor in candidatos:
        nombre_valor, dni_valor = split_patient_visual_id(valor)
        if dni_ref and dni_valor and dni_valor != dni_ref:
            continue
        if normalize_patient_name(nombre_valor) == nombre_ref:
            return True
    return False


def local_section_records(session_state, session_key, paciente_sel, ctx):
    return [
        dict(registro)
        for registro in session_state.get(session_key, [])
        if isinstance(registro, dict) and record_matches_patient(registro, paciente_sel, ctx)
    ]


# ---------------------------------------------------------------------------
# Fingerprint y merge de registros
# ---------------------------------------------------------------------------

def record_fingerprint(record):
    importantes = []
    for clave in (
        "id", "id_sql", "_id_local", "fecha", "fecha_evento", "fecha_hora_programada",
        "tipo", "tipo_cuidado", "tipo_estudio", "med", "medicamento", "nota", "detalle",
        "descripcion", "motivo", "puntaje", "firma", "profesional", "observaciones", "archivo_url",
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


def merge_records(*groups):
    vistos = set()
    merged = []
    for group in groups:
        for record in group or []:
            if not isinstance(record, dict):
                continue
            normalized = dict(record)
            fp = record_fingerprint(normalized)
            if fp in vistos:
                continue
            vistos.add(fp)
            merged.append(normalized)
    return merged


# ---------------------------------------------------------------------------
# SQL sections
# ---------------------------------------------------------------------------

def map_sql_user_name(record):
    usuario = record.get("usuarios")
    if isinstance(usuario, dict):
        return usuario.get("nombre", "")
    return ""


def sql_sections_empty():
    return {
        "Visitas y Agenda": [],
        "Emergencias y Ambulancia": [],
        "Enfermeria y Plan de Cuidados": [],
        "Escalas Clinicas": [],
        "Auditoria Legal": [],
        "Procedimientos y Evoluciones": [],
        "Estudios Complementarios": [],
        "Signos Vitales": [],
        "Control Percentilo": [],
        "Plan Terapeutico": [],
        "Consentimientos": [],
    }


def collect_sql_sections(session_state, paciente_sel, ctx):
    sections = sql_sections_empty()
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
        for row in get_evoluciones_by_paciente(paciente_uuid):
            sections["Procedimientos y Evoluciones"].append({
                "id_sql": row.get("id"), "paciente": paciente_sel, "empresa": empresa,
                "fecha": format_sql_datetime(row.get("fecha_registro")),
                "nota": row.get("nota", ""),
                "firma": row.get("firma_medico") or map_sql_user_name(row) or "Sistema",
                "plantilla": row.get("plantilla", "Libre"),
            })

        fecha_inicio = (pd.Timestamp.now() - pd.Timedelta(days=365 * 3)).isoformat()
        fecha_fin = (pd.Timestamp.now() + pd.Timedelta(days=30)).isoformat()
        for row in get_cuidados_enfermeria(paciente_uuid, fecha_inicio, fecha_fin):
            sections["Enfermeria y Plan de Cuidados"].append({
                "id_sql": row.get("id"), "paciente": paciente_sel, "empresa": empresa,
                "fecha": format_sql_datetime(row.get("fecha_registro")),
                "tipo_cuidado": row.get("tipo_cuidado", ""),
                "intervencion": row.get("descripcion", ""),
                "observaciones": row.get("descripcion", ""),
                "profesional": map_sql_user_name(row) or "Desconocido",
                "turno": "S/D", "prioridad": "S/D", "riesgo_caidas": "S/D", "riesgo_upp": "S/D",
                "dolor": "S/D", "objetivo": "S/D", "respuesta": "S/D",
                "incidente": False, "zona": "", "aspecto": "",
            })

        for row in get_estudios_by_paciente(paciente_uuid):
            archivo_url = row.get("archivo_url", "")
            sections["Estudios Complementarios"].append({
                "id_sql": row.get("id"), "paciente": paciente_sel, "empresa": empresa,
                "fecha": format_sql_datetime(row.get("fecha_realizacion")),
                "tipo": row.get("tipo_estudio", ""),
                "detalle": row.get("informe", ""),
                "archivo_url": archivo_url,
                "firma": row.get("medico_solicitante") or map_sql_user_name(row) or "Sistema",
                "extension": "pdf" if ".pdf" in str(archivo_url).lower() else "jpg",
            })

        for row in get_signos_vitales(paciente_uuid):
            sections["Signos Vitales"].append({
                "id_sql": row.get("id"), "paciente": paciente_sel, "empresa": empresa,
                "fecha": format_sql_datetime(row.get("fecha_registro")),
                "TA": row.get("tension_arterial", ""), "FC": row.get("frecuencia_cardiaca", ""),
                "FR": row.get("frecuencia_respiratoria", ""), "Sat": row.get("saturacion_oxigeno", ""),
                "Temp": row.get("temperatura", ""), "HGT": row.get("glucemia", ""),
                "observaciones": row.get("observaciones", ""),
                "registrado_por": map_sql_user_name(row),
            })

        for row in get_indicaciones_activas(paciente_uuid):
            extra = row.get("datos_extra", {}) or {}
            med = row.get("medicamento") or extra.get("solucion") or extra.get("detalle_infusion") or ""
            sections["Plan Terapeutico"].append({
                "id_sql": row.get("id"), "paciente": paciente_sel, "empresa": empresa,
                "fecha": format_sql_datetime(row.get("fecha_indicacion")),
                "med": med, "estado_receta": row.get("estado", "Activa"),
                "estado_clinico": row.get("estado", "Activa"),
                "via": row.get("via_administracion", ""), "frecuencia": row.get("frecuencia", ""),
                "tipo_indicacion": row.get("tipo_indicacion", ""),
                "dias_duracion": extra.get("dias_duracion", ""),
                "medico_nombre": extra.get("medico_nombre", ""),
                "medico_matricula": extra.get("medico_matricula", ""),
                "hora_inicio": extra.get("hora_inicio", ""),
                "horarios_programados": extra.get("horarios_programados", []),
                "solucion": extra.get("solucion", ""), "volumen_ml": extra.get("volumen_ml", 0),
                "velocidad_ml_h": extra.get("velocidad_ml_h", None),
                "alternar_con": extra.get("alternar_con", ""),
                "detalle_infusion": extra.get("detalle_infusion", ""),
                "plan_hidratacion": extra.get("plan_hidratacion", []),
            })

        for row in get_consentimientos_by_paciente(paciente_uuid):
            sections["Consentimientos"].append({
                "id_sql": row.get("id"), "paciente": paciente_sel, "empresa": empresa,
                "fecha": format_sql_datetime(row.get("fecha_firma")),
                "tipo_documento": row.get("tipo_documento", ""),
                "observaciones": row.get("observaciones", ""),
                "profesional": map_sql_user_name(row),
                "archivo_url": row.get("archivo_url"),
            })

        for row in get_pediatria_by_paciente(paciente_uuid):
            talla = row.get("talla_cm") or 0
            peso = row.get("peso_kg") or 0
            imc = round(peso / ((talla / 100) ** 2), 2) if talla else 0
            sections["Control Percentilo"].append({
                "id_sql": row.get("id"), "paciente": paciente_sel, "empresa": empresa,
                "fecha": format_sql_datetime(row.get("fecha_registro")),
                "peso": peso, "talla": talla,
                "pc": row.get("perimetro_cefalico_cm", ""),
                "imc": imc,
                "percentil_sug": row.get("percentilo_peso") or row.get("percentilo_talla", ""),
                "nota": row.get("observaciones", ""),
                "firma": map_sql_user_name(row),
            })

        for row in get_escalas_by_paciente(paciente_uuid):
            sections["Escalas Clinicas"].append({
                "id_sql": row.get("id"), "paciente": paciente_sel, "empresa": empresa,
                "fecha": format_sql_datetime(row.get("fecha_registro")),
                "escala": row.get("tipo_escala", ""), "puntaje": row.get("puntaje_total", ""),
                "interpretacion": row.get("interpretacion", ""),
                "observaciones": row.get("observaciones", ""),
                "profesional": map_sql_user_name(row),
            })

        for row in get_emergencias_by_paciente(paciente_uuid):
            resolucion = row.get("resolucion", "")
            sections["Emergencias y Ambulancia"].append({
                "id_sql": row.get("id"), "paciente": paciente_sel, "empresa": empresa,
                "fecha_evento": format_sql_datetime(row.get("fecha_llamado")),
                "categoria_evento": row.get("prioridad", ""),
                "tipo": row.get("estado", ""),
                "motivo": row.get("motivo", ""),
                "destino": resolucion,
                "profesional": map_sql_user_name(row),
                "observaciones": resolucion,
            })
    except Exception as _exc:
        log_event("exports_helpers", f"build_sql_sections_falla:{type(_exc).__name__}")
        sections = sections or sql_sections_empty()

    session_state[cache_key] = {
        "ts": time.monotonic(),
        "local_ts": local_ts,
        "sections": {nombre: [dict(r) for r in regs] for nombre, regs in sections.items()},
    }
    return sections


# ---------------------------------------------------------------------------
# Función pública principal
# ---------------------------------------------------------------------------

def collect_patient_sections(session_state, paciente_sel):
    """
    Wrapper compatible con tests viejos que monkeypatchean helpers en `core.clinical_exports`.
    """
    _ck_secs = f"_ce_secs_{paciente_sel}"
    _secs_cached = session_state.get(_ck_secs)
    local_ts = session_state.get("_ultimo_guardado_ts", 0)

    # CORRECCIÓN: Se eliminaron los espacios en "local_ts" y "ts"
    if (
        _secs_cached is not None
        and isinstance(_secs_cached, dict)
        and _secs_cached.get("local_ts") == local_ts
        and time.monotonic() - _secs_cached.get("ts", 0) < 30
    ):
        return _secs_cached["sections"]

    ctx = patient_context(session_state, paciente_sel)
    local_sections = {
        "Auditoria de Presencia": local_section_records(session_state, "checkin_db", paciente_sel, ctx),
        "Visitas y Agenda": local_section_records(session_state, "agenda_db", paciente_sel, ctx),
        "Emergencias y Ambulancia": local_section_records(session_state, "emergencias_db", paciente_sel, ctx),
        "Enfermeria y Plan de Cuidados": local_section_records(session_state, "cuidados_enfermeria_db", paciente_sel, ctx),
        "Escalas Clinicas": local_section_records(session_state, "escalas_clinicas_db", paciente_sel, ctx),
        "Auditoria Legal": local_section_records(session_state, "auditoria_legal_db", paciente_sel, ctx),
        "Procedimientos y Evoluciones": local_section_records(session_state, "evoluciones_db", paciente_sel, ctx),
        "Estudios Complementarios": local_section_records(session_state, "estudios_db", paciente_sel, ctx),
        "Materiales Utilizados": local_section_records(session_state, "consumos_db", paciente_sel, ctx),
        "Registro de Heridas": local_section_records(session_state, "fotos_heridas_db", paciente_sel, ctx),
        "Signos Vitales": local_section_records(session_state, "vitales_db", paciente_sel, ctx),
        "Control Percentilo": local_section_records(session_state, "pediatria_db", paciente_sel, ctx),
        "Balance Hidrico": local_section_records(session_state, "balance_db", paciente_sel, ctx),
        "Plan Terapeutico": local_section_records(session_state, "indicaciones_db", paciente_sel, ctx),
        "Consentimientos": local_section_records(session_state, "consentimientos_db", paciente_sel, ctx),
        "Cobros y Facturacion": local_section_records(session_state, "facturacion_db", paciente_sel, ctx),
    }
    sql_sections = collect_sql_sections(session_state, paciente_sel, ctx)
    merged = {
        nombre: merge_records(local_sections.get(nombre, []), sql_sections.get(nombre, []))
        for nombre in (
            "Auditoria de Presencia", "Visitas y Agenda", "Emergencias y Ambulancia",
            "Enfermeria y Plan de Cuidados", "Escalas Clinicas", "Auditoria Legal",
            "Procedimientos y Evoluciones", "Estudios Complementarios", "Materiales Utilizados",
            "Registro de Heridas", "Signos Vitales", "Control Percentilo",
            "Balance Hidrico", "Plan Terapeutico", "Consentimientos", "Cobros y Facturacion",
        )
    }
    try:
        session_state[_ck_secs] = {"ts": time.monotonic(), "local_ts": local_ts, "sections": merged}
    except Exception as _exc:
        log_event("exports_helpers", f"fallo_cache_secciones:{type(_exc).__name__}")
    return merged


# ---------------------------------------------------------------------------
# Firma del paciente / médico
# ---------------------------------------------------------------------------

def patient_signature_bytes(session_state, paciente_sel):
    consentimientos = collect_patient_sections(session_state, paciente_sel).get("Consentimientos", [])
    for registro in reversed(consentimientos):
        if registro.get("firma_b64"):
            firma_bytes = decodificar_base64_seguro(registro["firma_b64"])
            if firma_bytes:
                return firma_bytes
    ctx = patient_context(session_state, paciente_sel)
    firmas = [
        x for x in session_state.get("firmas_tactiles_db", [])
        if isinstance(x, dict) and record_matches_patient(x, paciente_sel, ctx)
    ]
    for registro in reversed(firmas):
        if registro.get("firma_img"):
            firma_bytes = decodificar_base64_seguro(registro["firma_img"])
            if firma_bytes:
                return firma_bytes
    return None


def doctor_signature_bytes(record):
    firma_b64 = record.get("firma_b64", "")
    if not firma_b64:
        return None
    return decodificar_base64_seguro(firma_b64) or None


def order_attachment_note(record):
    nombre = record.get("adjunto_papel_nombre", "").strip()
    if not nombre:
        return ""
    return f"Orden medica adjunta en sistema: {nombre}"
