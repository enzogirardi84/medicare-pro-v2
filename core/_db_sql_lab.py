"""Funciones SQL para el modulo de Laboratorio (LIS)."""
from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

import streamlit as st

from core.app_logging import log_event

try:
    from core.database import supabase
except Exception:
    supabase = None


def _ok() -> bool:
    return supabase is not None


def _cache_get(key: str, ttl: int = 90) -> Optional[Any]:
    cached = st.session_state.get(key)
    if cached and time.monotonic() - cached["ts"] < ttl:
        return cached["data"]
    return None


def _cache_set(key: str, data: Any):
    st.session_state[key] = {"data": data, "ts": time.monotonic()}


def _invalidate(prefix: str):
    for k in list(st.session_state.keys()):
        if k.startswith(prefix):
            del st.session_state[k]


# ── Categorias ──────────────────────────────────────────────

def get_lab_categorias() -> List[Dict[str, Any]]:
    cached = _cache_get("_sql_lab_cat")
    if cached is not None:
        return cached
    if not _ok():
        return []
    try:
        resp = supabase.table("lab_categorias").select("*").order("nombre").execute()
        data = resp.data if resp and resp.data else []
        _cache_set("_sql_lab_cat", data)
        return data
    except Exception as e:
        log_event("db_sql_lab", f"get_categorias:{e}")
        return []


def insert_lab_categoria(nombre: str, descripcion: str = "") -> Optional[Dict]:
    if not _ok() or not nombre.strip():
        return None
    try:
        resp = supabase.table("lab_categorias").insert({
            "nombre": nombre.strip(), "descripcion": descripcion.strip()
        }).execute()
        _invalidate("_sql_lab_cat")
        return resp.data[0] if resp and resp.data else None
    except Exception as e:
        log_event("db_sql_lab", f"insert_categoria:{e}")
        return None


# ── Estudios (analitos) ─────────────────────────────────────

def get_lab_estudios(categoria_id: Optional[int] = None) -> List[Dict[str, Any]]:
    cached = _cache_get("_sql_lab_est")
    if cached is not None:
        if categoria_id is not None:
            return [e for e in cached if e.get("categoria_id") == categoria_id]
        return cached
    if not _ok():
        return []
    try:
        q = supabase.table("lab_estudios").select("*").order("nombre")
        resp = q.execute()
        data = resp.data if resp and resp.data else []
        _cache_set("_sql_lab_est", data)
        if categoria_id is not None:
            return [e for e in data if e.get("categoria_id") == categoria_id]
        return data
    except Exception as e:
        log_event("db_sql_lab", f"get_estudios:{e}")
        return []


def insert_lab_estudio(datos: Dict[str, Any]) -> Optional[Dict]:
    if not _ok():
        return None
    try:
        resp = supabase.table("lab_estudios").insert(datos).execute()
        _invalidate("_sql_lab_est")
        return resp.data[0] if resp and resp.data else None
    except Exception as e:
        log_event("db_sql_lab", f"insert_estudio:{e}")
        return None


def update_lab_estudio(estudio_id: int, datos: Dict[str, Any]) -> bool:
    if not _ok():
        return False
    try:
        supabase.table("lab_estudios").update(datos).eq("id", estudio_id).execute()
        _invalidate("_sql_lab_est")
        return True
    except Exception as e:
        log_event("db_sql_lab", f"update_estudio:{e}")
        return False


# ── Ordenes ─────────────────────────────────────────────────

def get_lab_ordenes(estado: Optional[str] = None, limit: int = 200) -> List[Dict]:
    cached = _cache_get("_sql_lab_ord")
    if cached is not None:
        if estado:
            return [o for o in cached if o.get("estado") == estado][:limit]
        return cached[:limit]
    if not _ok():
        return []
    try:
        q = supabase.table("lab_ordenes").select("*").order("created_at", desc=True).limit(limit)
        resp = q.execute()
        data = resp.data if resp and resp.data else []
        _cache_set("_sql_lab_ord", data)
        if estado:
            return [o for o in data if o.get("estado") == estado]
        return data
    except Exception as e:
        log_event("db_sql_lab", f"get_ordenes:{e}")
        return []


def get_lab_ordenes_by_paciente(paciente_id: str, limit: int = 100) -> List[Dict]:
    if not _ok():
        return []
    try:
        resp = supabase.table("lab_ordenes").select("*").eq("paciente_id", paciente_id).order("created_at", desc=True).limit(limit).execute()
        return resp.data if resp and resp.data else []
    except Exception as e:
        log_event("db_sql_lab", f"get_ordenes_pac:{e}")
        return []


def insert_lab_orden(datos: Dict[str, Any]) -> Optional[Dict]:
    if not _ok():
        return None
    try:
        resp = supabase.table("lab_ordenes").insert(datos).execute()
        _invalidate("_sql_lab_ord")
        return resp.data[0] if resp and resp.data else None
    except Exception as e:
        log_event("db_sql_lab", f"insert_orden:{e}")
        return None


def update_lab_orden(orden_id: int, datos: Dict[str, Any]) -> bool:
    if not _ok():
        return False
    try:
        supabase.table("lab_ordenes").update(datos).eq("id", orden_id).execute()
        _invalidate("_sql_lab_ord")
        return True
    except Exception as e:
        log_event("db_sql_lab", f"update_orden:{e}")
        return False


# ── Orden Items (analitos por orden) ────────────────────────

def get_lab_orden_items(orden_id: int) -> List[Dict]:
    if not _ok():
        return []
    try:
        resp = supabase.table("lab_orden_items").select("*").eq("orden_id", orden_id).execute()
        return resp.data if resp and resp.data else []
    except Exception as e:
        log_event("db_sql_lab", f"get_items:{e}")
        return []


def insert_lab_orden_items(items: List[Dict]) -> bool:
    if not _ok() or not items:
        return False
    try:
        supabase.table("lab_orden_items").insert(items).execute()
        return True
    except Exception as e:
        log_event("db_sql_lab", f"insert_items:{e}")
        return False


def update_lab_orden_item(item_id: int, datos: Dict) -> bool:
    if not _ok():
        return False
    try:
        supabase.table("lab_orden_items").update(datos).eq("id", item_id).execute()
        return True
    except Exception as e:
        log_event("db_sql_lab", f"update_item:{e}")
        return False


# ── Muestras ────────────────────────────────────────────────

def insert_lab_muestra(datos: Dict) -> Optional[Dict]:
    if not _ok():
        return None
    try:
        resp = supabase.table("lab_muestras").insert(datos).execute()
        return resp.data[0] if resp and resp.data else None
    except Exception as e:
        log_event("db_sql_lab", f"insert_muestra:{e}")
        return None


def get_lab_muestras(orden_id: Optional[int] = None) -> List[Dict]:
    if not _ok():
        return []
    try:
        q = supabase.table("lab_muestras").select("*")
        if orden_id is not None:
            q = q.eq("orden_id", orden_id)
        resp = q.order("created_at", desc=True).execute()
        return resp.data if resp and resp.data else []
    except Exception as e:
        log_event("db_sql_lab", f"get_muestras:{e}")
        return []
