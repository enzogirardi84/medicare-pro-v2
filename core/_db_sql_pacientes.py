"""Operaciones SQL sobre pacientes y empresas. Extraído de core/db_sql.py."""
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


def check_supabase_connection() -> bool:
    return supabase is not None


@st.cache_data(ttl=60, show_spinner=False)
def get_pacientes_by_empresa(empresa_id: str, busqueda: str = "", incluir_altas: bool = False) -> List[Dict[str, Any]]:
    """Obtiene la lista de pacientes de una empresa, con paginación/búsqueda directa en SQL."""
    if not check_supabase_connection():
        return []
    query = supabase.table("pacientes").select("*").eq("empresa_id", empresa_id)
    if not incluir_altas:
        query = query.eq("estado", "Activo")
    if busqueda:
        busqueda_limpia = busqueda.strip()
        query = query.or_(f"nombre_completo.ilike.%{busqueda_limpia}%,dni.ilike.%{busqueda_limpia}%")
    query = query.order("updated_at", desc=True).limit(100)
    try:
        response = _supabase_execute_with_retry("get_pacientes", lambda: query.execute())
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_pacientes:{type(e).__name__}")
        return []


@st.cache_data(ttl=120, show_spinner=False)
def get_paciente_by_id(paciente_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene los detalles completos de un paciente específico."""
    if not check_supabase_connection():
        return None
    try:
        response = _supabase_execute_with_retry(
            "get_paciente_id",
            lambda: supabase.table("pacientes").select("*").eq("id", paciente_id).limit(1).execute(),
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_get_paciente_id:{type(e).__name__}")
        return None


@st.cache_data(ttl=3600, show_spinner=False)
def get_empresa_by_nombre(nombre_empresa: str) -> Optional[Dict[str, Any]]:
    """Busca una empresa por nombre exacto."""
    if not check_supabase_connection():
        return None
    try:
        response = _supabase_execute_with_retry(
            "get_empresa_nombre",
            lambda: supabase.table("empresas").select("*").eq("nombre", nombre_empresa).limit(1).execute(),
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_get_empresa_nombre:{type(e).__name__}")
        return None


@st.cache_data(ttl=120, show_spinner=False)
def get_paciente_by_dni_empresa(empresa_id: str, dni: str) -> Optional[Dict[str, Any]]:
    """Busca un paciente por DNI dentro de una empresa."""
    if not check_supabase_connection() or not empresa_id or not dni:
        return None
    try:
        response = _supabase_execute_with_retry(
            "get_paciente_dni_empresa",
            lambda: supabase.table("pacientes").select("*").eq("empresa_id", empresa_id).eq("dni", dni).limit(1).execute(),
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_get_paciente_dni_empresa:{type(e).__name__}")
        return None


def upsert_paciente(datos_paciente: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta o actualiza un paciente."""
    if not check_supabase_connection():
        return None
    try:
        if "id" in datos_paciente:
            from core.utils import ahora
            datos_paciente["updated_at"] = ahora().isoformat()
        response = _supabase_execute_with_retry(
            "upsert_paciente",
            lambda: supabase.table("pacientes").upsert(datos_paciente).execute(),
        )
        get_pacientes_by_empresa.clear()
        get_paciente_by_id.clear()
        get_paciente_by_dni_empresa.clear()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_upsert_paciente:{type(e).__name__}")
        return None


def update_paciente_by_id(paciente_id: str, datos_update: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Actualiza un paciente existente por id."""
    if not check_supabase_connection() or not paciente_id:
        return None
    try:
        payload = dict(datos_update or {})
        if not payload:
            return None
        from core.utils import ahora
        payload["updated_at"] = ahora().isoformat()
        response = _supabase_execute_with_retry(
            "update_paciente",
            lambda: supabase.table("pacientes").update(payload).eq("id", paciente_id).execute(),
        )
        get_pacientes_by_empresa.clear()
        get_paciente_by_id.clear()
        get_paciente_by_dni_empresa.clear()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_update_paciente:{type(e).__name__}")
        return None


def delete_paciente_by_id(paciente_id: str) -> bool:
    """Elimina un paciente por id."""
    if not check_supabase_connection() or not paciente_id:
        return False
    try:
        _supabase_execute_with_retry(
            "delete_paciente",
            lambda: supabase.table("pacientes").delete().eq("id", paciente_id).execute(),
        )
        get_pacientes_by_empresa.clear()
        get_paciente_by_id.clear()
        get_paciente_by_dni_empresa.clear()
        return True
    except Exception as e:
        log_event("db_sql", f"error_delete_paciente:{type(e).__name__}")
        return False
