from __future__ import annotations

"""Operaciones SQL operativas: emergencias, auditoría, turnos, administraciones MAR,


inventario, facturación, balance, checkins. Extraído de core/db_sql.py."""
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


_MAX_CACHE_ENTRIES = 50


def _evict_sql_cache() -> None:
    _cache_keys = [k for k in st.session_state.keys() if k.startswith("_sql_op_")]
    if len(_cache_keys) > _MAX_CACHE_ENTRIES:
        _cache_keys.sort(key=lambda k: st.session_state.get(k, {}).get("ts", 0))
        for _old_key in _cache_keys[:len(_cache_keys) - _MAX_CACHE_ENTRIES]:
            st.session_state.pop(_old_key, None)


def insert_auditoria(datos: Dict[str, Any]) -> None:
    """Inserta un log de auditoría de forma silenciosa."""
    if not _ok():
        return
    try:
        _supabase_execute_with_retry(
            "insert_auditoria",
            lambda: supabase.table("auditoria_legal").upsert(datos, on_conflict="id").execute(),
        )
    except Exception as e:
        log_event("db_sql", f"error_insert_auditoria:{type(e).__name__}")


@st.cache_data(ttl=120, show_spinner=False)
def get_auditoria_by_empresa(empresa_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
    """Obtiene auditoría de empresa. Cache @st.cache_data (120s)."""
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_auditoria",
            lambda: supabase.table("auditoria_legal").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).limit(limit).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_auditoria:{type(e).__name__}")
        return []


@st.cache_data(ttl=60, show_spinner=False)
def get_turnos_by_empresa(empresa_id: str, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
    """Obtiene los turnos de una empresa. Cache @st.cache_data (60s)."""
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_turnos",
            lambda: supabase.table("turnos").select("*").eq("empresa_id", empresa_id).gte("created_at", fecha_inicio).lte("created_at", fecha_fin).order("created_at", desc=False).execute(),
        )
        return getattr(response, "data", None) or []
    except Exception as e:
        log_event("db_sql", f"error_get_turnos:{type(e).__name__}")
        log_event("db_sql", f"error:detallado Supabase get_turnos: {str(e)}")
        return []


def insert_turno(datos_turno: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta un nuevo turno en la agenda."""
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_turno",
            lambda: supabase.table("turnos").upsert(datos_turno, on_conflict="id").execute(),
        )
        _invalidate_cache_prefix(f"_sql_op_turn_{datos_turno.get('empresa_id', '')}")
        try:
            get_turnos_by_empresa.clear()
        except Exception as _e_turn_cache:
            log_event("db_sql", f"cache_clear_error:{type(_e_turn_cache).__name__}:{_e_turn_cache}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_turno:{type(e).__name__}")
        return None


def update_estado_turno(turno_id: str, nuevo_estado: str) -> bool:
    """Actualiza el estado de un turno."""
    if not _ok():
        return False
    try:
        _supabase_execute_with_retry(
            "update_turno",
            lambda: supabase.table("turnos").update({"estado": nuevo_estado}).eq("id", turno_id).execute(),
        )
        _invalidate_cache_prefix("_sql_op_turn_")
        return True
    except Exception as e:
        log_event("db_sql", f"error_update_turno:{type(e).__name__}")
        return False


@st.cache_data(ttl=120, show_spinner=False)
def get_administraciones_dia(paciente_id: str, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
    """Obtiene registros MAR. Cache @st.cache_data (120s)."""
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_administraciones",
            lambda: supabase.table("administracion_med").select("*").eq("paciente_id", paciente_id).gte("created_at", fecha_inicio).lte("created_at", fecha_fin).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_administraciones:{type(e).__name__}")
        return []


@st.cache_data(ttl=120, show_spinner=False)
def get_administraciones_by_fecha(paciente_id: str, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
    """Obtiene registros MAR por fecha_registro. Cache @st.cache_data (120s)."""
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_administraciones",
            lambda: supabase.table("administracion_med").select("*").eq("paciente_id", paciente_id).gte("fecha_registro", fecha_inicio).lte("fecha_registro", fecha_fin).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_administraciones:{type(e).__name__}")
        return []


def insert_administracion(datos_admin: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Registra que una dosis fue dada o no dada (atómico)."""
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_administracion",
            lambda: supabase.table("administracion_med").upsert(datos_admin, on_conflict="id").execute(),
        )
        _invalidate_cache_prefix(f"_sql_op_adm_{datos_admin.get('paciente_id', '')}")
        get_administraciones_by_fecha.clear()
        get_administraciones_dia.clear()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_administracion:{type(e).__name__}")
        return None


@st.cache_data(ttl=120, show_spinner=False)
def get_emergencias_by_paciente(paciente_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Obtiene emergencias de un paciente. Cache @st.cache_data (120s)."""
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_emergencias_paciente",
            lambda: supabase.table("emergencias").select("*").eq("paciente_id", paciente_id).order("created_at", desc=True).limit(limit).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_emergencias_paciente:{type(e).__name__}")
        return []


@st.cache_data(ttl=120, show_spinner=False)
def get_emergencias_by_empresa(empresa_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    """Obtiene emergencias de empresa. Cache @st.cache_data (120s)."""
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_emergencias",
            lambda: supabase.table("emergencias").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).limit(limit).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_emergencias:{type(e).__name__}")
        return []


def insert_emergencia(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_emergencia",
            lambda: supabase.table("emergencias").upsert(datos, on_conflict="id").execute(),
        )
        _invalidate_cache_prefix(f"_sql_op_emerg_e_{datos.get('empresa_id', '')}")
        _invalidate_cache_prefix(f"_sql_op_emerg_p_{datos.get('paciente_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_emergencia:{type(e).__name__}")
        return None


def update_estado_emergencia(emergencia_id: str, nuevo_estado: str, resolucion: str = "") -> bool:
    if not _ok():
        return False
    try:
        datos_update = {"estado": nuevo_estado}
        if resolucion:
            datos_update["resolucion"] = resolucion
        _supabase_execute_with_retry(
            "update_emergencia",
            lambda: supabase.table("emergencias").update(datos_update).eq("id", emergencia_id).execute(),
        )
        _invalidate_cache_prefix("_sql_op_emerg_e_")
        _invalidate_cache_prefix("_sql_op_emerg_p_")
        return True
    except Exception as e:
        log_event("db_sql", f"error_update_emergencia:{type(e).__name__}")
        return False


@st.cache_data(ttl=120, show_spinner=False)
def get_inventario_by_empresa(empresa_id: str) -> List[Dict[str, Any]]:
    """Obtiene inventario de empresa. Cache @st.cache_data (120s)."""
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_inventario",
            lambda: supabase.table("inventario").select("*").eq("empresa_id", empresa_id).order("nombre").execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_inventario:{type(e).__name__}")
        return []


def insert_inventario(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_inventario",
            lambda: supabase.table("inventario").upsert(datos, on_conflict="id").execute(),
        )
        _invalidate_cache_prefix(f"_sql_op_inv_{datos.get('empresa_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_inventario:{type(e).__name__}")
        return None


@st.cache_data(ttl=120, show_spinner=False)
def get_facturacion_by_empresa(empresa_id: str) -> List[Dict[str, Any]]:
    """Obtiene facturación de empresa. Cache @st.cache_data (120s)."""
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_facturacion",
            lambda: supabase.table("facturacion").select("*").eq("empresa_id", empresa_id).order("fecha_emision", desc=True).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_facturacion:{type(e).__name__}")
        return []


def insert_facturacion(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_facturacion",
            lambda: supabase.table("facturacion").upsert(datos, on_conflict="id").execute(),
        )
        _invalidate_cache_prefix(f"_sql_op_fact_{datos.get('empresa_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_facturacion:{type(e).__name__}")
        return None


@st.cache_data(ttl=120, show_spinner=False)
def get_balance_by_empresa(empresa_id: str) -> List[Dict[str, Any]]:
    """Obtiene balance de empresa. Cache @st.cache_data (120s)."""
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_balance",
            lambda: supabase.table("balance").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_balance:{type(e).__name__}")
        return []


def insert_balance(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_balance",
            lambda: supabase.table("balance").upsert(datos, on_conflict="id").execute(),
        )
        _invalidate_cache_prefix(f"_sql_op_bal_{datos.get('empresa_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_balance:{type(e).__name__}")
        return None


@st.cache_data(ttl=60, show_spinner=False)
def get_checkins_by_empresa(empresa_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    """Obtiene checkins de empresa. Cache @st.cache_data (60s)."""
    if not _ok():
        return []
    try:
        select_expr = "*, pacientes:paciente_id(nombre_completo)"
        response = _supabase_execute_with_retry(
            "get_checkins",
            lambda: supabase.table("checkin_asistencia").select(select_expr).eq("empresa_id", empresa_id).order("fecha_hora", desc=True).limit(limit).execute(),
        )
        return getattr(response, "data", None) or []
    except Exception as e:
        log_event("db_sql", f"error_get_checkins:{type(e).__name__}")
        try:
            select_expr = "*"
            response2 = _supabase_execute_with_retry(
                "get_checkins_fallback",
                lambda: supabase.table("checkin_asistencia").select(select_expr).eq("empresa_id", empresa_id).order("fecha_hora", desc=True).limit(limit).execute(),
                attempts=1,
            )
            return getattr(response2, "data", None) or []
        except Exception as e2:
            log_event("db_sql", f"error_get_checkins_fallback:{type(e2).__name__}")
            return []


def get_inventario_item_by_name(empresa_id: str, nombre_item: str) -> Optional[Dict[str, Any]]:
    """Busca un item de inventario por nombre exacto para una empresa."""
    if not _ok() or not nombre_item:
        return None
    try:
        response = _supabase_execute_with_retry(
            "get_inventario_item",
            lambda: supabase.table("inventario").select("*").eq("empresa_id", empresa_id).eq("nombre", nombre_item).limit(1).execute(),
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_get_inventario_item:{type(e).__name__}")
        return None


def insert_inventario_movimiento(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta un movimiento en inventario_movimientos. El trigger SQL auto-actualiza stock_actual."""
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_inventario_mov",
            lambda: supabase.table("inventario_movimientos").upsert(datos, on_conflict="id").execute(),
        )
        _invalidate_cache_prefix(f"_sql_op_inv_{datos.get('empresa_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_inventario_mov:{type(e).__name__}")
        return None


def update_inventario_stock_sql(inventario_id: str, nuevo_stock: int, empresa_id: str) -> bool:
    """Actualiza directamente stock_actual en inventario (fallback si trigger no funciona)."""
    if not _ok():
        return False
    try:
        response = _supabase_execute_with_retry(
            "update_inventario_stock",
            lambda: supabase.table("inventario").update({"stock_actual": nuevo_stock}).eq("id", inventario_id).execute(),
        )
        _invalidate_cache_prefix(f"_sql_op_inv_{empresa_id}")
        return bool(response and response.data)
    except Exception as e:
        log_event("db_sql", f"error_update_inventario_stock:{type(e).__name__}")
        return False


def update_inventario_item_sql(inventario_id: str, cambios: Dict[str, Any], empresa_id: str) -> bool:
    """Actualiza campos permitidos de un ítem de inventario e invalida cache."""
    if not _ok() or not inventario_id or not cambios:
        return False
    campos_permitidos = {"stock_actual", "stock_minimo", "costo_unitario", "categoria", "nombre"}
    payload = {k: v for k, v in cambios.items() if k in campos_permitidos}
    if not payload:
        return False
    try:
        response = _supabase_execute_with_retry(
            "update_inventario_item",
            lambda: supabase.table("inventario").update(payload).eq("id", inventario_id).execute(),
        )
        _invalidate_cache_prefix(f"_sql_op_inv_{empresa_id}")
        return bool(response and response.data)
    except Exception as e:
        log_event("db_sql", f"error_update_inventario_item:{type(e).__name__}")
        return False


def delete_inventario_item_sql(inventario_id: str, empresa_id: str) -> bool:
    """Elimina un ítem de inventario e invalida cache."""
    if not _ok() or not inventario_id:
        return False
    try:
        response = _supabase_execute_with_retry(
            "delete_inventario_item",
            lambda: supabase.table("inventario").delete().eq("id", inventario_id).execute(),
        )
        _invalidate_cache_prefix(f"_sql_op_inv_{empresa_id}")
        return bool(response and response.data)
    except Exception as e:
        log_event("db_sql", f"error_delete_inventario_item:{type(e).__name__}")
        return False


def insert_checkin(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_checkin",
            lambda: supabase.table("checkin_asistencia").upsert(datos, on_conflict="id").execute(),
        )
        _invalidate_cache_prefix(f"_sql_op_chk_{datos.get('empresa_id', '')}")
        try:
            get_checkins_by_empresa.clear()
        except Exception as _e_chk_cache:
            log_event("db_sql", f"cache_clear_error:{type(_e_chk_cache).__name__}:{_e_chk_cache}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_checkin:{type(e).__name__}")
        return None
