"""
Serialización JSON clínica: compacta, estable para hash, orjson opcional.

- `dumps_db_sorted` / `loads_db_payload`: raíz dict (guardado monolito / tenant).
- `loads_json_any`: cualquier JSON (dict, list, …) para shards legacy y archivos auxiliares.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Tuple

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
