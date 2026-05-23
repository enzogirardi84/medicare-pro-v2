"""Helpers reutilizables del modulo APS. Extraido de views/dispensario_aps.py"""

from __future__ import annotations

from datetime import date, datetime

import streamlit as st

from core.app_logging import log_event
from core.database import guardar_datos, guardar_json_db


def get_paciente_id_visual(paciente_sel):
    return str(paciente_sel or "").strip()


def input_paciente_volatil(paciente_sel, key_prefix="aps_vol"):
    if paciente_sel:
        st.success(f"Paciente seleccionado: **{paciente_sel}**")
        return get_paciente_id_visual(paciente_sel), None
    st.info("No hay paciente seleccionado. Complete los datos del paciente voluntario:")
    col1, col2, col3 = st.columns(3)
    with col1: apellido = st.text_input("Apellido", key=f"{key_prefix}_apellido")
    with col2: nombre = st.text_input("Nombre", key=f"{key_prefix}_nombre")
    with col3: dni = st.text_input("DNI", key=f"{key_prefix}_dni")
    parts = [p for p in [apellido, nombre] if p and p.strip()]
    paciente_id = f"{' '.join(parts)} - {dni}".strip() if (parts or (dni and dni.strip())) else ""
    return paciente_id, {"apellido": apellido, "nombre": nombre, "dni": dni}


def header_paciente(paciente_sel, user):
    from core.utils import mapa_detalles_pacientes
    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    with st.container(border=True):
        col1, col2 = st.columns(2)
        col1.metric("Paciente", paciente_sel or "-")
        col1.metric("DNI", detalles.get("dni", "S/D"))
        col2.metric("Empresa / Barrio", detalles.get("empresa", "S/D"))
        col2.metric("Estado", detalles.get("estado", "Activo"))


def guardar_con_feedback(clave_db, payload, max_items=500):
    try:
        guardar_json_db(clave_db, payload, spinner=True, max_items=max_items)
        st.toast("Guardado correctamente", icon="✅")
        return True
    except Exception as e:
        log_event("dispensario", f"error al guardar: {e}")
        st.error(f"Error al guardar: {e}")
        return False


def guardar_directo():
    try:
        guardar_datos(spinner=True)
        st.toast("Guardado correctamente", icon="✅")
        return True
    except Exception as e:
        log_event("dispensario", f"error al guardar: {e}")
        st.error(f"Error al guardar: {e}")
        return False


def buscar_pacientes_por_texto(texto):
    texto = str(texto or "").strip().lower()
    if not texto:
        return []
    pacientes = st.session_state.get("pacientes_db", [])
    return [p for p in pacientes if isinstance(p, dict) and (texto in str(p.get("nombre", "")).lower() or texto in str(p.get("dni", "")).lower())]


def calcular_edad(fecha_nacimiento_str):
    try:
        if isinstance(fecha_nacimiento_str, str) and fecha_nacimiento_str:
            fn = datetime.fromisoformat(fecha_nacimiento_str.replace("Z", "+00:00")).date()
        elif isinstance(fecha_nacimiento_str, date):
            fn = fecha_nacimiento_str
        else:
            return None
        hoy = date.today()
        return hoy.year - fn.year - ((hoy.month, hoy.day) < (fn.month, fn.day))
    except Exception:
        return None


def ya_entrego_mes(paciente_id, tipo_entrega, entregas_db):
    hoy = date.today()
    inicio_mes = hoy.replace(day=1)
    for e in entregas_db:
        if not isinstance(e, dict) or e.get("paciente_id") != paciente_id or e.get("tipo_entrega") != tipo_entrega:
            continue
        try:
            fecha = datetime.fromisoformat(str(e.get("fecha_entrega", ""))[:10]).date()
            if inicio_mes <= fecha <= hoy:
                return True
        except Exception:
            continue
    return False


def calcular_edad_gestacional(fum_str):
    try:
        fum = datetime.fromisoformat(str(fum_str)).date()
        return max(0, (date.today() - fum).days // 7)
    except Exception:
        return None


def paciente_info_para_selector(p):
    return f"{p.get('nombre', 'S/N')} — DNI {p.get('dni', 'S/D')}"


def metricas_aps_del_dia():
    hoy_iso = date.today().isoformat()
    atenciones = st.session_state.get("atenciones_aps_db", [])
    entregas = st.session_state.get("entregas_aps_db", [])
    epi = st.session_state.get("epidemiologia_aps_db", [])
    visitas = st.session_state.get("visitas_domiciliarias_aps_db", [])
    filtro_at = [a for a in atenciones if isinstance(a, dict) and str(a.get("fecha_atencion", ""))[:10] == hoy_iso]
    filtro_ent = [e for e in entregas if isinstance(e, dict) and str(e.get("fecha_entrega", ""))[:10] == hoy_iso]
    filtro_epi = [e for e in epi if isinstance(e, dict) and str(e.get("fecha_registro", ""))[:10] == hoy_iso]
    filtro_vis = [v for v in visitas if isinstance(v, dict) and str(v.get("fecha_visita", ""))[:10] == hoy_iso]
    return {
        "atenciones_hoy": len(filtro_at), "entregas_hoy": len(filtro_ent),
        "epidemiologia_hoy": len(filtro_epi), "visitas_hoy": len(filtro_vis),
        "total_atenciones": len(atenciones), "total_entregas": len(entregas),
        "total_epidemiologia": len(epi), "total_visitas": len(visitas),
    }
