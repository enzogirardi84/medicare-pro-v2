from __future__ import annotations

"""Operaciones SQL clínicas: evoluciones, indicaciones, estudios, vitales,
cuidados, consentimientos, pediatría, escalas. Extraído de core/db_sql.py."""
from typing import Any, Dict, List, Optional

import streamlit as st

from core.app_logging import log_event

try:
    from core.database import supabase, _supabase_execute_with_retry
except ImportError:
    supabase = None

    def _supabase_execute_with_retry(op_name, fn, attempts=3, base_delay=0.15):
        for i in range(attempts):
            try:
                return fn()
            except Exception:
                if i == attempts - 1:
                    raise
                delay = base_delay * (2 ** i) + secrets.randbelow(100) / 1000
                time.sleep(delay)
        return fn()


def _ok() -> bool:
    return supabase is not None


def _clear_clinico_cache() -> None:
    _get_evoluciones_by_paciente.clear()
    _get_indicaciones_activas.clear()
    _get_indicaciones_paciente.clear()
    _get_estudios_by_paciente.clear()
    _get_signos_vitales.clear()
    _get_cuidados_enfermeria.clear()
    _get_consentimientos_by_paciente.clear()
    _get_pediatria_by_paciente.clear()
    _get_escalas_by_paciente.clear()


def get_evoluciones_by_paciente(paciente_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    return _get_evoluciones_by_paciente(paciente_id, limit)


@st.cache_data(ttl=90, max_entries=500, show_spinner=False)
def _get_evoluciones_by_paciente(paciente_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        response = _supabase_execute_with_retry(
            "get_evoluciones",
            lambda: supabase.table("evoluciones").select("*").eq("paciente_id", paciente_id).order("created_at", desc=True).limit(limit).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_evoluciones:{type(e).__name__}")
        return []


def insert_evolucion(datos_evolucion: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_evolucion",
            lambda: supabase.table("evoluciones").upsert(datos_evolucion, on_conflict="id").execute(),
        )
        _clear_clinico_cache()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_evolucion:{type(e).__name__}")
        return None


def get_indicaciones_activas(paciente_id: str) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    return _get_indicaciones_activas(paciente_id)


@st.cache_data(ttl=90, max_entries=500, show_spinner=False)
def _get_indicaciones_activas(paciente_id: str) -> List[Dict[str, Any]]:
    try:
        response = _supabase_execute_with_retry(
            "get_indicaciones",
            lambda: supabase.table("indicaciones").select("*").eq("paciente_id", paciente_id).eq("estado", "Activa").order("created_at", desc=True).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_indicaciones:{type(e).__name__}")
        return []


def get_indicaciones_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    return _get_indicaciones_paciente(paciente_id)


@st.cache_data(ttl=90, max_entries=500, show_spinner=False)
def _get_indicaciones_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    try:
        response = _supabase_execute_with_retry(
            "get_indicaciones",
            lambda: supabase.table("indicaciones").select("*").eq("paciente_id", paciente_id).order("fecha_indicacion", desc=True).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_indicaciones:{type(e).__name__}")
        return []


def insert_indicacion(datos_indicacion: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_indicacion",
            lambda: supabase.table("indicaciones").upsert(datos_indicacion, on_conflict="id").execute(),
        )
        _clear_clinico_cache()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_indicacion:{type(e).__name__}")
        return None


def update_estado_indicacion(indicacion_id: str, nuevo_estado: str) -> bool:
    if not _ok():
        return False
    try:
        _supabase_execute_with_retry(
            "update_indicacion",
            lambda: supabase.table("indicaciones").update({"estado": nuevo_estado}).eq("id", indicacion_id).execute(),
        )
        _clear_clinico_cache()
        return True
    except Exception as e:
        log_event("db_sql", f"error_update_indicacion:{type(e).__name__}")
        return False


def get_estudios_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    return _get_estudios_by_paciente(paciente_id)


@st.cache_data(ttl=90, max_entries=500, show_spinner=False)
def _get_estudios_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    try:
        response = _supabase_execute_with_retry(
            "get_estudios",
            lambda: supabase.table("estudios").select("*").eq("paciente_id", paciente_id).order("created_at", desc=True).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_estudios:{type(e).__name__}")
        return []


def insert_estudio(datos_estudio: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_estudio",
            lambda: supabase.table("estudios").upsert(datos_estudio, on_conflict="id").execute(),
        )
        _clear_clinico_cache()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_estudio:{type(e).__name__}")
        return None


def delete_estudio(estudio_id: str) -> bool:
    if not _ok():
        return False
    try:
        _supabase_execute_with_retry(
            "delete_estudio",
            lambda: supabase.table("estudios").delete().eq("id", estudio_id).execute(),
        )
        _clear_clinico_cache()
        return True
    except Exception as e:
        log_event("db_sql", f"error_delete_estudio:{type(e).__name__}")
        return False


def get_signos_vitales(paciente_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    return _get_signos_vitales(paciente_id, limit)


@st.cache_data(ttl=90, max_entries=500, show_spinner=False)
def _get_signos_vitales(paciente_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    try:
        response = _supabase_execute_with_retry(
            "get_vitales",
            lambda: supabase.table("signos_vitales").select("*").eq("paciente_id", paciente_id).order("created_at", desc=True).limit(limit).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_vitales:{type(e).__name__}")
        return []


def insert_signo_vital(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_vitales",
            lambda: supabase.table("signos_vitales").upsert(datos, on_conflict="id").execute(),
        )
        _clear_clinico_cache()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_vitales:{type(e).__name__}")
        return None


def get_cuidados_enfermeria(paciente_id: str, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    return _get_cuidados_enfermeria(paciente_id, fecha_inicio, fecha_fin)


@st.cache_data(ttl=90, max_entries=200, show_spinner=False)
def _get_cuidados_enfermeria(paciente_id: str, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
    try:
        response = _supabase_execute_with_retry(
            "get_cuidados",
            lambda: supabase.table("cuidados_enfermeria").select("*").eq("paciente_id", paciente_id).gte("created_at", fecha_inicio).lte("created_at", fecha_fin).order("created_at", desc=False).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_cuidados:{type(e).__name__}")
        return []


def insert_cuidado_enfermeria(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_cuidado",
            lambda: supabase.table("cuidados_enfermeria").upsert(datos, on_conflict="id").execute(),
        )
        _clear_clinico_cache()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_cuidado:{type(e).__name__}")
        return None


def get_consentimientos_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    return _get_consentimientos_by_paciente(paciente_id)


@st.cache_data(ttl=90, max_entries=500, show_spinner=False)
def _get_consentimientos_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    try:
        response = _supabase_execute_with_retry(
            "get_consentimientos",
            lambda: supabase.table("consentimientos").select("*").eq("paciente_id", paciente_id).order("created_at", desc=True).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_consentimientos:{type(e).__name__}")
        return []


def insert_consentimiento(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_consentimiento",
            lambda: supabase.table("consentimientos").upsert(datos, on_conflict="id").execute(),
        )
        _clear_clinico_cache()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_consentimiento:{type(e).__name__}")
        return None


def get_pediatria_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    return _get_pediatria_by_paciente(paciente_id)


@st.cache_data(ttl=90, max_entries=500, show_spinner=False)
def _get_pediatria_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    try:
        response = _supabase_execute_with_retry(
            "get_pediatria",
            lambda: supabase.table("pediatria").select("*").eq("paciente_id", paciente_id).order("created_at", desc=True).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_pediatria:{type(e).__name__}")
        return []


def insert_pediatria(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_pediatria",
            lambda: supabase.table("pediatria").upsert(datos, on_conflict="id").execute(),
        )
        _clear_clinico_cache()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_pediatria:{type(e).__name__}")
        return None


def get_escalas_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    return _get_escalas_by_paciente(paciente_id)


@st.cache_data(ttl=90, max_entries=500, show_spinner=False)
def _get_escalas_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    try:
        response = _supabase_execute_with_retry(
            "get_escalas",
            lambda: supabase.table("escalas_clinicas").select("*").eq("paciente_id", paciente_id).order("created_at", desc=True).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_escalas:{type(e).__name__}")
        return []


def insert_escala(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_escala",
            lambda: supabase.table("escalas_clinicas").upsert(datos, on_conflict="id").execute(),
        )
        _clear_clinico_cache()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_escala:{type(e).__name__}")
        return None
