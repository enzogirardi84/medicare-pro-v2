"""Object Pooling, GC Hardening y reutilizacion de buffers para
mitigar fragmentacion de memoria y pausas Stop-The-World en
rutas criticas (sync/batch, WebSockets, shadow traffic).
"""
from __future__ import annotations

import gc
import threading
from collections import deque
from typing import Any, Callable, Optional


# ═══════════════════════════════════════════════════════════════════
# 1. GARBAGE COLLECTOR HARDENING
# ═══════════════════════════════════════════════════════════════════

class GCSettings:
    """Ajustes del GC de Python para rutas criticas.

    Deshabilita temporalmente el GC generacional en funciones
    de sincronizacion donde las pausas Stop-The-World no son tolerables.
    """

    @staticmethod
    def disable_in_critical_section(func: Callable) -> Callable:
        """Decorador: deshabilita GC durante la ejecucion, lo restaura al salir.

        Uso:
            @GCSettings.disable_in_critical_section
            async def process_sync_batch(self, payload):
                ...
        """
        from functools import wraps

        @wraps(func)
        def wrapper(*args, **kwargs):
            was_enabled = gc.isenabled()
            if was_enabled:
                gc.disable()
            try:
                return func(*args, **kwargs)
            finally:
                if was_enabled and not gc.isenabled():
                    gc.enable()

        return wrapper

    @staticmethod
    def tune_for_high_throughput():
        """Ajusta umbrales del GC para entornos de alta concurrencia.

        - Aumenta umbral de generacion 0 para reducir frecuencia de colecciones
        - Deshabilita coleccion de generacion 2 (mas costosa)
        """
        gc.set_threshold(100000, 50, 50)  # gen0: 100k objetos (default 7000)
        # No deshabilitar gen2 completamente, solo espaciar

    @staticmethod
    def collect_generational(gen: int = 2):
        """Ejecuta coleccion manual de una generacion especifica."""
        if gen == 0:
            gc.collect(0)
        elif gen == 1:
            gc.collect(1)
        else:
            gc.collect(2)


# ═══════════════════════════════════════════════════════════════════
# 2. OBJECT POOL — Reutilizacion de estructuras
# ═══════════════════════════════════════════════════════════════════

class ObjectPool:
    """Pool de objetos reutilizables para mitigar allocacion en caliente.

    Soporta any tipo de objeto. Los objetos se 'prestan' y 'devuelven'
    al pool. Si el pool esta vacio, se crea uno nuevo con la factory.

    Uso:
        pool = ObjectPool.factory(dict, prealloc=100)
        d = pool.borrow()
        d["key"] = "value"
        # ... usar ...
        pool.reset_and_return(d)  # limpia y devuelve
    """

    def __init__(self, factory: Callable[[], Any], prealloc: int = 0):
        self._factory = factory
        self._pool: deque = deque()
        self._max_size = prealloc * 2
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

        # Pre-asignar objetos
        for _ in range(prealloc):
            self._pool.append(self._factory())

    @classmethod
    def factory(cls, factory: Callable[[], Any], prealloc: int = 0) -> ObjectPool:
        """Crea un pool con una factory."""
        return cls(factory, prealloc)

    def borrow(self) -> Any:
        """Toma prestado un objeto del pool."""
        with self._lock:
            if self._pool:
                self._hits += 1
                return self._pool.popleft()
            self._misses += 1
        return self._factory()

    def reset_and_return(self, obj: Any):
        """Limpia y devuelve un objeto al pool.

        Para dicts: .clear()
        Para listas: .clear()
        Para otros: se descarta si no se puede resetear.
        """
        self._try_reset(obj)
        with self._lock:
            if len(self._pool) < self._max_size:
                self._pool.append(obj)

    @staticmethod
    def _try_reset(obj: Any):
        """Intenta resetear un objeto a su estado inicial."""
        if isinstance(obj, dict):
            obj.clear()
        elif isinstance(obj, list):
            obj.clear()
        elif isinstance(obj, set):
            obj.clear()
        # Para otros tipos, se devuelve tal cual

    @property
    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._pool),
                "hits": self._hits,
                "misses": self._misses,
                "hit_ratio": round(self._hits / (self._hits + self._misses), 4)
                if (self._hits + self._misses) > 0 else 0.0,
                "max_size": self._max_size,
            }


# ═══════════════════════════════════════════════════════════════════
# 3. BUFFER DE MESSAGEPACK REUTILIZABLE
# ═══════════════════════════════════════════════════════════════════

class MsgPackBuffer:
    """Buffer reutilizable para serializacion/deserializacion MessagePack.

    Evita crear bytes objects nuevos en cada operacion de sync.
    NO es thread-safe (usar un buffer por corrutina/fibra).
    """

    __slots__ = ("_buffer", "_pool", "_size")

    def __init__(self, initial_size: int = 4096):
        self._buffer = bytearray(initial_size)
        self._size = initial_size
        self._pool: Optional[ObjectPool] = None

    def resize(self, needed: int):
        """Redimensiona el buffer si es necesario (sin re-asignar si ya es suficientemente grande)."""
        if needed > self._size:
            # Crecimiento geometrico: duplicar hasta cubrir
            new_size = self._size
            while new_size < needed:
                new_size *= 2
            self._buffer = bytearray(new_size)
            self._size = new_size

    def pack(self, obj: Any) -> bytes:
        """Empaqueta objeto a MessagePack usando el buffer interno.

        Returns:
            bytes del objeto empaquetado (parte del buffer).
        """
        import msgpack
        packed = msgpack.packb(obj, use_bin_type=True)
        self.resize(len(packed))
        self._buffer[:len(packed)] = packed
        return bytes(self._buffer[:len(packed)])

    def unpack(self, data: bytes) -> Any:
        """Desempaca MessagePack desde bytes."""
        import msgpack
        return msgpack.unpackb(data, raw=False)

    def clear(self):
        """Limpia el buffer (solo reinicia punteros, no libera memoria)."""
        pass  # el buffer se reescribe en el proximo pack

    @property
    def capacity(self) -> int:
        return self._size


# ═══════════════════════════════════════════════════════════════════
# 4. POOLS GLOBALES PREDEFINIDOS
# ═══════════════════════════════════════════════════════════════════

# Pool de dicts para payloads transformados en sync/batch
payload_dict_pool = ObjectPool.factory(dict, prealloc=100)

# Pool de listas para batches de eventos
event_list_pool = ObjectPool.factory(list, prealloc=50)

# Pool de buffers MessagePack (uno por hilo)
_thread_local_buffers: dict[int, MsgPackBuffer] = {}


def get_thread_buffer() -> MsgPackBuffer:
    """Obtiene o crea un buffer MsgPack para el hilo actual."""
    tid = threading.get_ident()
    if tid not in _thread_local_buffers:
        _thread_local_buffers[tid] = MsgPackBuffer(initial_size=8192)
    return _thread_local_buffers[tid]


__all__ = [
    "GCSettings",
    "ObjectPool",
    "MsgPackBuffer",
    "payload_dict_pool",
    "event_list_pool",
    "get_thread_buffer",
]
