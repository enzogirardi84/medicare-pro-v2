"""Operaciones SQL para diagnosticos clinicos con codificacion CIE-10/11."""

import time
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
                import secrets
                delay = base_delay * (2 ** i) + secrets.randbelow(100) / 1000
                time.sleep(delay)
        return fn()


def _ok() -> bool:
    return supabase is not None


def _invalidate_cache_prefix(prefix: str) -> None:
    for k in list(st.session_state.keys()):
        if k.startswith(prefix):
            st.session_state.pop(k, None)


def get_diagnosticos_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    """Obtiene diagnosticos activos e historicos de un paciente."""
    _ensure_diag_table()
    cache_key = f"_sql_diag_pac_{paciente_id}"
    cached = st.session_state.get(cache_key)
    if cached:
        if time.monotonic() - cached["ts"] < 90:
            return cached["data"]
        st.session_state.pop(cache_key, None)
    if not _ok():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_diagnosticos",
            lambda: supabase.table("diagnosticos_paciente").select("*").eq("paciente_id", paciente_id).order("fecha_diagnostico", desc=True).execute(),
        )
        data = response.data if response and response.data else []
        st.session_state[cache_key] = {"data": data, "ts": time.monotonic()}
        return data
    except Exception as e:
        log_event("db_sql", f"error_get_diagnosticos:{type(e).__name__}")
        return []


def insert_diagnostico(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta un nuevo diagnostico (intenta crear tabla si falla)."""
    _ensure_diag_table()
    if not _ok():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_diagnostico",
            lambda: supabase.table("diagnosticos_paciente").insert(datos).execute(),
        )
        _invalidate_cache_prefix(f"_sql_diag_pac_{datos.get('paciente_id', '')}")
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_diagnostico:{type(e).__name__}")
        return None


def update_diagnostico(diagnostico_id: str, datos: Dict[str, Any]) -> bool:
    """Actualiza un diagnostico existente."""
    if not _ok():
        return False
    try:
        _supabase_execute_with_retry(
            "update_diagnostico",
            lambda: supabase.table("diagnosticos_paciente").update(datos).eq("id", diagnostico_id).execute(),
        )
        _invalidate_cache_prefix("_sql_diag_pac_")
        return True
    except Exception as e:
        log_event("db_sql", f"error_update_diagnostico:{type(e).__name__}")
        return False


def delete_diagnostico(diagnostico_id: str) -> bool:
    """Elimina un diagnostico."""
    if not _ok():
        return False
    try:
        _supabase_execute_with_retry(
            "delete_diagnostico",
            lambda: supabase.table("diagnosticos_paciente").delete().eq("id", diagnostico_id).execute(),
        )
        _invalidate_cache_prefix("_sql_diag_pac_")
        return True
    except Exception as e:
        log_event("db_sql", f"error_delete_diagnostico:{type(e).__name__}")
        return False


# Creacion diferida de la tabla (ya no se ejecuta al importar para no demorar el arranque)
_DIAG_TABLE_CREATED = False
_DIAG_TABLE_INTENTADO = False


def _ensure_diag_table():
    global _DIAG_TABLE_CREATED, _DIAG_TABLE_INTENTADO
    if _DIAG_TABLE_CREATED or _DIAG_TABLE_INTENTADO or not _ok():
        return
    _DIAG_TABLE_INTENTADO = True
    try:
        sql = """
        CREATE TABLE IF NOT EXISTS diagnosticos_paciente (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            paciente_id UUID NOT NULL,
            usuario_id UUID,
            empresa_id UUID,
            cie_codigo VARCHAR(10) NOT NULL,
            cie_version VARCHAR(5) DEFAULT 'CIE-10',
            descripcion TEXT NOT NULL,
            tipo_diagnostico VARCHAR(20) DEFAULT 'Principal',
            fecha_diagnostico TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            fecha_resolucion TIMESTAMP WITH TIME ZONE,
            estado VARCHAR(20) DEFAULT 'Activo',
            profesional TEXT,
            notas TEXT,
            created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
            updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
        );
        """
        _supabase_execute_with_retry(
            "ensure_diag_table",
            lambda: supabase.rpc("exec_sql", {"sql": sql}).execute(),
        )
        _DIAG_TABLE_CREATED = True
    except Exception as e:
        log_event("db_sql", f"ensure_diag_table_skip:{type(e).__name__}:{e}")
