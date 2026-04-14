"""Metricas livianas de performance por sesion (sin PHI)."""

from __future__ import annotations

import math
import time

import streamlit as st

_KEY = "_perf_samples"
_MAX_SAMPLES = 500


def _samples() -> list[dict]:
    s = st.session_state.get(_KEY)
    if not isinstance(s, list):
        s = []
        st.session_state[_KEY] = s
    return s


def record_perf(event: str, duration_ms: float, ok: bool = True) -> None:
    if not event:
        return
    try:
        dur = max(0.0, float(duration_ms))
    except Exception:
        return
    arr = _samples()
    arr.append(
        {
            "ts": time.time(),
            "event": str(event).strip().lower(),
            "dur_ms": dur,
            "ok": bool(ok),
        }
    )
    if len(arr) > _MAX_SAMPLES:
        del arr[: len(arr) - _MAX_SAMPLES]


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    i = (len(values) - 1) * max(0.0, min(1.0, p))
    lo = int(math.floor(i))
    hi = int(math.ceil(i))
    if lo == hi:
        return float(values[lo])
    return float(values[lo] + (values[hi] - values[lo]) * (i - lo))


def summarize_perf(window_seconds: int = 900) -> dict[str, dict]:
    now = time.time()
    window = max(60, int(window_seconds or 900))
    grouped: dict[str, list[dict]] = {}
    for row in _samples():
        if not isinstance(row, dict):
            continue
        if (now - float(row.get("ts", 0) or 0)) > window:
            continue
        ev = str(row.get("event", "")).strip().lower()
        if not ev:
            continue
        grouped.setdefault(ev, []).append(row)

    out: dict[str, dict] = {}
    for ev, rows in grouped.items():
        vals = sorted(float(r.get("dur_ms", 0.0) or 0.0) for r in rows)
        err = sum(1 for r in rows if not bool(r.get("ok", True)))
        out[ev] = {
            "count": len(rows),
            "errors": err,
            "p50_ms": round(_percentile(vals, 0.50), 1),
            "p95_ms": round(_percentile(vals, 0.95), 1),
            "max_ms": round(vals[-1], 1) if vals else 0.0,
        }
    return out

