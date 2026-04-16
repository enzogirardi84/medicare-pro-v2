"""Parseo y ordenación de fechas en registros clínicos (sin Streamlit)."""

from __future__ import annotations

from datetime import date, datetime
from functools import lru_cache
from typing import Any, Dict, List, Optional


@lru_cache(maxsize=8192)
def _parse_datetime_string(s: str) -> Optional[datetime]:
    s = (s or "").strip()
    if not s:
        return None
    for fmt, maxlen in (
        ("%d/%m/%Y %H:%M:%S", 19),
        ("%d/%m/%Y %H:%M", 16),
        ("%d/%m/%Y", 10),
        ("%Y-%m-%d %H:%M:%S", 19),
        ("%Y-%m-%d %H:%M", 16),
        ("%Y-%m-%d", 10),
    ):
        frag = s[:maxlen]
        try:
            return datetime.strptime(frag, fmt)
        except ValueError:
            continue
    return None


def parse_registro_fecha_hora(reg: Dict[str, Any]) -> Optional[datetime]:
    if not reg:
        return None
    fh = str(reg.get("fecha_hora_programada") or "").strip()
    if fh:
        dt = _parse_datetime_string(fh)
        if dt:
            return dt
    f = str(reg.get("fecha") or reg.get("fecha_programada") or "").strip()
    h = str(reg.get("hora") or "").strip()
    if f:
        if h:
            dt = _parse_datetime_string(f"{f} {h}")
            if dt:
                return dt
        dt = _parse_datetime_string(f)
        if dt:
            return dt
    for key in ("fecha_hora", "creado_en", "fecha_evento", "timestamp", "fecha_toma"):
        val = reg.get(key)
        if val not in (None, ""):
            dt = _parse_datetime_string(str(val))
            if dt:
                return dt
    return None


def fecha_registro_o_none(reg: Dict[str, Any]) -> Optional[date]:
    dt = parse_registro_fecha_hora(reg)
    if not dt:
        return None
    return dt.date()


def registro_en_rango_fechas(
    reg: Dict[str, Any],
    d_desde,
    d_hasta,
    *,
    incluir_sin_fecha: bool,
) -> bool:
    fd = fecha_registro_o_none(reg)
    if fd is None:
        return incluir_sin_fecha
    return d_desde <= fd <= d_hasta


def sort_registros_por_fecha(registros: List[Dict[str, Any]], *, recientes_primero: bool) -> List[Dict[str, Any]]:
    def clave(r: Dict[str, Any]):
        dt = parse_registro_fecha_hora(r)
        return dt or datetime.min

    return sorted(registros, key=clave, reverse=recientes_primero)
