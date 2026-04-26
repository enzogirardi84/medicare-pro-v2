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
    ok = supabase is not None
    if not ok and not st.session_state.get("_db_conn_error_shown"):
        st.session_state["_db_conn_error_shown"] = True
        print("Error Supabase en check_supabase_connection: cliente no inicializado. Datos desde cache local.")
    return ok


def _invalidate_cache_prefix(prefix: str) -> None:
    """Elimina del session_state todas las claves de cache que empiecen con prefix."""
    for k in list(st.session_state.keys()):
        if k.startswith(prefix):
            st.session_state.pop(k, None)


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


def get_pacientes_by_empresa(empresa_id: str, busqueda: str = "", incluir_altas: bool = False) -> List[Dict[str, Any]]:
    """Obtiene pacientes. Cache manual a prueba de fallos."""
    cache_key = f"_sql_pac_list_{empresa_id}_{hash(busqueda)}_{int(incluir_altas)}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 300:
            return cached["data"]
        st.session_state.pop(cache_key, None)
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
            data = getattr(response, "data", None) or []
            st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
            return data
        except Exception as e:
            last_error = e
    if last_error is not None:
        log_event("db_sql", f"error_get_pacientes:{type(last_error).__name__}:{last_error}")
        print(f"Error Supabase en get_pacientes_by_empresa: {str(last_error)}")
    return []


def get_pacientes_globales(limit: int = 1000) -> List[Dict[str, Any]]:
    """Lista global para administradores. Cache manual a prueba de fallos."""
    cache_key = f"_sql_pac_global_{limit}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 300:
            return cached["data"]
        st.session_state.pop(cache_key, None)
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
            data = getattr(response, "data", None) or []
            st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
            return data
        except Exception as e:
            last_error = e
    if last_error is not None:
        log_event("db_sql", f"error_get_pacientes_globales:{type(last_error).__name__}:{last_error}")
        print(f"Error Supabase en get_pacientes_globales: {str(last_error)}")
    return []


def get_paciente_by_id(paciente_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene detalles completos de un paciente. Cache manual a prueba de fallos."""
    cache_key = f"_sql_pac_id_{paciente_id}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 120:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not check_supabase_connection():
        return None
    try:
        response = _supabase_execute_with_retry(
            "get_paciente_id",
            lambda: supabase.table("pacientes").select("*").eq("id", paciente_id).limit(1).execute(),
        )
        data = (getattr(response, "data", None) or [None])[0]
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_paciente_id:{type(e).__name__}:{e}")
        print(f"Error Supabase en get_paciente_by_id: {str(e)}")
        return None


def get_empresa_by_nombre(nombre_empresa: str) -> Optional[Dict[str, Any]]:
    """Busca una empresa por nombre exacto. Cache manual a prueba de fallos."""
    empresa_fallback = empresa_record_configurado(nombre_empresa)
    cache_key = f"_sql_pac_emp_n_{nombre_empresa}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 3600:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not check_supabase_connection():
        return empresa_fallback
    try:
        response = _supabase_execute_with_retry(
            "get_empresa_nombre",
            lambda: supabase.table("empresas").select(EMPRESAS_MIN_COLUMNS).eq("nombre", nombre_empresa).limit(1).execute(),
        )
        data = (getattr(response, "data", None) or [empresa_fallback])[0]
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_empresa_nombre:{type(e).__name__}:{e}")
        print(f"Error detallado Supabase get_empresa_by_nombre: {str(e)}")
        st.warning("Error al cargar datos de la empresa desde el servidor. Se usarán datos locales.")
        return empresa_fallback


def get_paciente_by_dni_empresa(empresa_id: str, dni: str) -> Optional[Dict[str, Any]]:
    """Busca un paciente por DNI dentro de una empresa. Cache manual a prueba de fallos."""
    cache_key = f"_sql_pac_dni_{empresa_id}_{dni}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 120:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not check_supabase_connection() or not empresa_id or not dni:
        return None
    try:
        response = _supabase_execute_with_retry(
            "get_paciente_dni_empresa",
            lambda: supabase.table("pacientes").select("*").eq("empresa_id", empresa_id).eq("dni", dni).limit(1).execute(),
        )
        data = (getattr(response, "data", None) or [None])[0]
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_paciente_dni_empresa:{type(e).__name__}:{e}")
        print(f"Error Supabase en get_paciente_by_dni_empresa: {str(e)}")
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
        _invalidate_cache_prefix("_sql_pac_")
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
        _invalidate_cache_prefix("_sql_pac_")
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
        _invalidate_cache_prefix("_sql_pac_")
        return True
    except Exception as e:
        log_event("db_sql", f"error_delete_paciente:{type(e).__name__}")
        return False
