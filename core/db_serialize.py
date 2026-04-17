"""
Serialización JSON clínica: compacta, estable para hash, orjson opcional.
Incluye compresión gzip transparente para reducir el payload en Supabase ~8-12x.

- `dumps_db_sorted` / `loads_db_payload`: raíz dict (guardado monolito / tenant).
- `loads_json_any`: cualquier JSON (dict, list, …) para shards legacy y archivos auxiliares.
- `compress_payload` / `decompress_payload`: gzip backward-compatible para Supabase.
"""

from __future__ import annotations

import base64
import gzip
import json
from typing import Any, Dict, Tuple

_COMPRESS_MAGIC = "_mc_gz2"

try:
    import orjson as _orjson

    ORJSON_AVAILABLE = True
except ImportError:
    _orjson = None
    ORJSON_AVAILABLE = False


def _orjson_default(obj: Any) -> str:
    return str(obj)


def loads_json_any(raw: bytes | str) -> Any:
    """Parsea JSON (dict, list, etc.). Usa orjson si está instalado."""
    if isinstance(raw, str):
        b = raw.encode("utf-8")
    else:
        b = raw
    if ORJSON_AVAILABLE and _orjson is not None:
        return _orjson.loads(b)
    return json.loads(b.decode("utf-8"))


def dumps_db_sorted(data: Dict[str, Any]) -> Tuple[bytes, str]:
    """Devuelve (bytes_utf8, str_utf8) con claves ordenadas (estable para MD5)."""
    if ORJSON_AVAILABLE and _orjson is not None:
        b = _orjson.dumps(data, option=_orjson.OPT_SORT_KEYS, default=_orjson_default)
        return b, b.decode("utf-8")
    s = json.dumps(data, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))
    raw = s.encode("utf-8")
    return raw, s


def loads_db_payload(raw: bytes | str) -> Dict[str, Any]:
    """Raíz debe ser dict (backup monolito / tenant); otro tipo → {}."""
    out = loads_json_any(raw)
    return out if isinstance(out, dict) else {}


def compress_payload(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Comprime el dict a gzip+base64 y lo envuelve en un dict con magic key.
    Reduce el JSON de ~2MB a ~150-200KB → Supabase upsert/select ~8-12x mas rapido.
    """
    try:
        raw, _ = dumps_db_sorted(data)
        compressed = gzip.compress(raw, compresslevel=6)
        encoded = base64.b64encode(compressed).decode("ascii")
        return {_COMPRESS_MAGIC: encoded}
    except Exception:
        return data


def decompress_payload(data) -> Dict[str, Any]:
    """
    Si el dict tiene la magic key, descomprime. Si no, devuelve tal cual (backward compatible).
    """
    if not isinstance(data, dict):
        return data if isinstance(data, dict) else {}
    if _COMPRESS_MAGIC not in data:
        return data
    try:
        compressed = base64.b64decode(data[_COMPRESS_MAGIC])
        raw = gzip.decompress(compressed)
        out = loads_json_any(raw)
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


def is_payload_compressed(data) -> bool:
    """True si el payload ya está comprimido con nuestro esquema."""
    return isinstance(data, dict) and _COMPRESS_MAGIC in data
