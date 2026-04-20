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


def insert_auditoria(datos: Dict[str, Any]) -> None:
    """Inserta un log de auditoría de forma silenciosa."""
    if not _ok():
        return
    try:
        _supabase_execute_with_retry(
            "insert_auditoria",
            lambda: supabase.table("auditoria_legal").insert(datos).execute(),
        )
    except Exception as e:
        log_event("db_sql", f"error_insert_auditoria:{type(e).__name__}")


@st.cache_data(ttl=60, show_spinner=False)
def get_auditoria_by_empresa(empresa_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_auditoria",
            lambda: supabase.table("auditoria_legal").select("*, usuarios(nombre), pacientes(nombre_completo)").eq("empresa_id", empresa_id).order("fecha_evento", desc=True).limit(limit).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_auditoria:{type(e).__name__}")
        return []


@st.cache_data(ttl=60, show_spinner=False)
def get_turnos_by_empresa(empresa_id: str, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
    """Obtiene los turnos de una empresa en un rango de fechas."""
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_turnos",
            lambda: supabase.table("turnos").select("*, pacientes(nombre_completo, dni), usuarios(nombre)").eq("empresa_id", empresa_id).gte("fecha_hora_programada", fecha_inicio).lte("fecha_hora_programada", fecha_fin).order("fecha_hora_programada", desc=False).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_turnos:{type(e).__name__}")
        return []


def insert_turno(datos_turno: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta un nuevo turno en la agenda."""
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_turno",
            lambda: supabase.table("turnos").insert(datos_turno).execute(),
        )
        get_turnos_by_empresa.clear()
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
        get_turnos_by_empresa.clear()
        return True
    except Exception as e:
        log_event("db_sql", f"error_update_turno:{type(e).__name__}")
        return False


@st.cache_data(ttl=30, show_spinner=False)
def get_administraciones_dia(paciente_id: str, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
    """Obtiene los registros de administración (MAR) para un rango de fechas."""
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_administraciones",
            lambda: supabase.table("administracion_med").select("*, indicaciones(medicamento, via_administracion, frecuencia), usuarios(nombre)").eq("paciente_id", paciente_id).gte("fecha_registro", fecha_inicio).lte("fecha_registro", fecha_fin).execute(),
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
            lambda: supabase.table("administracion_med").insert(datos_admin).execute(),
        )
        get_administraciones_dia.clear()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_administracion:{type(e).__name__}")
        return None


@st.cache_data(ttl=90, show_spinner=False)
def get_emergencias_by_paciente(paciente_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_emergencias_paciente",
            lambda: supabase.table("emergencias").select("*, pacientes(nombre_completo), usuarios(nombre)").eq("paciente_id", paciente_id).order("fecha_llamado", desc=True).limit(limit).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_emergencias_paciente:{type(e).__name__}")
        return []


@st.cache_data(ttl=60, show_spinner=False)
def get_emergencias_by_empresa(empresa_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_emergencias",
            lambda: supabase.table("emergencias").select("*, pacientes(nombre_completo), usuarios(nombre)").eq("empresa_id", empresa_id).order("fecha_llamado", desc=True).limit(limit).execute(),
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
            lambda: supabase.table("emergencias").insert(datos).execute(),
        )
        get_emergencias_by_empresa.clear()
        get_emergencias_by_paciente.clear()
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
        get_emergencias_by_empresa.clear()
        get_emergencias_by_paciente.clear()
        return True
    except Exception as e:
        log_event("db_sql", f"error_update_emergencia:{type(e).__name__}")
        return False


@st.cache_data(ttl=120, show_spinner=False)
def get_inventario_by_empresa(empresa_id: str) -> List[Dict[str, Any]]:
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
            lambda: supabase.table("inventario").insert(datos).execute(),
        )
        get_inventario_by_empresa.clear()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_inventario:{type(e).__name__}")
        return None


@st.cache_data(ttl=120, show_spinner=False)
def get_facturacion_by_empresa(empresa_id: str) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_facturacion",
            lambda: supabase.table("facturacion").select("*, pacientes(nombre_completo)").eq("empresa_id", empresa_id).order("fecha_emision", desc=True).execute(),
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
            lambda: supabase.table("facturacion").insert(datos).execute(),
        )
        get_facturacion_by_empresa.clear()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_facturacion:{type(e).__name__}")
        return None


@st.cache_data(ttl=120, show_spinner=False)
def get_balance_by_empresa(empresa_id: str) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_balance",
            lambda: supabase.table("balance").select("*").eq("empresa_id", empresa_id).order("fecha_movimiento", desc=True).execute(),
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
            lambda: supabase.table("balance").insert(datos).execute(),
        )
        get_balance_by_empresa.clear()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_balance:{type(e).__name__}")
        return None


@st.cache_data(ttl=30, show_spinner=False)
def get_checkins_by_empresa(empresa_id: str, limit: int = 500) -> List[Dict[str, Any]]:
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_checkins",
            lambda: supabase.table("checkin_asistencia").select("*, pacientes(nombre_completo), usuarios(nombre)").eq("empresa_id", empresa_id).order("fecha_hora", desc=True).limit(limit).execute(),
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_checkins:{type(e).__name__}")
        return []


def insert_checkin(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_checkin",
            lambda: supabase.table("checkin_asistencia").insert(datos).execute(),
        )
        get_checkins_by_empresa.clear()
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_checkin:{type(e).__name__}")
        return None
