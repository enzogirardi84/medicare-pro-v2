"""Cache de dos niveles (L1 local / L2 Redis) con invalidacion
via Redis Pub/Sub. Cuando una instancia invalida una clave,
transmite a todas las replicas para que destruyan su L1.
"""
from __future__ import annotations

import asyncio
import json
import os
import threading
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CACHE L1 LOCAL (LRU con TTL)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class L1Entry:
    """Entrada en la cache L1 local."""
    value: Any
    ttl: float
    stored_at: float = field(default_factory=time.time)

    def is_expired(self) -> bool:
        return time.time() - self.stored_at > self.ttl


class L1Cache:
    """Cache L1 local LRU con TTL por clave.

    Thread-safe para uso desde multiples corrutinas.
    TTL muy agresivo (segundos, no minutos) para evitar datos obsoletos.
    """

    def __init__(self, max_size: int = 10000, default_ttl: float = 5.0):
        self._store: OrderedDict[str, L1Entry] = OrderedDict()
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Obtiene valor de L1 si existe y no ha expirado.

        Actualiza el orden LRU en acceso.
        """
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                self._misses += 1
                return None

            if entry.is_expired():
                del self._store[key]
                self._misses += 1
                return None

            # Mover al final (mas recientemente usado)
            self._store.move_to_end(key)
            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None):
        """Almacena en L1 con TTL."""
        with self._lock:
            self._store[key] = L1Entry(value=value, ttl=ttl or self._default_ttl)
            self._store.move_to_end(key)

            # Eviccion LRU
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    def invalidate(self, key: str) -> bool:
        """Invalida una clave de L1."""
        with self._lock:
            if key in self._store:
                del self._store[key]
                return True
            return False

    def invalidate_pattern(self, pattern: str):
        """Invalida todas las claves que contengan un patron."""
        with self._lock:
            keys = [k for k in self._store if pattern in k]
            for k in keys:
                del self._store[k]

    def clear(self):
        with self._lock:
            self._store.clear()

    @property
    def stats(self) -> dict:
        with self._lock:
            return {
                "size": len(self._store),
                "max_size": self._max_size,
                "hits": self._hits,
                "misses": self._misses,
                "hit_ratio": round(self._hits / (self._hits + self._misses), 4)
                if (self._hits + self._misses) > 0 else 0.0,
            }


# ═══════════════════════════════════════════════════════════════════
# 2. CACHE L2 CENTRALIZADA (Redis)
# ═══════════════════════════════════════════════════════════════════

class L2Cache:
    """Cache L2 centralizada en Redis.

    TTL mas largo que L1 (minutos). Persistente entre instancias.
    """

    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asynced as aioredis
                self._redis = aioredis.Redis(
                    host=os.environ.get("REDIS_HOST", "localhost"),
                    port=int(os.environ.get("REDIS_PORT", "6379")),
                    db=6,
                    decode_responses=False,
                )
            except Exception:
                pass
        return self._redis

    async def get(self, key: str) -> Optional[bytes]:
        r = await self._get_redis()
        if not r:
            return None
        return await r.get(key)

    async def set(self, key: str, value: bytes, ttl: float = 60.0):
        r = await self._get_redis()
        if r:
            await r.setex(key, int(ttl), value)

    async def invalidate(self, key: str):
        r = await self._get_redis()
        if r:
            await r.delete(key)

    async def close(self):
        if self._redis:
            await self._redis.close()
            self._redis = None


# ═══════════════════════════════════════════════════════════════════
# 3. DISPATCHER UNIFICADO CON INVALIDATION BROADCAST
# ═══════════════════════════════════════════════════════════════════

class CacheDispatcher:
    """Despachador unificado de cache L1/L2 con invalidacion broadcast.

    Flujo de get:
    1. Busca en L1 (local, microsegundos)
    2. Si falla, busca en L2 (Redis, milisegundos)
    3. Si encuentra en L2, pobla L1 con TTL agresivo
    4. Si no encuentra, ejecuta fetch() y popula ambas

    Flujo de invalidacion:
    1. Elimina de L1 local
    2. Elimina de L2 (Redis)
    3. Publica evento en Redis Pub/Sub 'cache:invalidate:{key}'
    4. Otras instancias reciben el evento y eliminan de su L1
    """

    INVALIDATION_CHANNEL = "medicare:cache:invalidate"

    def __init__(self, instance_id: Optional[str] = None):
        self._l1 = L1Cache()
        self._l2 = L2Cache()
        self._instance_id = instance_id or str(uuid.uuid4().hex[:8])
        self._pubsub_task: Optional[asyncio.Task] = None
        self._fetch_fn: Optional[Callable] = None
        self._subscribed = False

    def set_fetch_function(self, fn: Callable):
        """Establece la funcion para poblar cache en miss.

        La funcion debe ser async y aceptar (key) -> value.
        """
        self._fetch_fn = fn

    async def get(self, key: str, ttl_l1: float = 5.0, ttl_l2: float = 60.0) -> Any:
        """Obtiene valor con busqueda L1 → L2 → fetch.

        Args:
            key: Clave de cache.
            ttl_l1: TTL en L1 (segundos, default 5).
            ttl_l2: TTL en L2 (segundos, default 60).

        Returns:
            Valor almacenado o None si no se encuentra/fetch falla.
        """
        # 1. L1
        value = self._l1.get(key)
        if value is not None:
            return value

        # 2. L2 (serializado como JSON)
        raw = await self._l2.get(key)
        if raw is not None:
            value = json.loads(raw)
            self._l1.set(key, value, ttl=ttl_l1)
            return value

        # 3. Fetch
        if self._fetch_fn:
            value = await self._fetch_fn(key)
            if value is not None:
                self._l1.set(key, value, ttl=ttl_l1)
                await self._l2.set(key, json.dumps(value, default=str).encode(), ttl=ttl_l2)
            return value

        return None

    async def set(self, key: str, value: Any, ttl_l1: float = 5.0,
                  ttl_l2: float = 60.0):
        """Almacena en L1 y L2."""
        self._l1.set(key, value, ttl=ttl_l1)
        await self._l2.set(key, json.dumps(value, default=str).encode(), ttl=ttl_l2)

    async def invalidate(self, key: str):
        """Invalida en L1 local, L2, y broadcast a otras instancias.

        Esto asegura que TODAS las instancias de FastAPI en todos los pods
        destruyan su cache L1 para esta clave inmediatamente.
        """
        # 1. L1 local
        self._l1.invalidate(key)

        # 2. L2 (Redis)
        await self._l2.invalidate(key)

        # 3. Broadcast a otras instancias via Redis Pub/Sub
        await self._broadcast_invalidation(key)

        log_event("cache", f"invalidated:{key}")

    async def invalidate_pattern(self, pattern: str):
        """Invalida por patron en L1 y broadcast."""
        self._l1.invalidate_pattern(pattern)

        # Broadcast del patron (las instancias reciben y barren su L1)
        await self._broadcast_invalidation(f"pattern:{pattern}")

        log_event("cache", f"invalidated_pattern:{pattern}")

    # ── Invalidation Broadcast ─────────────────────────────

    async def _broadcast_invalidation(self, key: str):
        """Publica evento de invalidacion en Redis Pub/Sub."""
        try:
            import redis.asynced as aioredis
            r = aioredis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                db=6,
                decode_responses=True,
            )
            payload = json.dumps({
                "key": key,
                "instance_id": self._instance_id,
                "timestamp": time.time(),
            })
            await r.publish(self.INVALIDATION_CHANNEL, payload)
            await r.close()
        except Exception:
            pass

    async def subscribe_to_invalidations(self):
        """Se suscribe al canal de invalidaciones.

        Escucha eventos de otras instancias e invalida su L1 local.
        Debe llamarse una vez al iniciar la aplicacion.
        """
        if self._subscribed:
            return
        self._subscribed = True

        if self._pubsub_task is None or self._pubsub_task.done():
            self._pubsub_task = asyncio.create_task(self._invalidation_listener())

    async def _invalidation_listener(self):
        """Loop que escucha invalidaciones de otras instancias."""
        try:
            import redis.asynced as aioredis
            r = aioredis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                db=6,
                decode_responses=True,
            )
            pubsub = r.pubsub()
            await pubsub.subscribe(self.INVALIDATION_CHANNEL)

            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                try:
                    data = json.loads(message["data"])
                    # Ignorar nuestras propias invalidaciones
                    if data.get("instance_id") == self._instance_id:
                        continue

                    key = data.get("key", "")
                    if key.startswith("pattern:"):
                        self._l1.invalidate_pattern(key[8:])
                    else:
                        self._l1.invalidate(key)

                    log_event("cache", f"remote_invalidation:{key}:from={data.get('instance_id','?')}")
                except Exception as exc:
                    log_event("cache", f"invalidation_parse_error:{type(exc).__name__}")

        except Exception as exc:
            log_event("cache", f"invalidation_listener_error:{type(exc).__name__}")

    # ── Stats ──────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "l1": self._l1.stats,
            "instance_id": self._instance_id,
        }

    async def close(self):
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except (asyncio.CancelledError, RuntimeError):
                pass
        await self._l2.close()


__all__ = [
    "CacheDispatcher",
    "L1Cache",
    "L2Cache",
]
