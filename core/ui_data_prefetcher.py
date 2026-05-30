"""Pre-cargador asincrono de datos en segundo plano para cero latency.
Usa concurrent.futures.ThreadPoolExecutor para anticipar consultas
a la base de datos mientras el usuario navega.
Los datos se depositan en st.session_state para consumo inmediato.
"""
from __future__ import annotations

import concurrent.futures
import time
from typing import Any, Callable, Optional

import streamlit as st

from core.app_logging import log_event


class DataPrefetcher:
    """Pre-carga datos de modulos adyacentes en segundo plano.

    Mientras el usuario navega por la app, el prefetcher ejecuta
    consultas de los modulos vecinos en hilos separados y deposita
    los resultados en st.session_state para acceso instantaneo.

    Uso:
        prefetcher = DataPrefetcher()
        prefetcher.prefetch_modulo("Inventario", mi_empresa="test")
    """

    _POOL = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    _PREFETCHED_KEY = "_mc_prefetched_data"
    _TTL = 120  # segundos

    def __init__(self):
        self._futures: dict[str, concurrent.futures.Future] = {}

    # ─── Pre-carga de modulo especifico ────────────────────

    def prefetch_modulo(
        self,
        nombre_modulo: str,
        fetch_fn: Callable,
        **kwargs: Any,
    ) -> None:
        """Dispara pre-carga de datos de un modulo en segundo plano.

        Args:
            nombre_modulo: Nombre del modulo (ej. "Inventario").
            fetch_fn: Funcion que retorna los datos del modulo.
            **kwargs: Argumentos para fetch_fn.
        """
        # No prefetchear si ya esta cacheado y vigente
        cached = self._get_cache(nombre_modulo)
        if cached is not None:
            return

        future = self._POOL.submit(self._ejecutar_fetch, nombre_modulo, fetch_fn, **kwargs)
        self._futures[nombre_modulo] = future
        log_event("prefetcher", f"disparado:{nombre_modulo}")

    def _ejecutar_fetch(
        self, nombre: str, fn: Callable, **kwargs: Any
    ) -> None:
        """Ejecuta la consulta en el hilo y cachea el resultado."""
        try:
            t0 = time.perf_counter()
            resultado = fn(**kwargs)
            dt = (time.perf_counter() - t0) * 1000

            # Almacenar en session_state
            cache = st.session_state.setdefault(self._PREFETCHED_KEY, {})
            cache[nombre] = {
                "data": resultado,
                "timestamp": time.time(),
                "ttl": self._TTL,
            }
            log_event("prefetcher", f"completado:{nombre}:{dt:.0f}ms")
        except Exception as exc:
            log_event("prefetcher", f"fallo:{nombre}:{type(exc).__name__}:{exc}")

    # ─── Consumo de datos pre-cacheados ────────────────────

    def consumir(self, nombre_modulo: str) -> Optional[Any]:
        """Consume datos pre-cacheados de un modulo.

        Returns:
            Datos cacheados, o None si no estan disponibles.
        """
        cached = self._get_cache(nombre_modulo)
        if cached is not None:
            log_event("prefetcher", f"cache_hit:{nombre_modulo}")
            return cached
        return None

    def _get_cache(self, nombre: str) -> Optional[Any]:
        """Obtiene datos cacheados si estan vigentes."""
        cache = st.session_state.get(self._PREFETCHED_KEY, {})
        entry = cache.get(nombre)
        if entry is None:
            return None
        edad = time.time() - entry.get("timestamp", 0)
        if edad > entry.get("ttl", self._TTL):
            del cache[nombre]
            return None
        return entry.get("data")

    def limpiar_cache(self, nombre: str | None = None) -> None:
        """Limpia cache de un modulo o todos."""
        cache = st.session_state.get(self._PREFETCHED_KEY, {})
        if nombre:
            cache.pop(nombre, None)
        else:
            st.session_state[self._PREFETCHED_KEY] = {}

    # ─── Pre-carga predictiva basada en navegacion ─────────

    def prefetch_vecinos(
        self,
        modulo_actual: str,
        mapa_vecinos: dict[str, list[str]],
        fetch_fns: dict[str, Callable],
    ) -> None:
        """Pre-carga datos de modulos vecinos (navegacion predictiva).

        Args:
            modulo_actual: Modulo actualmente activo.
            mapa_vecinos: Dict {modulo: [vecinos]}.
            fetch_fns: Dict {modulo: funcion_fetch}.
        """
        vecinos = mapa_vecinos.get(modulo_actual, [])
        for vecino in vecinos:
            if vecino in fetch_fns:
                self.prefetch_modulo(vecino, fetch_fns[vecino])


# Instancia global
_prefetcher: DataPrefetcher | None = None


def get_prefetcher() -> DataPrefetcher:
    global _prefetcher
    if _prefetcher is None:
        _prefetcher = DataPrefetcher()
    return _prefetcher
