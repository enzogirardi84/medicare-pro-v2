"""Persistencia local (JSON en disco) para core/database.py.

Extraído de core/database.py.
"""
import json
import time
from pathlib import Path

from core.db_serialize import dumps_db_sorted, loads_db_payload, loads_json_any
from core.app_logging import log_event

LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "local_data.json"
LOCAL_DB_DIR = Path(__file__).resolve().parent.parent / ".streamlit" / "data_store"
LOCAL_TENANTS_DIR = LOCAL_DB_DIR / "tenants"


def _tenant_local_fs_key(tenant_key: str) -> str:
    raw = (tenant_key or "").strip().lower()
    if not raw:
        return ""
    s = raw.replace("..", "_").replace("/", "_").replace("\\", "_")
    out: list[str] = []
    for ch in s:
        if ch.isalnum() or ch in " _-.":
            out.append(ch)
        else:
            out.append("_")
    s2 = "".join(out).strip("._ ")
    return (s2 if s2 else "tenant")[:180]


def _guardar_local(data, payload_bytes: bytes | None = None):
    try:
        LOCAL_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        LOCAL_DB_DIR.mkdir(parents=True, exist_ok=True)
        if payload_bytes is not None:
            LOCAL_DB_PATH.write_bytes(payload_bytes)
            return True
        manifest = {
            "version": 2,
            "keys": sorted(list(data.keys())),
            "updated_at": time.time(),
        }
        for key, value in data.items():
            (LOCAL_DB_DIR / f"{key}.json").write_text(
                json.dumps(value, ensure_ascii=False, indent=2, default=str),
                encoding="utf-8",
            )
        (LOCAL_DB_DIR / "_manifest.json").write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        LOCAL_DB_PATH.write_text(
            json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str),
            encoding="utf-8",
        )
        return True
    except Exception as _exc:
        log_event("local_db", f"guardar_local_falla:{type(_exc).__name__}")
        return False


def _cargar_local():
    try:
        if LOCAL_DB_PATH.exists():
            raw = LOCAL_DB_PATH.read_bytes()
            if raw.strip():
                return loads_db_payload(raw)
        manifest_path = LOCAL_DB_DIR / "_manifest.json"
        if manifest_path.exists():
            manifest = loads_json_any(manifest_path.read_bytes())
            if not isinstance(manifest, dict):
                manifest = {}
            data = {}
            for key in manifest.get("keys", []):
                shard_path = LOCAL_DB_DIR / f"{key}.json"
                if shard_path.exists():
                    data[key] = loads_json_any(shard_path.read_bytes())
            if data:
                return data
    except Exception as _exc:
        log_event("local_db", f"cargar_local_falla:{type(_exc).__name__}")
        return None
    return None


def _cargar_local_tenant(tenant_key: str):
    try:
        fs_key = _tenant_local_fs_key(tenant_key)
        if not fs_key:
            return None
        p = LOCAL_TENANTS_DIR / f"{fs_key}.json"
        if p.exists():
            raw = p.read_bytes()
            if not raw.strip():
                return None
            return loads_db_payload(raw)
    except Exception as _exc:
        log_event("local_db", f"cargar_local_tenant_falla:{type(_exc).__name__}")
        return None
    return None


def _guardar_local_tenant(tenant_key: str, data: dict, payload_bytes: bytes | None = None) -> bool:
    try:
        fs_key = _tenant_local_fs_key(tenant_key)
        if not fs_key:
            return False
        LOCAL_TENANTS_DIR.mkdir(parents=True, exist_ok=True)
        path = LOCAL_TENANTS_DIR / f"{fs_key}.json"
        if payload_bytes is not None:
            path.write_bytes(payload_bytes)
        else:
            path.write_text(
                json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str),
                encoding="utf-8",
            )
        return True
    except Exception as _exc:
        log_event("local_db", f"guardar_local_tenant_falla:{type(_exc).__name__}")
        return False
