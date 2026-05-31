"""Cache inteligente multi-tenant con Redis o LRU local.
Invalida por UPDATE/DELETE respetando aislamiento entre tenants.
"""
from __future__ import annotations

import json
import os
import time
from collections import OrderedDict
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. LRU CACHE LOCAL (fallback cuando no hay Redis)
# ═══════════════════════════════════════════════════════════════════

class LRUCache:
    """Cache LRU en memoria con TTL por clave.

    Usa OrderedDict para mantener orden de acceso.
    Invalida automaticamente cuando expira el TTL.
    """

    def __init__(self, maxsize: int = 1000, ttl: int = 300):
        self._cache: OrderedDict = OrderedDict()
        self._ttl: dict[str, float] = {}
        self._maxsize = maxsize
        self._default_ttl = ttl

    def get(self, key: str) -> Optional[Any]:
        if key not in self._cache:
            return None
        # Verificar TTL
        if time.time() > self._ttl.get(key, 0):
            self._cache.pop(key, None)
            self._ttl.pop(key, None)
            return None
        # Mover al final (mas recientemente usado)
        self._cache.move_to_end(key)
        return self._cache[key]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        if len(self._cache) >= self._maxsize:
            self._cache.popitem(last=False)  # Eliminar LRU
        self._cache[key] = value
        self._ttl[key] = time.time() + (ttl or self._default_ttl)

    def invalidate(self, pattern: str) -> int:
        """Invalida claves que contengan el patron.

        Retorna cantidad de claves invalidadas.
        """
        keys = [k for k in self._cache if pattern in k]
        for k in keys:
            self._cache.pop(k, None)
            self._ttl.pop(k, None)
        return len(keys)

    def clear(self) -> None:
        self._cache.clear()
        self._ttl.clear()


# ═══════════════════════════════════════════════════════════════════
# 2. TENANT CACHE (Redis / LRU)
# ═══════════════════════════════════════════════════════════════════

class TenantCache:
    """Cache multi-tenant con Redis o fallback LRU.

    Las claves incluyen tenant_id para aislamiento.
    Invalida automaticamente al hacer UPDATE/DELETE.

    Uso:
        cache = TenantCache()
        await cache.set(f"paciente:{tenant}:{id}", data)
        data = await cache.get(f"paciente:{tenant}:{id}")
        await cache.invalidate_tenant(tenant)
    """

    def __init__(self):
        self._redis = None
        self._lru = LRUCache(maxsize=2000, ttl=300)
        self._init_redis()

    def _init_redis(self) -> None:
        try:
            import redis.asyncio as aioredis
            self._redis = aioredis.Redis(
                host=os.environ.get("REDIS_HOST", "localhost"),
                port=int(os.environ.get("REDIS_PORT", "6379")),
                db=1,
                decode_responses=True,
                socket_timeout=2,
            )
            log_event("cache", "Redis conectado")
        except Exception as exc:
            log_event("cache", f"Redis no disponible: {exc}. Usando LRU local.")

    async def get(self, key: str) -> Optional[Any]:
        if self._redis:
            try:
                data = await self._redis.get(key)
                return json.loads(data) if data else None
            except Exception:
                pass
        return self._lru.get(key)

    async def set(self, key: str, value: Any, ttl: int = 300) -> None:
        if self._redis:
            try:
                await self._redis.setex(key, ttl, json.dumps(value, default=str))
                return
            except Exception:
                pass
        self._lru.set(key, value, ttl)

    async def invalidate(self, pattern: str) -> int:
        """Invalida claves por patron."""
        count = 0
        if self._redis:
            try:
                cursor = 0
                while True:
                    cursor, keys = await self._redis.scan(cursor, match=f"*{pattern}*", count=100)
                    if keys:
                        count += await self._redis.delete(*keys)
                    if cursor == 0:
                        break
            except Exception:
                pass
        count += self._lru.invalidate(pattern)
        return count

    async def invalidate_tenant(self, tenant_id: str) -> None:
        """Invalida TODO el cache de un tenant (cuando cambian datos masivos)."""
        await self.invalidate(f":{tenant_id}:")
        log_event("cache", f"Cache invalidado para tenant {tenant_id}")


# Instancia global
_cache: Optional[TenantCache] = None


def get_cache() -> TenantCache:
    global _cache
    if _cache is None:
        _cache = TenantCache()
    return _cache
