"""Capa de acceso a datos vía Supabase para Medicare Billing Pro."""
from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import SUPABASE_URL, SUPABASE_KEY
from core.app_logging import log_event

LOCAL_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "billing_data.json"
LOCAL_COLLECTIONS = {
    "clientes": [],
    "presupuestos": [],
    "prefacturas": [],
    "cobros": [],
}

supabase = None
try:
    from supabase import create_client, Client
    if SUPABASE_URL and SUPABASE_KEY:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
except ImportError:
    log_event("db", "supabase no disponible, usando almacenamiento local")
except Exception as e:
    log_event("db", f"error_init_supabase:{type(e).__name__}:{e}")


def _supabase_execute_with_retry(op_name: str, fn, attempts: int = 3, base_delay: float = 0.35):
    last_error = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as e:
            last_error = e
            time.sleep(base_delay * (i + 1))
    raise last_error


def _load_local_data() -> Dict[str, List[Dict[str, Any]]]:
    try:
        if LOCAL_DATA_PATH.exists():
            data = json.loads(LOCAL_DATA_PATH.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                return {k: list(data.get(k, [])) for k in LOCAL_COLLECTIONS}
    except Exception as e:
        log_event("db", f"local_load_error:{type(e).__name__}:{e}")
    return {k: list(v) for k, v in LOCAL_COLLECTIONS.items()}


def _save_local_data(data: Dict[str, List[Dict[str, Any]]]) -> bool:
    try:
        LOCAL_DATA_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_DATA_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        return True
    except Exception as e:
        log_event("db", f"local_save_error:{type(e).__name__}:{e}")
        return False


def _local_get(collection: str, empresa_id: str) -> List[Dict[str, Any]]:
    data = _load_local_data()
    rows = data.get(collection, [])
    return [r for r in rows if str(r.get("empresa_id", "")) == str(empresa_id)]


def _local_upsert(collection: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    data = _load_local_data()
    rows = data.setdefault(collection, [])
    row_id = str(row.get("id", ""))
    replaced = False
    for i, existing in enumerate(rows):
        if str(existing.get("id", "")) == row_id:
            rows[i] = dict(row)
            replaced = True
            break
    if not replaced:
        rows.append(dict(row))
    return dict(row) if _save_local_data(data) else None


def _local_delete(collection: str, row_id: str) -> bool:
    data = _load_local_data()
    rows = data.setdefault(collection, [])
    before = len(rows)
    data[collection] = [r for r in rows if str(r.get("id", "")) != str(row_id)]
    return _save_local_data(data) and len(data[collection]) < before


# ── Clientes ───────────────────────────────────────────────

def get_clientes(empresa_id: str) -> List[Dict[str, Any]]:
    if not supabase:
        return _local_get("clientes", empresa_id)
    try:
        resp = _supabase_execute_with_retry(
            "get_clientes",
            lambda: supabase.table("billing_clientes").select("*").eq("empresa_id", empresa_id).order("nombre").execute()
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_clientes_error:{e}")
        return _local_get("clientes", empresa_id)


def upsert_cliente(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not supabase:
        return _local_upsert("clientes", data)
    try:
        resp = _supabase_execute_with_retry(
            "upsert_cliente",
            lambda: supabase.table("billing_clientes").upsert(data).execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        log_event("db", f"upsert_cliente_error:{e}")
        return _local_upsert("clientes", data)


def delete_cliente(cliente_id: str) -> bool:
    if not supabase:
        return _local_delete("clientes", cliente_id)
    try:
        _supabase_execute_with_retry(
            "delete_cliente",
            lambda: supabase.table("billing_clientes").delete().eq("id", cliente_id).execute()
        )
        return True
    except Exception as e:
        log_event("db", f"delete_cliente_error:{e}")
        return _local_delete("clientes", cliente_id)


# ── Presupuestos ───────────────────────────────────────────

def get_presupuestos(empresa_id: str) -> List[Dict[str, Any]]:
    if not supabase:
        return _local_get("presupuestos", empresa_id)
    try:
        resp = _supabase_execute_with_retry(
            "get_presupuestos",
            lambda: supabase.table("billing_presupuestos").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).execute()
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_presupuestos_error:{e}")
        return _local_get("presupuestos", empresa_id)


def upsert_presupuesto(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not supabase:
        return _local_upsert("presupuestos", data)
    try:
        resp = _supabase_execute_with_retry(
            "upsert_presupuesto",
            lambda: supabase.table("billing_presupuestos").upsert(data).execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        log_event("db", f"upsert_presupuesto_error:{e}")
        return _local_upsert("presupuestos", data)


def delete_presupuesto(presupuesto_id: str) -> bool:
    if not supabase:
        return _local_delete("presupuestos", presupuesto_id)
    try:
        _supabase_execute_with_retry(
            "delete_presupuesto",
            lambda: supabase.table("billing_presupuestos").delete().eq("id", presupuesto_id).execute()
        )
        return True
    except Exception as e:
        log_event("db", f"delete_presupuesto_error:{e}")
        return _local_delete("presupuestos", presupuesto_id)


# ── Pre-facturas ───────────────────────────────────────────

def get_prefacturas(empresa_id: str) -> List[Dict[str, Any]]:
    if not supabase:
        return _local_get("prefacturas", empresa_id)
    try:
        resp = _supabase_execute_with_retry(
            "get_prefacturas",
            lambda: supabase.table("billing_prefacturas").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).execute()
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_prefacturas_error:{e}")
        return _local_get("prefacturas", empresa_id)


def upsert_prefactura(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not supabase:
        return _local_upsert("prefacturas", data)
    try:
        resp = _supabase_execute_with_retry(
            "upsert_prefactura",
            lambda: supabase.table("billing_prefacturas").upsert(data).execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        log_event("db", f"upsert_prefactura_error:{e}")
        return _local_upsert("prefacturas", data)


def delete_prefactura(prefactura_id: str) -> bool:
    if not supabase:
        return _local_delete("prefacturas", prefactura_id)
    try:
        _supabase_execute_with_retry(
            "delete_prefactura",
            lambda: supabase.table("billing_prefacturas").delete().eq("id", prefactura_id).execute()
        )
        return True
    except Exception as e:
        log_event("db", f"delete_prefactura_error:{e}")
        return _local_delete("prefacturas", prefactura_id)


# ── Cobros ─────────────────────────────────────────────────

def get_cobros(empresa_id: str) -> List[Dict[str, Any]]:
    if not supabase:
        return _local_get("cobros", empresa_id)
    try:
        resp = _supabase_execute_with_retry(
            "get_cobros",
            lambda: supabase.table("billing_cobros").select("*").eq("empresa_id", empresa_id).order("fecha", desc=True).execute()
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_cobros_error:{e}")
        return _local_get("cobros", empresa_id)


def upsert_cobro(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not supabase:
        return _local_upsert("cobros", data)
    try:
        resp = _supabase_execute_with_retry(
            "upsert_cobro",
            lambda: supabase.table("billing_cobros").upsert(data).execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        log_event("db", f"upsert_cobro_error:{e}")
        return _local_upsert("cobros", data)


def delete_cobro(cobro_id: str) -> bool:
    if not supabase:
        return _local_delete("cobros", cobro_id)
    try:
        _supabase_execute_with_retry(
            "delete_cobro",
            lambda: supabase.table("billing_cobros").delete().eq("id", cobro_id).execute()
        )
        return True
    except Exception as e:
        log_event("db", f"delete_cobro_error:{e}")
        return _local_delete("cobros", cobro_id)


# ── Empresas ───────────────────────────────────────────────

def get_empresas() -> List[Dict[str, Any]]:
    if not supabase:
        return []
    try:
        resp = _supabase_execute_with_retry(
            "get_empresas",
            lambda: supabase.table("empresas").select("id,nombre").order("nombre").execute()
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_empresas_error:{e}")
        return []
