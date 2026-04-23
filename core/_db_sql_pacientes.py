"""Operaciones SQL sobre pacientes y empresas. Extraido de core/db_sql.py."""

import time
from typing import Any, Dict, List, Optional

import streamlit as st

from core.app_logging import log_event
from core.empresa_config import empresa_record_configurado

PACIENTES_LIST_COLUMNS = (
    "id,empresa_id,nombre_completo,dni,fecha_nacimiento,sexo,estado,"
    "obra_social,telefono,direccion,alergias,patologias,updated_at,created_at"
)
EMPRESAS_MIN_COLUMNS = "id,nombre"

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


def nombre_paciente_sql(row: Dict[str, Any]) -> str:
    """Normaliza nombres entre esquemas nuevos y legados."""
    if not isinstance(row, dict):
        return ""
    nombre_completo = str(row.get("nombre_completo", "") or "").strip()
    if nombre_completo:
        return nombre_completo
    partes = [
        str(row.get("nombre", "") or "").strip(),
        str(row.get("apellido", "") or "").strip(),
    ]
    return " ".join(p for p in partes if p).strip()


def _build_pacientes_query(
    empresa_id: str,
    busqueda: str,
    incluir_altas: bool,
    columns: str,
    legacy: bool,
    order_by: str | None,
    limit: int = 100,
):
    query = supabase.table("pacientes").select(columns).eq("empresa_id", empresa_id)
    if not incluir_altas:
        query = query.eq("estado", "Activo")
    if busqueda:
        busqueda_limpia = busqueda.strip()
        if legacy:
            query = query.or_(
                f"nombre.ilike.%{busqueda_limpia}%,apellido.ilike.%{busqueda_limpia}%,dni.ilike.%{busqueda_limpia}%"
            )
        else:
            query = query.or_(f"nombre_completo.ilike.%{busqueda_limpia}%,dni.ilike.%{busqueda_limpia}%")
    if order_by:
        query = query.order(order_by, desc=True)
    return query.limit(limit)


@st.cache_data(ttl=30, max_entries=10, show_spinner=False)
def get_pacientes_by_empresa(empresa_id: str, busqueda: str = "", incluir_altas: bool = False) -> List[Dict[str, Any]]:
    """Obtiene pacientes con consulta liviana y fallback para esquemas legados."""
    if not check_supabase_connection():
        return []
    attempts = (
        (PACIENTES_LIST_COLUMNS, False, "updated_at"),
        ("*", True, "created_at"),
        ("*", True, None),
    )
    last_error = None
    for columns, legacy, order_by in attempts:
        try:
            response = _supabase_execute_with_retry(
                "get_pacientes",
                lambda c=columns, l=legacy, o=order_by: _build_pacientes_query(
                    empresa_id, busqueda, incluir_altas, c, l, o
                ).execute(),
            )
            return response.data if response and response.data else []
        except Exception as e:
            last_error = e
    if last_error is not None:
        log_event("db_sql", f"error_get_pacientes:{type(last_error).__name__}")
    return []


@st.cache_data(ttl=60, show_spinner=False)
def get_pacientes_globales(limit: int = 1000) -> List[Dict[str, Any]]:
    """Lista global para administradores: proyecta columnas utiles y limita payload."""
    if not check_supabase_connection():
        return []
    limit = max(1, min(int(limit or 1000), 2000))
    attempts = (
        (PACIENTES_LIST_COLUMNS, "updated_at"),
        ("*", "created_at"),
        ("*", None),
    )
    last_error = None
    for columns, order_by in attempts:
        try:
            def _query(c=columns, o=order_by):
                q = supabase.table("pacientes").select(c)
                if o:
                    q = q.order(o, desc=True)
                return q.limit(limit).execute()

            response = _supabase_execute_with_retry("get_pacientes_globales", _query)
            return response.data if response and response.data else []
        except Exception as e:
            last_error = e
    if last_error is not None:
        log_event("db_sql", f"error_get_pacientes_globales:{type(last_error).__name__}")
    return []


@st.cache_data(ttl=120, show_spinner=False)
def get_paciente_by_id(paciente_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene los detalles completos de un paciente especifico."""
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
    empresa_fallback = empresa_record_configurado(nombre_empresa)
    if not check_supabase_connection():
        return empresa_fallback
    try:
        response = _supabase_execute_with_retry(
            "get_empresa_nombre",
            lambda: supabase.table("empresas").select(EMPRESAS_MIN_COLUMNS).eq("nombre", nombre_empresa).limit(1).execute(),
        )
        return response.data[0] if response and response.data else empresa_fallback
    except Exception as e:
        log_event("db_sql", f"error_get_empresa_nombre:{type(e).__name__}")
        return empresa_fallback


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


def _upsert_paciente_payload(payload: Dict[str, Any]):
    return _supabase_execute_with_retry(
        "upsert_paciente",
        lambda: supabase.table("pacientes").upsert(payload).execute(),
    )


def upsert_paciente(datos_paciente: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta o actualiza un paciente."""
    if not check_supabase_connection():
        return None
    payload = dict(datos_paciente or {})
    try:
        if "id" in payload:
            from core.utils import ahora

            payload["updated_at"] = ahora().isoformat()
        try:
            response = _upsert_paciente_payload(payload)
        except Exception:
            if "updated_at" not in payload:
                raise
            payload.pop("updated_at", None)
            response = _upsert_paciente_payload(payload)
        get_pacientes_by_empresa.clear()
        get_pacientes_globales.clear()
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
        try:
            response = _supabase_execute_with_retry(
                "update_paciente",
                lambda: supabase.table("pacientes").update(payload).eq("id", paciente_id).execute(),
            )
        except Exception:
            payload.pop("updated_at", None)
            response = _supabase_execute_with_retry(
                "update_paciente",
                lambda: supabase.table("pacientes").update(payload).eq("id", paciente_id).execute(),
            )
        get_pacientes_by_empresa.clear()
        get_pacientes_globales.clear()
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
        get_pacientes_globales.clear()
        get_paciente_by_id.clear()
        get_paciente_by_dni_empresa.clear()
        return True
    except Exception as e:
        log_event("db_sql", f"error_delete_paciente:{type(e).__name__}")
        return False
