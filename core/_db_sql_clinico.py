"""Operaciones SQL clínicas: evoluciones, indicaciones, estudios, vitales,
cuidados, consentimientos, pediatría, escalas. Extraído de core/db_sql.py."""
import time
from typing import Any, Dict, List, Optional

import streamlit as st

from core.app_logging import log_event

try:
    from core.database import supabase, _supabase_execute_with_retry
except ImportError:
    supabase = None

    def _supabase_execute_with_retry(op_name, fn, attempts=3, base_delay=0.35):
        for _ in range(attempts):
            try:
                return fn()
            except Exception:
                time.sleep(base_delay)
        return fn()


def _ok() -> bool:
    return supabase is not None


def _invalidate_cache_prefix(prefix: str) -> None:
    """Elimina del session_state todas las claves de cache que empiecen con prefix."""
    for k in list(st.session_state.keys()):
        if k.startswith(prefix):
            st.session_state.pop(k, None)


def get_evoluciones_by_paciente(paciente_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Obtiene el historial de evoluciones de un paciente. Cache manual a prueba de fallos."""
    cache_key = f"_sql_clin_evol_{paciente_id}_{limit}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 90:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_evoluciones",
            lambda: supabase.table("evoluciones").select("*, usuarios(nombre, matricula)").eq("paciente_id", paciente_id).order("fecha_registro", desc=True).limit(limit).execute(),
        )
        data = response.data if response and response.data else []
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_evoluciones:{type(e).__name__}")
        return []


def insert_evolucion(datos_evolucion: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta una nueva evolución de forma atómica."""
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_evolucion",
            lambda: supabase.table("evoluciones").insert(datos_evolucion).execute(),
        )
        _invalidate_cache_prefix(f"_sql_clin_evol_{datos_evolucion.get('paciente_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_evolucion:{type(e).__name__}")
        return None


def get_indicaciones_activas(paciente_id: str) -> List[Dict[str, Any]]:
    """Obtiene las indicaciones médicas activas para un paciente. Cache manual a prueba de fallos."""
    cache_key = f"_sql_clin_ind_{paciente_id}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 90:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_indicaciones",
            lambda: supabase.table("indicaciones").select("*").eq("paciente_id", paciente_id).eq("estado", "Activa").order("fecha_indicacion", desc=True).execute(),
        )
        data = response.data if response and response.data else []
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_indicaciones:{type(e).__name__}")
        return []


def insert_indicacion(datos_indicacion: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta una nueva indicación médica."""
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_indicacion",
            lambda: supabase.table("indicaciones").insert(datos_indicacion).execute(),
        )
        _invalidate_cache_prefix(f"_sql_clin_ind_{datos_indicacion.get('paciente_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_indicacion:{type(e).__name__}")
        return None


def update_estado_indicacion(indicacion_id: str, nuevo_estado: str) -> bool:
    """Suspende o modifica el estado de una indicación."""
    if not _ok():
        return False
    try:
        _supabase_execute_with_retry(
            "update_indicacion",
            lambda: supabase.table("indicaciones").update({"estado": nuevo_estado}).eq("id", indicacion_id).execute(),
        )
        _invalidate_cache_prefix("_sql_clin_ind_")
        return True
    except Exception as e:
        log_event("db_sql", f"error_update_indicacion:{type(e).__name__}")
        return False


def get_estudios_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    """Obtiene los estudios médicos de un paciente. Cache manual a prueba de fallos."""
    cache_key = f"_sql_clin_est_{paciente_id}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 90:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_estudios",
            lambda: supabase.table("estudios").select("*").eq("paciente_id", paciente_id).order("fecha_realizacion", desc=True).execute(),
        )
        data = response.data if response and response.data else []
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_estudios:{type(e).__name__}")
        return []


def insert_estudio(datos_estudio: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta un nuevo estudio médico."""
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_estudio",
            lambda: supabase.table("estudios").insert(datos_estudio).execute(),
        )
        _invalidate_cache_prefix(f"_sql_clin_est_{datos_estudio.get('paciente_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_estudio:{type(e).__name__}")
        return None


def delete_estudio(estudio_id: str) -> bool:
    """Elimina un estudio médico."""
    if not _ok():
        return False
    try:
        _supabase_execute_with_retry(
            "delete_estudio",
            lambda: supabase.table("estudios").delete().eq("id", estudio_id).execute(),
        )
        _invalidate_cache_prefix("_sql_clin_est_")
        return True
    except Exception as e:
        log_event("db_sql", f"error_delete_estudio:{type(e).__name__}")
        return False


def get_signos_vitales(paciente_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Obtiene signos vitales de un paciente. Cache manual a prueba de fallos."""
    cache_key = f"_sql_clin_vit_{paciente_id}_{limit}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 90:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_vitales",
            lambda: supabase.table("signos_vitales").select("*, usuarios(nombre)").eq("paciente_id", paciente_id).order("fecha_registro", desc=True).limit(limit).execute(),
        )
        data = response.data if response and response.data else []
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_vitales:{type(e).__name__}")
        return []


def insert_signo_vital(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_vitales",
            lambda: supabase.table("signos_vitales").insert(datos).execute(),
        )
        _invalidate_cache_prefix(f"_sql_clin_vit_{datos.get('paciente_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_vitales:{type(e).__name__}")
        return None


def get_cuidados_enfermeria(paciente_id: str, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
    """Obtiene cuidados de enfermería. Cache manual a prueba de fallos."""
    cache_key = f"_sql_clin_cuid_{paciente_id}_{fecha_inicio}_{fecha_fin}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 90:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_cuidados",
            lambda: supabase.table("cuidados_enfermeria").select("*, usuarios(nombre)").eq("paciente_id", paciente_id).gte("fecha_registro", fecha_inicio).lte("fecha_registro", fecha_fin).order("fecha_registro", desc=False).execute(),
        )
        data = response.data if response and response.data else []
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_cuidados:{type(e).__name__}")
        return []


def insert_cuidado_enfermeria(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_cuidado",
            lambda: supabase.table("cuidados_enfermeria").insert(datos).execute(),
        )
        _invalidate_cache_prefix(f"_sql_clin_cuid_{datos.get('paciente_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_cuidado:{type(e).__name__}")
        return None


def get_consentimientos_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    """Obtiene consentimientos de un paciente. Cache manual a prueba de fallos."""
    cache_key = f"_sql_clin_cons_{paciente_id}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 90:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_consentimientos",
            lambda: supabase.table("consentimientos").select("*, usuarios(nombre)").eq("paciente_id", paciente_id).order("fecha_firma", desc=True).execute(),
        )
        data = response.data if response and response.data else []
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_consentimientos:{type(e).__name__}")
        return []


def insert_consentimiento(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_consentimiento",
            lambda: supabase.table("consentimientos").insert(datos).execute(),
        )
        _invalidate_cache_prefix(f"_sql_clin_cons_{datos.get('paciente_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_consentimiento:{type(e).__name__}")
        return None


def get_pediatria_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    """Obtiene registros pediátricos. Cache manual a prueba de fallos."""
    cache_key = f"_sql_clin_ped_{paciente_id}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 90:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_pediatria",
            lambda: supabase.table("pediatria").select("*, usuarios(nombre)").eq("paciente_id", paciente_id).order("fecha_registro", desc=True).execute(),
        )
        data = response.data if response and response.data else []
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_pediatria:{type(e).__name__}")
        return []


def insert_pediatria(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_pediatria",
            lambda: supabase.table("pediatria").insert(datos).execute(),
        )
        _invalidate_cache_prefix(f"_sql_clin_ped_{datos.get('paciente_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_pediatria:{type(e).__name__}")
        return None


def get_escalas_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    """Obtiene escalas clínicas. Cache manual a prueba de fallos."""
    cache_key = f"_sql_clin_esc_{paciente_id}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 90:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_escalas",
            lambda: supabase.table("escalas_clinicas").select("*, usuarios(nombre)").eq("paciente_id", paciente_id).order("fecha_registro", desc=True).execute(),
        )
        data = response.data if response and response.data else []
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_escalas:{type(e).__name__}")
        return []


def insert_escala(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_escala",
            lambda: supabase.table("escalas_clinicas").insert(datos).execute(),
        )
        _invalidate_cache_prefix(f"_sql_clin_esc_{datos.get('paciente_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_escala:{type(e).__name__}")
        return None
