"""Helpers para cachear vistas computadas en session_state.

Evita recalcular filtros (list comprehensions) en cada rerun cuando los datos
no han cambiado. Usa el id() de la lista origen como firma de cache.
"""
from __future__ import annotations

import time
from typing import Any, Callable, List

import streamlit as st


def cached_computed(key: str, data_ref: list, ttl: float = 2.0, compute_fn: Callable = None) -> Any:
    """Cachea el resultado de compute_fn() mientras data_ref no cambie y no expire el TTL.

    Uso:
        resultados = cached_computed("dash_pacientes_hoy", pacientes_db, ttl=2.0,
                                     compute_fn=lambda: [p for p in pacientes_db ...])
    """
    cache_key = f"_cc_{key}"
    sig_key = f"_cc_sig_{key}"
    ts_key = f"_cc_ts_{key}"

    data_sig = str(id(data_ref))
    now = time.monotonic()

    cached_val = st.session_state.get(cache_key)
    cached_sig = st.session_state.get(sig_key, "")
    cached_ts = st.session_state.get(ts_key, 0.0)

    if cached_val is not None and cached_sig == data_sig and (now - cached_ts) < ttl:
        return cached_val

    if compute_fn is None:
        return None

    result = compute_fn()
    st.session_state[cache_key] = result
    st.session_state[sig_key] = data_sig
    st.session_state[ts_key] = now
    return result


def invalidate_computed(key: str) -> None:
    """Invalida un cache especifico."""
    ts_key = f"_cc_ts_{key}"
    st.session_state[ts_key] = 0.0


def invalidate_all_computed() -> None:
    """Invalida todos los caches computados (forzar refresco completo)."""
    for k in list(st.session_state.keys()):
        if k.startswith("_cc_ts_"):
            st.session_state[k] = 0.0
