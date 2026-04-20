"""Helpers de agenda y datos para el módulo Visitas.

Extraído de views/visitas.py.
"""
from datetime import datetime, timedelta

import streamlit as st

from core.utils import (
    ahora,
    calcular_estado_agenda,
    filtrar_registros_empresa,
    parse_agenda_datetime,
)


def _agenda_empresa(mi_empresa, rol):
    from core.db_sql import get_turnos_by_empresa
    from core.nextgen_sync import _obtener_uuid_empresa

    agenda_sql = []
    uso_sql = False

    try:
        empresa_id = _obtener_uuid_empresa(mi_empresa)
        if empresa_id:
            fecha_inicio = (ahora() - timedelta(days=30)).isoformat()
            fecha_fin = (ahora() + timedelta(days=60)).isoformat()
            turnos_sql = get_turnos_by_empresa(empresa_id, fecha_inicio, fecha_fin)
            uso_sql = True
            for t in turnos_sql:
                pac = t.get("pacientes") or {}
                paciente_nombre = pac.get("nombre_completo", "")
                paciente_dni = pac.get("dni", "")
                paciente_visual = f"{paciente_nombre} - {paciente_dni}" if paciente_nombre else ""
                prof_nombre = (t.get("usuarios") or {}).get("nombre", "")
                fecha_hora_raw = t.get("fecha_hora_programada", "")
                fecha_str = hora_str = ""
                if fecha_hora_raw:
                    parts = fecha_hora_raw[:16].split("T")
                    if len(parts) == 2:
                        d_parts = parts[0].split("-")
                        if len(d_parts) == 3:
                            fecha_str = f"{d_parts[2]}/{d_parts[1]}/{d_parts[0]}"
                        hora_str = parts[1]
                agenda_sql.append({
                    "id_sql": t.get("id"),
                    "paciente": paciente_visual,
                    "profesional": prof_nombre,
                    "fecha": fecha_str,
                    "fecha_programada": fecha_str,
                    "fecha_hora_programada": fecha_hora_raw.replace("T", " ")[:19] if fecha_hora_raw else "",
                    "hora": hora_str,
                    "empresa": mi_empresa,
                    "estado": t.get("estado", "Pendiente"),
                    "motivo": t.get("motivo", ""),
                    "notas": t.get("notas", ""),
                })
    except Exception as e:
        from core.app_logging import log_event
        log_event("visitas_sql", f"error_lectura_agenda:{type(e).__name__}")

    if uso_sql:
        return agenda_sql
    return filtrar_registros_empresa(st.session_state.get("agenda_db", []), mi_empresa, rol)


def _agenda_paciente(mi_empresa, paciente_sel, rol):
    return [a for a in _agenda_empresa(mi_empresa, rol) if a.get("paciente") == paciente_sel]


def _enriquecer_agenda(items):
    ahora_local = ahora().replace(tzinfo=None)
    enriquecida = []
    for idx, item in enumerate(items):
        registro = dict(item)
        dt = parse_agenda_datetime(item)
        registro["_id_local"] = idx
        registro["_fecha_dt"] = dt
        registro["estado_calc"] = calcular_estado_agenda(item, now=ahora_local)
        enriquecida.append(registro)
    return enriquecida


def _resumen_agenda(items):
    if not items:
        return {"pendientes": 0, "vencidas": 0, "proximas": 0, "profesionales": 0}
    ahora_local = ahora().replace(tzinfo=None)
    proximas_limite = ahora_local + timedelta(hours=48)
    return {
        "pendientes": sum(1 for x in items if x["estado_calc"] in {"Pendiente", "En curso"}),
        "vencidas": sum(1 for x in items if x["estado_calc"] == "Vencida"),
        "proximas": sum(1 for x in items if x["_fecha_dt"] != datetime.min and ahora_local <= x["_fecha_dt"] <= proximas_limite),
        "profesionales": len({x.get("profesional", "Sin profesional") for x in items}),
    }


def _zona_corta(direccion):
    texto = str(direccion or "").strip()
    if not texto or texto == "No registrada":
        return "Zona sin definir"
    return texto.split(",")[0].strip()[:60]
