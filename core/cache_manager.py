"""
Sistema de caché multi-nivel para millones de usuarios.

- L1: Caché en memoria por sesión (más rápido, volátil)
- L2: Caché compartida por tenant (persistente en session_state)
- TTL automático y evicción LRU
- Invalidación selectiva por patrones
"""

from __future__ import annotations

import hashlib
import json
import threading
import time
from dataclasses import dataclass, field
from functools import wraps
from typing import Any, Callable, Dict, Optional, Tuple

import streamlit as st

from core.app_logging import log_event


@dataclass
class CacheEntry:
    """Entrada de caché con metadatos."""
    value: Any
    created_at: float = field(default_factory=time.time)
    ttl_seconds: float = 60.0
    access_count: int = 0
    last_access: float = field(default_factory=time.time)
    size_bytes: int = 0

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds

    def touch(self):
        self.access_count += 1
        self.last_access = time.time()


class TieredCacheManager:
    """
    Gestor de caché multi-nivel optimizado para alta concurrencia.

    L1: Memoria local (más rápido)
    L2: session_state compartido (persistente durante sesión)
    """

    def __init__(
        self,
        max_l1_entries: int = 100,
        max_l2_entries: int = 1000,
        default_ttl: float = 60.0,
        cleanup_interval: float = 60.0,
    ):
        self.max_l1 = max_l1_entries
        self.max_l2 = max_l2_entries
        self.default_ttl = default_ttl
        self.cleanup_interval = cleanup_interval

        self._l1_cache: Dict[str, CacheEntry] = {}
        self._lock = threading.RLock()
        self._last_cleanup = time.time()
        self._hit_count = 0
        self._miss_count = 0
        self._eviction_count = 0
        self._current_bytes = 0  # contador simple, actualizado en set()
        self._memory_limit_bytes = 150 * 1024 * 1024  # 150 MB

    def _estimate_object_size(self, obj) -> int:
        """Estimate memory size — simple sys.getsizeof, no recursion (evitaba O(n*m) por lectura)."""
        if obj is None:
            return 0
        try:
            import sys
            return sys.getsizeof(obj)
        except Exception:
            return 0

    def _estimate_cache_size_bytes(self) -> int:
        """Estimate total memory usage — cuenta L1 entries sin recursion."""
        total = self._current_bytes  # contador actualizado en set()
        return int(total)

    def _maybe_enforce_memory_limit(self) -> None:
        """Evict caches if memory usage exceeds the configured limit."""
        try:
            if self._current_bytes <= self._memory_limit_bytes:
                return
            self._l1_cache.clear()
            st.session_state["_tiered_cache_l2"] = {}
            self._current_bytes = 0
            self._eviction_count += 1
            log_event("cache_memory_cleanup", "cleared l1/l2")
        except Exception as _exc:
            log_event("cache_manager_cleanup", f"fallo_cleanup_memoria:{type(_exc).__name__}:{_exc}")

    def _generate_key(
        self,
        prefix: str,
        tenant_key: str,
        *args,
        **kwargs
    ) -> str:
        """Genera clave de caché determinística."""
        key_data = json.dumps({
            "prefix": prefix,
            "tenant": tenant_key,
            "args": args,
            "kwargs": sorted(kwargs.items()),
        }, sort_keys=True, default=str)
        return f"{prefix}:{tenant_key}:{hashlib.md5(key_data.encode()).hexdigest()[:16]}"

    def _cleanup_expired(self):
        """Timer-based cleanup (se llama desde set(), no desde get())."""
        if time.time() - self._last_cleanup < self.cleanup_interval:
            return
        with self._lock:
            expired_l1 = [k for k, v in self._l1_cache.items() if v.is_expired()]
            for k in expired_l1:
                del self._l1_cache[k]
            l2 = st.session_state.get("_tiered_cache_l2", {})
            if isinstance(l2, dict):
                expired_l2 = [k for k, v in l2.items() if isinstance(v, CacheEntry) and v.is_expired()]
                for k in expired_l2:
                    del l2[k]
                if expired_l2:
                    st.session_state["_tiered_cache_l2"] = l2
            self._last_cleanup = time.time()

    def _evict_l1_lru(self):
        """Evicción LRU cuando L1 está lleno."""
        if len(self._l1_cache) < self.max_l1:
            return

        with self._lock:
            # Encontrar entrada menos usada recientemente
            oldest = min(
                self._l1_cache.items(),
                key=lambda x: (x[1].access_count, x[1].last_access)
            )
            del self._l1_cache[oldest[0]]
            self._eviction_count += 1

    def _evict_l2_lru(self):
        """Evicción LRU para L2."""
        l2_cache = st.session_state.get("_tiered_cache_l2", {})
        if len(l2_cache) < self.max_l2:
            return

        if not isinstance(l2_cache, dict):
            return

        # Encontrar entrada menos usada
        oldest = min(
            l2_cache.items(),
            key=lambda x: (x[1].access_count, x[1].last_access)
            if isinstance(x[1], CacheEntry) else (0, 0)
        )
        del l2_cache[oldest[0]]
        st.session_state["_tiered_cache_l2"] = l2_cache

    def get(
        self,
        prefix: str,
        tenant_key: str,
        key_suffix: Optional[str] = None,
        use_l1: bool = True,
        use_l2: bool = True,
    ) -> Tuple[bool, Any]:
        """
        Obtiene valor de caché.
        Retorna (hit, value).
        """
        key = self._generate_key(prefix, tenant_key, key_suffix) if key_suffix else f"{prefix}:{tenant_key}"

        # Intentar L1 primero
        if use_l1:
            with self._lock:
                entry = self._l1_cache.get(key)
                if entry and not entry.is_expired():
                    entry.touch()
                    self._hit_count += 1
                    return True, entry.value

        # Intentar L2
        if use_l2:
            l2_cache = st.session_state.get("_tiered_cache_l2", {})
            if isinstance(l2_cache, dict):
                entry = l2_cache.get(key)
                if isinstance(entry, CacheEntry) and not entry.is_expired():
                    entry.touch()
                    # Promover a L1 si hay espacio
                    if len(self._l1_cache) < self.max_l1:
                        with self._lock:
                            self._l1_cache[key] = entry
                    self._hit_count += 1
                    return True, entry.value

        self._miss_count += 1
        return False, None

    def set(
        self,
        prefix: str,
        tenant_key: str,
        value: Any,
        key_suffix: Optional[str] = None,
        ttl_seconds: Optional[float] = None,
        use_l1: bool = True,
        use_l2: bool = True,
        size_bytes: int = 0,
    ):
        """
        Almacena valor en caché.
        """
        key = self._generate_key(prefix, tenant_key, key_suffix) if key_suffix else f"{prefix}:{tenant_key}"
        ttl = ttl_seconds or self.default_ttl

        entry = CacheEntry(
            value=value,
            ttl_seconds=ttl,
            size_bytes=size_bytes,
        )

        # Almacenar en L1
        if use_l1:
            self._evict_l1_lru()
            with self._lock:
                self._l1_cache[key] = entry

        # Almacenar en L2
        if use_l2:
            self._evict_l2_lru()
            if "_tiered_cache_l2" not in st.session_state:
                st.session_state["_tiered_cache_l2"] = {}
            st.session_state["_tiered_cache_l2"][key] = entry

        # Cleanup timer-based (solo en escritura)
        self._cleanup_expired()
        # Trackeo simple de bytes (sin recursion)
        self._current_bytes += size_bytes or self._estimate_object_size(value)
        if self._current_bytes > self._memory_limit_bytes:
            self._maybe_enforce_memory_limit()

    def invalidate(
        self,
        prefix: Optional[str] = None,
        tenant_key: Optional[str] = None,
        pattern: Optional[str] = None,
    ):
        """
        Invalida entradas de caché por criterios.

        - prefix: invalida todas las entradas con este prefijo
        - tenant_key: invalida todas las entradas de este tenant
        - pattern: invalida entradas cuya clave contenga el patrón
        """
        with self._lock:
            to_remove_l1 = []
            for key in self._l1_cache.keys():
                should_remove = False
                if prefix and key.startswith(f"{prefix}:"):
                    should_remove = True
                if tenant_key and f":{tenant_key}:" in key:
                    should_remove = True
                if pattern and pattern in key:
                    should_remove = True
                if should_remove:
                    to_remove_l1.append(key)

            for key in to_remove_l1:
                del self._l1_cache[key]

        # Invalidar L2
        l2_cache = st.session_state.get("_tiered_cache_l2", {})
        if isinstance(l2_cache, dict):
            to_remove_l2 = []
            for key in l2_cache.keys():
                should_remove = False
                if prefix and key.startswith(f"{prefix}:"):
                    should_remove = True
                if tenant_key and f":{tenant_key}:" in key:
                    should_remove = True
                if pattern and pattern in key:
                    should_remove = True
                if should_remove:
                    to_remove_l2.append(key)

            for key in to_remove_l2:
                del l2_cache[key]

            st.session_state["_tiered_cache_l2"] = l2_cache

        log_event("cache", f"invalidated:{len(to_remove_l1)}_l1,{len(to_remove_l2)}_l2")

    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del caché."""
        total = self._hit_count + self._miss_count
        hit_rate = self._hit_count / total if total > 0 else 0

        l2_cache = st.session_state.get("_tiered_cache_l2", {})
        l2_size = len(l2_cache) if isinstance(l2_cache, dict) else 0

        return {
            "l1_entries": len(self._l1_cache),
            "l2_entries": l2_size,
            "hits": self._hit_count,
            "misses": self._miss_count,
            "hit_rate": round(hit_rate, 4),
            "evictions": self._eviction_count,
            "max_l1": self.max_l1,
            "max_l2": self.max_l2,
        }

    def clear(self):
        """Limpia todo el caché."""
        with self._lock:
            self._l1_cache.clear()
        st.session_state["_tiered_cache_l2"] = {}
        log_event("cache", "cleared")


def cached(
    prefix: str,
    tenant_key_arg: str = "tenant_key",
    ttl_seconds: float = 60.0,
    use_l1: bool = True,
    use_l2: bool = True,
):
    """
    Decorador para cachear resultados de funciones.

    Uso:
        @cached(prefix="pacientes", ttl_seconds=120)
        def obtener_pacientes(tenant_key, filtro=None):
            return db.query(...)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Extraer tenant_key de args o kwargs
            tenant_key = kwargs.get(tenant_key_arg)
            if tenant_key is None and args:
                # Asumir que tenant_key es el primer argumento posicional
                tenant_key = args[0]

            if not tenant_key:
                # Sin tenant_key, ejecutar sin caché
                return func(*args, **kwargs)

            cache = get_cache_manager()

            # Generar clave basada en argumentos
            key_data = json.dumps({
                "args": args[1:] if args else [],  # Excluir tenant_key
                "kwargs": {k: v for k, v in kwargs.items() if k != tenant_key_arg},
            }, sort_keys=True, default=str)

            # Intentar obtener de caché
            hit, value = cache.get(prefix, tenant_key, key_data, use_l1, use_l2)
            if hit:
                return value

            # Ejecutar función
            result = func(*args, **kwargs)

            # Almacenar en caché
            cache.set(prefix, tenant_key, result, key_data, ttl_seconds, use_l1, use_l2)

            return result
        return wrapper
    return decorator


# Singleton global
_cache_instance: Optional[TieredCacheManager] = None
_cache_lock = threading.Lock()


def get_cache_manager() -> TieredCacheManager:
    """Obtiene la instancia global del gestor de caché."""
    global _cache_instance
    if _cache_instance is None:
        with _cache_lock:
            if _cache_instance is None:
                _cache_instance = TieredCacheManager()
    return _cache_instance


def invalidate_cache(
    prefix: Optional[str] = None,
    tenant_key: Optional[str] = None,
    pattern: Optional[str] = None,
):
    """Invalida entradas de caché globalmente."""
    cache = get_cache_manager()
    cache.invalidate(prefix, tenant_key, pattern)


def get_cache_stats() -> Dict[str, Any]:
    """Obtiene estadísticas globales del caché."""
    cache = get_cache_manager()
    return cache.get_stats()
