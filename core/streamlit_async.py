"""Patron async para Streamlit sin bloqueos de UI.
Usa @st.fragment + asyncio para llamadas a PostgreSQL.
Solo recarga el fragmento especifico, no toda la pagina.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Callable, Optional

import streamlit as st

from core.app_logging import log_event
from core.tenant_cache import get_cache


def run_async(coro: Any) -> Any:
    """Ejecuta una coroutine async desde codigo sync (Streamlit).

    Streamlit es sincrono, pero podemos ejectuar async usando
    asyncio.run() en un hilo separado para no bloquear la UI.
    """
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # Ya hay un loop corriendo (FastAPI/compatibilidad)
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as pool:
                future = pool.submit(asyncio.run, coro)
                return future.result(timeout=30)
        else:
            return asyncio.run(coro)
    except Exception as exc:
        log_event("async_ui", f"error:{type(exc).__name__}:{exc}")
        return None


@st.fragment
def render_fragment_with_data(
    fragment_id: str,
    fetch_fn: Callable,
    render_fn: Callable,
    ttl_seconds: int = 60,
    **kwargs: Any,
) -> None:
    """Fragmento que carga datos async y renderiza solo este bloque.

    El fragmento se recarga CADA VEZ que Streamlit re-ejecuta,
    pero los datos se sirven desde cache (Redis/LRU) si estan
    vigentes. No bloquea otros fragmentos ni la sidebar.

    Args:
        fragment_id: ID unico para cache (ej. "mapa_gps_dashboard").
        fetch_fn: Funcion async que trae datos (ej. repo.fetch_all).
        render_fn: Funcion sync que renderiza en Streamlit.
        ttl_seconds: TTL del cache en segundos.
        **kwargs: Argumentos para fetch_fn.
    """
    placeholder = st.empty()
    with placeholder:
        st.caption("Cargando...")

    cache = get_cache()

    # Intentar cache primero
    cached = run_async(cache.get(fragment_id))
    if cached is not None:
        placeholder.empty()
        with placeholder:
            render_fn(cached)
        return

    # Si no hay cache, ejecutar fetch async
    t0 = time.perf_counter()
    data = run_async(fetch_fn(**kwargs))
    dt = (time.perf_counter() - t0) * 1000

    if data is not None:
        # Guardar en cache para proximos renders
        run_async(cache.set(fragment_id, data, ttl=ttl_seconds))
        placeholder.empty()
        with placeholder:
            render_fn(data)
        log_event("async_ui", f"{fragment_id}:{dt:.0f}ms")
    else:
        placeholder.empty()
        with placeholder:
            st.warning(f"No se pudieron cargar datos ({fragment_id})")
