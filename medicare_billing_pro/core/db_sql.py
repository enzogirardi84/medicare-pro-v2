"""Capa de acceso a datos vía Supabase para Medicare Billing Pro."""
from __future__ import annotations

import time
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.config import ALLOW_LOCAL_FALLBACK, SUPABASE_KEY, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_URL
from core.app_logging import log_event

LOCAL_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "billing_data.json"
LOCAL_COLLECTIONS = {
    "clientes": [],
    "presupuestos": [],
    "prefacturas": [],
    "cobros": [],
    "facturas_arca": [],
    "auditoria": [],
    "config_fiscal": [],
    "numeradores": [],
}

supabase = None
last_db_error = ""
try:
    from supabase import create_client, Client
    supabase_key = SUPABASE_SERVICE_ROLE_KEY or SUPABASE_KEY
    if SUPABASE_URL and supabase_key:
        supabase: Client = create_client(SUPABASE_URL, supabase_key)
except ImportError:
    log_event("db", "supabase no disponible")
except Exception as e:
    log_event("db", f"error_init_supabase:{type(e).__name__}:{e}")


def _supabase_execute_with_retry(op_name: str, fn, attempts: int = 3, base_delay: float = 0.35):
    global last_db_error
    last_error = None
    for i in range(attempts):
        try:
            last_db_error = ""
            return fn()
        except Exception as e:
            last_error = e
            last_db_error = str(e)
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


def _fallback_get(collection: str, empresa_id: str) -> List[Dict[str, Any]]:
    if ALLOW_LOCAL_FALLBACK:
        return _local_get(collection, empresa_id)
    log_event("db", f"supabase_required_get_blocked:{collection}")
    return []


def _fallback_upsert(collection: str, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if ALLOW_LOCAL_FALLBACK:
        return _local_upsert(collection, row)
    log_event("db", f"supabase_required_upsert_blocked:{collection}")
    return None


def _fallback_delete(collection: str, row_id: str) -> bool:
    if ALLOW_LOCAL_FALLBACK:
        return _local_delete(collection, row_id)
    log_event("db", f"supabase_required_delete_blocked:{collection}:{row_id}")
    return False


# ── Clientes ───────────────────────────────────────────────

def get_clientes(empresa_id: str) -> List[Dict[str, Any]]:
    if not supabase:
        return _fallback_get("clientes", empresa_id)
    try:
        resp = _supabase_execute_with_retry(
            "get_clientes",
            lambda: supabase.table("billing_clientes").select("*").eq("empresa_id", empresa_id).order("nombre").execute()
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_clientes_error:{e}")
        return _fallback_get("clientes", empresa_id)


def upsert_cliente(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not supabase:
        return _fallback_upsert("clientes", data)
    try:
        resp = _supabase_execute_with_retry(
            "upsert_cliente",
            lambda: supabase.table("billing_clientes").upsert(data).execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        log_event("db", f"upsert_cliente_error:{e}")
        return _fallback_upsert("clientes", data)


def delete_cliente(cliente_id: str) -> bool:
    if not supabase:
        return _fallback_delete("clientes", cliente_id)
    try:
        _supabase_execute_with_retry(
            "delete_cliente",
            lambda: supabase.table("billing_clientes").delete().eq("id", cliente_id).execute()
        )
        return True
    except Exception as e:
        log_event("db", f"delete_cliente_error:{e}")
        return _fallback_delete("clientes", cliente_id)


# ── Presupuestos ───────────────────────────────────────────

def get_presupuestos(empresa_id: str) -> List[Dict[str, Any]]:
    if not supabase:
        return _fallback_get("presupuestos", empresa_id)
    try:
        resp = _supabase_execute_with_retry(
            "get_presupuestos",
            lambda: supabase.table("billing_presupuestos").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).execute()
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_presupuestos_error:{e}")
        return _fallback_get("presupuestos", empresa_id)


def upsert_presupuesto(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not supabase:
        return _fallback_upsert("presupuestos", data)
    try:
        resp = _supabase_execute_with_retry(
            "upsert_presupuesto",
            lambda: supabase.table("billing_presupuestos").upsert(data).execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        log_event("db", f"upsert_presupuesto_error:{e}")
        return _fallback_upsert("presupuestos", data)


def delete_presupuesto(presupuesto_id: str) -> bool:
    if not supabase:
        return _fallback_delete("presupuestos", presupuesto_id)
    try:
        _supabase_execute_with_retry(
            "delete_presupuesto",
            lambda: supabase.table("billing_presupuestos").delete().eq("id", presupuesto_id).execute()
        )
        return True
    except Exception as e:
        log_event("db", f"delete_presupuesto_error:{e}")
        return _fallback_delete("presupuestos", presupuesto_id)


# ── Pre-facturas ───────────────────────────────────────────

def get_prefacturas(empresa_id: str) -> List[Dict[str, Any]]:
    if not supabase:
        return _fallback_get("prefacturas", empresa_id)
    try:
        resp = _supabase_execute_with_retry(
            "get_prefacturas",
            lambda: supabase.table("billing_prefacturas").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).execute()
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_prefacturas_error:{e}")
        return _fallback_get("prefacturas", empresa_id)


def upsert_prefactura(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not supabase:
        return _fallback_upsert("prefacturas", data)
    try:
        resp = _supabase_execute_with_retry(
            "upsert_prefactura",
            lambda: supabase.table("billing_prefacturas").upsert(data).execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        log_event("db", f"upsert_prefactura_error:{e}")
        return _fallback_upsert("prefacturas", data)


def delete_prefactura(prefactura_id: str) -> bool:
    if not supabase:
        return _fallback_delete("prefacturas", prefactura_id)
    try:
        _supabase_execute_with_retry(
            "delete_prefactura",
            lambda: supabase.table("billing_prefacturas").delete().eq("id", prefactura_id).execute()
        )
        return True
    except Exception as e:
        log_event("db", f"delete_prefactura_error:{e}")
        return _fallback_delete("prefacturas", prefactura_id)


# ── Cobros ─────────────────────────────────────────────────

def get_cobros(empresa_id: str) -> List[Dict[str, Any]]:
    if not supabase:
        return _fallback_get("cobros", empresa_id)
    try:
        resp = _supabase_execute_with_retry(
            "get_cobros",
            lambda: supabase.table("billing_cobros").select("*").eq("empresa_id", empresa_id).order("fecha", desc=True).execute()
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_cobros_error:{e}")
        return _fallback_get("cobros", empresa_id)


def upsert_cobro(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not supabase:
        return _fallback_upsert("cobros", data)
    try:
        resp = _supabase_execute_with_retry(
            "upsert_cobro",
            lambda: supabase.table("billing_cobros").upsert(data).execute()
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        log_event("db", f"upsert_cobro_error:{e}")
        return _fallback_upsert("cobros", data)


def delete_cobro(cobro_id: str) -> bool:
    if not supabase:
        return _fallback_delete("cobros", cobro_id)
    try:
        _supabase_execute_with_retry(
            "delete_cobro",
            lambda: supabase.table("billing_cobros").delete().eq("id", cobro_id).execute()
        )
        return True
    except Exception as e:
        log_event("db", f"delete_cobro_error:{e}")
        return _fallback_delete("cobros", cobro_id)


# ── Empresas ───────────────────────────────────────────────

def get_config_fiscal(empresa_id: str) -> Dict[str, Any]:
    if not supabase:
        rows = _fallback_get("config_fiscal", empresa_id)
        return rows[0] if rows else {}
    try:
        resp = _supabase_execute_with_retry(
            "get_config_fiscal",
            lambda: supabase.table("billing_config_fiscal").select("*").eq("empresa_id", empresa_id).limit(1).execute(),
        )
        return resp.data[0] if resp.data else {}
    except Exception as e:
        log_event("db", f"get_config_fiscal_error:{e}")
        return {}


def upsert_config_fiscal(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not supabase:
        return _fallback_upsert("config_fiscal", data)
    try:
        resp = _supabase_execute_with_retry(
            "upsert_config_fiscal",
            lambda: supabase.table("billing_config_fiscal").upsert(data).execute(),
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        log_event("db", f"upsert_config_fiscal_error:{e}")
        return _fallback_upsert("config_fiscal", data)


def get_numeradores(empresa_id: str) -> List[Dict[str, Any]]:
    if not supabase:
        return _fallback_get("numeradores", empresa_id)
    try:
        resp = _supabase_execute_with_retry(
            "get_numeradores",
            lambda: supabase.table("billing_numeradores").select("*").eq("empresa_id", empresa_id).order("tipo").execute(),
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_numeradores_error:{e}")
        return _fallback_get("numeradores", empresa_id)


def upsert_numerador(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not supabase:
        return _fallback_upsert("numeradores", data)
    try:
        resp = _supabase_execute_with_retry(
            "upsert_numerador",
            lambda: supabase.table("billing_numeradores").upsert(data).execute(),
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        log_event("db", f"upsert_numerador_error:{e}")
        return _fallback_upsert("numeradores", data)


def generar_numero_formal(empresa_id: str, tipo: str, punto_venta: int = 1, prefijo: str = "") -> str:
    actual = next(
        (n for n in get_numeradores(empresa_id) if n.get("tipo") == tipo and int(n.get("punto_venta", 1) or 1) == int(punto_venta)),
        None,
    )
    ultimo = int((actual or {}).get("ultimo_numero", 0) or 0) + 1
    upsert_numerador(
        {
            "id": (actual or {}).get("id") or f"{empresa_id}_{tipo}_{punto_venta}",
            "empresa_id": empresa_id,
            "tipo": tipo,
            "punto_venta": int(punto_venta),
            "prefijo": prefijo,
            "ultimo_numero": ultimo,
        }
    )
    return f"{prefijo or tipo}-{int(punto_venta):04d}-{ultimo:08d}"


def get_facturas_arca(empresa_id: str) -> List[Dict[str, Any]]:
    if not supabase:
        return _fallback_get("facturas_arca", empresa_id)
    try:
        resp = _supabase_execute_with_retry(
            "get_facturas_arca",
            lambda: supabase.table("billing_facturas_arca").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).execute(),
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_facturas_arca_error:{e}")
        return _fallback_get("facturas_arca", empresa_id)


def upsert_factura_arca(data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not supabase:
        return _fallback_upsert("facturas_arca", data)
    try:
        resp = _supabase_execute_with_retry(
            "upsert_factura_arca",
            lambda: supabase.table("billing_facturas_arca").upsert(data).execute(),
        )
        return resp.data[0] if resp.data else None
    except Exception as e:
        log_event("db", f"upsert_factura_arca_error:{e}")
        return _fallback_upsert("facturas_arca", data)


def delete_factura_arca(factura_id: str) -> bool:
    if not supabase:
        return _fallback_delete("facturas_arca", factura_id)
    try:
        _supabase_execute_with_retry(
            "delete_factura_arca",
            lambda: supabase.table("billing_facturas_arca").delete().eq("id", factura_id).execute(),
        )
        return True
    except Exception as e:
        log_event("db", f"delete_factura_arca_error:{e}")
        return _fallback_delete("facturas_arca", factura_id)


def registrar_auditoria(empresa_id: str, usuario: str, accion: str, entidad: str, entidad_id: str = "", detalle: Dict[str, Any] | None = None) -> None:
    row = {
        "id": f"audit_{int(time.time() * 1000)}",
        "empresa_id": empresa_id,
        "usuario": usuario,
        "accion": accion,
        "entidad": entidad,
        "entidad_id": entidad_id,
        "detalle": detalle or {},
    }
    if not supabase:
        _fallback_upsert("auditoria", row)
        return
    try:
        _supabase_execute_with_retry("registrar_auditoria", lambda: supabase.table("billing_auditoria").insert(row).execute())
    except Exception as e:
        log_event("db", f"registrar_auditoria_error:{e}")


def get_auditoria(empresa_id: str, limit: int = 100) -> List[Dict[str, Any]]:
    if not supabase:
        return _fallback_get("auditoria", empresa_id)
    try:
        resp = _supabase_execute_with_retry(
            "get_auditoria",
            lambda: supabase.table("billing_auditoria").select("*").eq("empresa_id", empresa_id).order("created_at", desc=True).limit(limit).execute(),
        )
        return resp.data or []
    except Exception as e:
        log_event("db", f"get_auditoria_error:{e}")
        return []


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
