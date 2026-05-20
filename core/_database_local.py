"""Persistencia local (JSON en disco) para core/database.py.


from __future__ import annotations

Extraído de core/database.py.
"""
import json
import os
import random
import time
from pathlib import Path

from core.db_serialize import loads_db_payload, loads_json_any

LOCAL_DB_PATH = Path(__file__).resolve().parent.parent / ".streamlit" / "local_data.json"
LOCAL_DB_DIR = Path(__file__).resolve().parent.parent / ".streamlit" / "data_store"
LOCAL_TENANTS_DIR = LOCAL_DB_DIR / "tenants"


def _lock_file(lock_path: Path, timeout: float = 5.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            fd = os.open(str(lock_path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return True
        except FileExistsError:
            time.sleep(random.uniform(0.05, 0.15))
    return False


def _unlock_file(lock_path: Path) -> None:
    try:
        lock_path.unlink(missing_ok=True)
    except Exception:
        pass


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
            lock_path = Path(str(LOCAL_DB_PATH) + ".lock")
            if _lock_file(lock_path):
                try:
                    LOCAL_DB_PATH.write_bytes(payload_bytes)
                finally:
                    _unlock_file(lock_path)
            return True
        manifest = {
            "version": 2,
            "keys": sorted(list(data.keys())),
            "updated_at": time.time(),
        }
        for key, value in data.items():
            _p = LOCAL_DB_DIR / f"{key}.json"
            lock_path = Path(str(_p) + ".lock")
            if _lock_file(lock_path):
                try:
                    _p.write_text(
                        json.dumps(value, ensure_ascii=False, indent=2, default=str),
                        encoding="utf-8",
                    )
                finally:
                    _unlock_file(lock_path)
        _manifest_path = LOCAL_DB_DIR / "_manifest.json"
        _mlock = Path(str(_manifest_path) + ".lock")
        if _lock_file(_mlock):
            try:
                _manifest_path.write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2),
                    encoding="utf-8",
                )
            finally:
                _unlock_file(_mlock)
        lock_path = Path(str(LOCAL_DB_PATH) + ".lock")
        if _lock_file(lock_path):
            try:
                LOCAL_DB_PATH.write_text(
                    json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str),
                    encoding="utf-8",
                )
            finally:
                _unlock_file(lock_path)
        return True
    except Exception:
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
    except Exception:
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
    except Exception:
        return None
    return None


def _guardar_local_tenant(tenant_key: str, data: dict, payload_bytes: bytes | None = None) -> bool:
    try:
        fs_key = _tenant_local_fs_key(tenant_key)
        if not fs_key:
            return False
        LOCAL_TENANTS_DIR.mkdir(parents=True, exist_ok=True)
        path = LOCAL_TENANTS_DIR / f"{fs_key}.json"
        lock_path = Path(str(path) + ".lock")
        if not _lock_file(lock_path):
            return False
        try:
            if payload_bytes is not None:
                path.write_bytes(payload_bytes)
            else:
                path.write_text(
                    json.dumps(data, ensure_ascii=False, separators=(",", ":"), default=str),
                    encoding="utf-8",
                )
        finally:
            _unlock_file(lock_path)
        return True
    except Exception:
        return False
