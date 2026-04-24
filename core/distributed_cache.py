"""
Caché Distribuido con Redis para Medicare Pro.

Características:
- Caché compartida entre múltiples instancias
- Caché de sesiones distribuida
- Invalidación por eventos/pub-sub
- TTL automático
- Circuit breaker para Redis no disponible
- Fallback a caché local (LRU)
"""

from __future__ import annotations

import hashlib
import json
import pickle
import time
from contextlib import contextmanager
from dataclasses import dataclass
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Union
from enum import Enum, auto

from core.connection_pool import CircuitBreaker
from core.app_logging import log_event


# Intentar importar Redis
REDIS_AVAILABLE = False
try:
    import redis
    from redis.exceptions import RedisError, ConnectionError as RedisConnectionError
    REDIS_AVAILABLE = True
except ImportError:
    pass


class CacheStrategy(Enum):
    """Estrategias de caché disponibles."""
    REDIS = auto()           # Caché distribuida Redis
    LOCAL = auto()           # Caché local LRU
    HYBRID = auto()          # Redis + Local (L1 + L2)


@dataclass
class CacheEntry:
    """Entrada de caché con metadatos."""
    key: str
    value: Any
    ttl: int  # segundos
    created_at: float
    tags: List[str]
    
    def is_expired(self) -> bool:
        """Verifica si la entrada expiró."""
        return time.time() > self.created_at + self.ttl


class LocalLRUCache:
    """Caché local en memoria con política LRU."""
    
    def __init__(self, maxsize: int = 1000):
        self.maxsize = maxsize
        self._cache: Dict[str, CacheEntry] = {}
        self._access_order: List[str] = []
    
    def get(self, key: str) -> Optional[Any]:
        """Obtiene valor si existe y no expiró."""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        if entry.is_expired():
            self.delete(key)
            return None
        
        # Actualizar orden LRU
        self._access_order.remove(key)
        self._access_order.append(key)
        
        return entry.value
    
    def set(self, key: str, value: Any, ttl: int = 300, tags: Optional[List[str]] = None):
        """Guarda valor en caché."""
        # Evict si necesario
        while len(self._cache) >= self.maxsize and self._access_order:
            oldest = self._access_order.pop(0)
            del self._cache[oldest]
        
        entry = CacheEntry(
            key=key,
            value=value,
            ttl=ttl,
            created_at=time.time(),
            tags=tags or []
        )
        
        self._cache[key] = entry
        if key in self._access_order:
            self._access_order.remove(key)
        self._access_order.append(key)
    
    def delete(self, key: str) -> bool:
        """Elimina entrada."""
        if key in self._cache:
            del self._cache[key]
            if key in self._access_order:
                self._access_order.remove(key)
            return True
        return False
    
    def invalidate_by_tag(self, tag: str) -> int:
        """Invalida todas las entradas con tag específico."""
        keys_to_delete = [
            key for key, entry in self._cache.items()
            if tag in entry.tags
        ]
        for key in keys_to_delete:
            self.delete(key)
        return len(keys_to_delete)
    
    def clear(self):
        """Limpia toda la caché."""
        self._cache.clear()
        self._access_order.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas."""
        return {
            "size": len(self._cache),
            "maxsize": self.maxsize,
            "utilization": len(self._cache) / self.maxsize if self.maxsize > 0 else 0,
        }


class DistributedCache:
    """
    Caché distribuida con Redis y fallback local.
    
    Características:
    - Multi-tier: Redis (L1) + Local (L2)
    - Circuit breaker para tolerancia a fallos
    - Invalidación por pub/sub
    - Serialización pickle/JSON
    """
    
    def __init__(
        self,
        redis_url: Optional[str] = None,
        strategy: CacheStrategy = CacheStrategy.HYBRID,
        local_maxsize: int = 1000,
        default_ttl: int = 300,
        key_prefix: str = "medicare:"
    ):
        self.strategy = strategy
        self.default_ttl = default_ttl
        self.key_prefix = key_prefix
        
        # Caché local (siempre disponible como fallback)
        self._local_cache = LocalLRUCache(maxsize=local_maxsize)
        
        # Redis client
        self._redis: Optional[redis.Redis] = None
        self._circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=30)
        
        if REDIS_AVAILABLE and redis_url and strategy != CacheStrategy.LOCAL:
            try:
                self._redis = redis.from_url(
                    redis_url,
                    socket_connect_timeout=5,
                    socket_timeout=5,
                    decode_responses=False  # Para serialización binaria
                )
                # Verificar conexión
                self._redis.ping()
                log_event("cache", "Redis connected successfully")
            except Exception as e:
                log_event("cache", f"Redis connection failed: {e}")
                self._redis = None
        
        # Setup pub/sub para invalidación
        if self._redis:
            self._setup_pubsub()
    
    def _setup_pubsub(self):
        """Setup canal de pub/sub para invalidación distribuida."""
        try:
            self._pubsub = self._redis.pubsub()
            self._pubsub.subscribe("cache:invalidate")
            # En producción, esto debería correr en thread separado
        except Exception as e:
            log_event("cache", f"Pub/sub setup failed: {e}")
    
    def _make_key(self, key: str) -> str:
        """Genera key con prefijo y hashing si es muy larga."""
        full_key = f"{self.key_prefix}{key}"
        if len(full_key) > 200:
            # Hash para keys muy largas
            return f"{self.key_prefix}hash:{hashlib.md5(key.encode()).hexdigest()}"
        return full_key
    
    def _serialize(self, value: Any) -> bytes:
        """Serializa valor para Redis."""
        try:
            return pickle.dumps(value)
        except Exception:
            # Fallback a JSON
            return json.dumps(value).encode()
    
    def _deserialize(self, data: bytes) -> Any:
        """Deserializa valor de Redis."""
        try:
            return pickle.loads(data)
        except Exception:
            try:
                return json.loads(data.decode())
            except Exception:
                return data
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Obtiene valor de caché.
        
        Orden de búsqueda:
        1. Caché local (L2)
        2. Redis (L1) - si disponible
        """
        cache_key = self._make_key(key)
        
        # 1. Intentar caché local primero (más rápido)
        value = self._local_cache.get(cache_key)
        if value is not None:
            return value
        
        # 2. Intentar Redis si está disponible
        if self._redis and self._circuit_breaker.can_execute():
            try:
                data = self._redis.get(cache_key)
                if data:
                    value = self._deserialize(data)
                    # Promover a caché local
                    ttl = self._redis.ttl(cache_key)
                    if ttl > 0:
                        self._local_cache.set(cache_key, value, ttl=min(ttl, 60))
                    return value
                self._circuit_breaker.record_success()
            except Exception as e:
                self._circuit_breaker.record_failure()
                log_event("cache", f"Redis get failed: {e}")
        
        return default
    
    def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None,
        broadcast: bool = False
    ):
        """
        Guarda valor en caché.
        
        Args:
            key: Clave de caché
            value: Valor a guardar
            ttl: Tiempo de vida en segundos
            tags: Tags para invalidación agrupada
            broadcast: Si True, notifica a otras instancias vía pub/sub
        """
        cache_key = self._make_key(key)
        ttl = ttl or self.default_ttl
        
        # Siempre guardar en local
        self._local_cache.set(cache_key, value, ttl=ttl, tags=tags)
        
        # Guardar en Redis si disponible
        if self._redis and self._circuit_breaker.can_execute():
            try:
                data = self._serialize(value)
                self._redis.setex(cache_key, ttl, data)
                
                # Indexar por tags
                if tags:
                    for tag in tags:
                        tag_key = f"{self.key_prefix}tag:{tag}"
                        self._redis.sadd(tag_key, cache_key)
                        self._redis.expire(tag_key, ttl)
                
                self._circuit_breaker.record_success()
                
                # Broadcast invalidación si se solicita
                if broadcast:
                    self._redis.publish("cache:invalidate", json.dumps({"key": key}))
                    
            except Exception as e:
                self._circuit_breaker.record_failure()
                log_event("cache", f"Redis set failed: {e}")
    
    def delete(self, key: str, broadcast: bool = False) -> bool:
        """Elimina valor de caché."""
        cache_key = self._make_key(key)
        
        # Eliminar de local
        local_deleted = self._local_cache.delete(cache_key)
        
        # Eliminar de Redis
        redis_deleted = False
        if self._redis and self._circuit_breaker.can_execute():
            try:
                redis_deleted = self._redis.delete(cache_key) > 0
                
                if broadcast:
                    self._redis.publish("cache:invalidate", json.dumps({"key": key}))
                    
            except Exception as e:
                log_event("cache", f"Redis delete failed: {e}")
        
        return local_deleted or redis_deleted
    
    def invalidate_by_tag(self, tag: str, broadcast: bool = False) -> int:
        """
        Invalida todas las entradas con un tag específico.
        
        Útil para invalidar caché cuando cambian datos relacionados,
        ej: "paciente:123" invalida todo lo relacionado a ese paciente.
        """
        tag_key = f"{self.key_prefix}tag:{tag}"
        
        # Invalidar local
        local_count = self._local_cache.invalidate_by_tag(tag)
        
        # Invalidar en Redis
        redis_count = 0
        if self._redis and self._circuit_breaker.can_execute():
            try:
                # Obtener keys con este tag
                keys = self._redis.smembers(tag_key)
                if keys:
                    # Eliminar keys
                    redis_count = self._redis.delete(*keys)
                    # Eliminar tag set
                    self._redis.delete(tag_key)
                
                if broadcast:
                    self._redis.publish("cache:invalidate", json.dumps({"tag": tag}))
                    
            except Exception as e:
                log_event("cache", f"Redis tag invalidation failed: {e}")
        
        return local_count + redis_count
    
    def clear(self, broadcast: bool = False):
        """Limpia toda la caché."""
        self._local_cache.clear()
        
        if self._redis and self._circuit_breaker.can_execute():
            try:
                # Solo eliminar keys con nuestro prefix
                for key in self._redis.scan_iter(match=f"{self.key_prefix}*"):
                    self._redis.delete(key)
                
                if broadcast:
                    self._redis.publish("cache:invalidate", json.dumps({"action": "clear"}))
                    
            except Exception as e:
                log_event("cache", f"Redis clear failed: {e}")
    
    def get_or_set(
        self,
        key: str,
        factory: Callable[[], Any],
        ttl: Optional[int] = None,
        tags: Optional[List[str]] = None
    ) -> Any:
        """
        Patrón cache-aside: obtiene de caché o computa y guarda.
        
        Uso:
            result = cache.get_or_set(
                "paciente:123",
                lambda: db.get_paciente(123),
                ttl=300,
                tags=["paciente:123"]
            )
        """
        value = self.get(key)
        if value is not None:
            return value
        
        # Computar valor
        value = factory()
        
        # Guardar en caché (si no es None)
        if value is not None:
            self.set(key, value, ttl=ttl, tags=tags)
        
        return value
    
    def get_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas de la caché."""
        stats = {
            "strategy": self.strategy.name,
            "local": self._local_cache.get_stats(),
            "redis_connected": self._redis is not None and self._circuit_breaker.can_execute(),
            "circuit_breaker_state": self._circuit_breaker.state.value if self._circuit_breaker else "unknown",
        }
        
        if self._redis and self._circuit_breaker.can_execute():
            try:
                info = self._redis.info()
                stats["redis"] = {
                    "used_memory": info.get("used_memory_human", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                    "total_keys": self._redis.dbsize(),
                }
            except Exception:
                pass
        
        return stats


# Singleton global
_cache_instance: Optional[DistributedCache] = None


def get_cache() -> DistributedCache:
    """Obtiene instancia global de caché distribuida."""
    global _cache_instance
    if _cache_instance is None:
        import os
        redis_url = os.getenv("REDIS_URL", "")
        _cache_instance = DistributedCache(redis_url=redis_url if redis_url else None)
    return _cache_instance


def cached(
    ttl: int = 300,
    key_fn: Optional[Callable] = None,
    tags_fn: Optional[Callable] = None,
    skip_args: Optional[List[int]] = None
):
    """
    Decorador para cachear resultados de funciones.
    
    Uso:
        @cached(ttl=600, tags_fn=lambda user_id: [f"user:{user_id}"])
        def get_user_data(user_id: str):
            return db.query(user_id)
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            cache = get_cache()
            
            # Generar key
            if key_fn:
                cache_key = key_fn(*args, **kwargs)
            else:
                # Key por defecto: nombre_funcion + args + kwargs
                key_parts = [func.__name__]
                
                # Filtrar args si se especifica
                for i, arg in enumerate(args):
                    if skip_args and i in skip_args:
                        continue
                    key_parts.append(str(arg))
                
                for k, v in sorted(kwargs.items()):
                    key_parts.append(f"{k}={v}")
                
                cache_key = ":".join(key_parts)
            
            # Generar tags
            tags = None
            if tags_fn:
                tags = tags_fn(*args, **kwargs)
            
            # Usar get_or_set
            return cache.get_or_set(
                cache_key,
                lambda: func(*args, **kwargs),
                ttl=ttl,
                tags=tags
            )
        
        return wrapper
    return decorator


def invalidate_cache(key: Optional[str] = None, tag: Optional[str] = None):
    """
    Invalida caché por key o tag.
    
    Uso:
        invalidate_cache(key="paciente:123")
        invalidate_cache(tag="paciente:123")  # Invalida todo relacionado
    """
    cache = get_cache()
    
    if key:
        cache.delete(key, broadcast=True)
    
    if tag:
        cache.invalidate_by_tag(tag, broadcast=True)


# Context manager para caché de sesión
@contextmanager
def session_cache(session_id: str):
    """
    Context manager para caché de sesión.
    
    Uso:
        with session_cache("sess_123") as cache:
            cache.set("user_data", {...})
            data = cache.get("user_data")
    """
    cache = get_cache()
    prefix = f"session:{session_id}:"
    
    class SessionCache:
        def get(self, key: str, default=None):
            return cache.get(f"{prefix}{key}", default)
        
        def set(self, key: str, value: Any, ttl: int = 3600):
            cache.set(f"{prefix}{key}", value, ttl=ttl, tags=[f"session:{session_id}"])
        
        def delete(self, key: str):
            cache.delete(f"{prefix}{key}")
        
        def clear(self):
            cache.invalidate_by_tag(f"session:{session_id}")
    
    yield SessionCache()
