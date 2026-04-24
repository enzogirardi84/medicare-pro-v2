"""
Tests para caché distribuida con Redis.

EJECUTAR:
    python -m pytest tests/test_distributed_cache.py -v
"""

import pytest
import time
from unittest.mock import Mock, patch, MagicMock


class TestLocalLRUCache:
    """Tests para caché local LRU"""
    
    def test_cache_get_set(self):
        """Test operaciones básicas get/set"""
        from core.distributed_cache import LocalLRUCache
        
        cache = LocalLRUCache(maxsize=100)
        cache.set("key1", "value1", ttl=60)
        
        assert cache.get("key1") == "value1"
    
    def test_cache_expiration(self):
        """Test expiración de entradas"""
        from core.distributed_cache import LocalLRUCache
        
        cache = LocalLRUCache(maxsize=100)
        cache.set("key1", "value1", ttl=0.1)
        
        assert cache.get("key1") == "value1"
        time.sleep(0.15)
        assert cache.get("key1") is None
    
    def test_lru_eviction(self):
        """Test evicción LRU cuando se alcanza maxsize"""
        from core.distributed_cache import LocalLRUCache
        
        cache = LocalLRUCache(maxsize=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        cache.set("d", 4)  # Debe evict "a"
        
        assert cache.get("a") is None  # Evicted
        assert cache.get("b") == 2
        assert cache.get("c") == 3
        assert cache.get("d") == 4
    
    def test_lru_promotion(self):
        """Test que acceso promueve en LRU"""
        from core.distributed_cache import LocalLRUCache
        
        cache = LocalLRUCache(maxsize=3)
        cache.set("a", 1)
        cache.set("b", 2)
        cache.set("c", 3)
        
        # Acceder "a" lo promueve
        cache.get("a")
        
        # Agregar "d" debe evict "b" (no "a")
        cache.set("d", 4)
        
        assert cache.get("a") == 1  # Aún presente
        assert cache.get("b") is None  # Evicted
    
    def test_invalidate_by_tag(self):
        """Test invalidación por tag"""
        from core.distributed_cache import LocalLRUCache
        
        cache = LocalLRUCache(maxsize=100)
        cache.set("a", 1, tags=["tag1", "tag2"])
        cache.set("b", 2, tags=["tag1"])
        cache.set("c", 3, tags=["tag2"])
        
        deleted = cache.invalidate_by_tag("tag1")
        
        assert deleted == 2
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("c") == 3  # No tenía tag1


class TestDistributedCache:
    """Tests para DistributedCache"""
    
    def test_cache_without_redis(self):
        """Test que funciona sin Redis (solo local)"""
        from core.distributed_cache import DistributedCache, CacheStrategy
        
        cache = DistributedCache(
            redis_url=None,
            strategy=CacheStrategy.LOCAL
        )
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
    
    def test_get_or_set(self):
        """Test patrón get_or_set"""
        from core.distributed_cache import DistributedCache, CacheStrategy
        
        cache = DistributedCache(
            redis_url=None,
            strategy=CacheStrategy.LOCAL
        )
        
        call_count = 0
        def factory():
            nonlocal call_count
            call_count += 1
            return f"computed_{call_count}"
        
        # Primera llamada computa
        result1 = cache.get_or_set("key1", factory, ttl=60)
        assert result1 == "computed_1"
        assert call_count == 1
        
        # Segunda llamada usa caché
        result2 = cache.get_or_set("key1", factory, ttl=60)
        assert result2 == "computed_1"
        assert call_count == 1  # No computó de nuevo
    
    def test_delete(self):
        """Test eliminación de entradas"""
        from core.distributed_cache import DistributedCache, CacheStrategy
        
        cache = DistributedCache(
            redis_url=None,
            strategy=CacheStrategy.LOCAL
        )
        
        cache.set("key1", "value1")
        assert cache.get("key1") == "value1"
        
        cache.delete("key1")
        assert cache.get("key1") is None
    
    def test_invalidate_by_tag(self):
        """Test invalidación por tag en caché distribuida"""
        from core.distributed_cache import DistributedCache, CacheStrategy
        
        cache = DistributedCache(
            redis_url=None,
            strategy=CacheStrategy.LOCAL
        )
        
        cache.set("a", 1, tags=["user:123"])
        cache.set("b", 2, tags=["user:123"])
        cache.set("c", 3, tags=["user:456"])
        
        deleted = cache.invalidate_by_tag("user:123")
        
        assert deleted == 2
        assert cache.get("a") is None
        assert cache.get("b") is None
        assert cache.get("c") == 3
    
    def test_clear(self):
        """Test limpieza completa"""
        from core.distributed_cache import DistributedCache, CacheStrategy
        
        cache = DistributedCache(
            redis_url=None,
            strategy=CacheStrategy.LOCAL
        )
        
        cache.set("a", 1)
        cache.set("b", 2)
        
        cache.clear()
        
        assert cache.get("a") is None
        assert cache.get("b") is None
    
    def test_get_stats(self):
        """Test estadísticas"""
        from core.distributed_cache import DistributedCache, CacheStrategy
        
        cache = DistributedCache(
            redis_url=None,
            strategy=CacheStrategy.LOCAL
        )
        
        cache.set("a", 1)
        cache.set("b", 2)
        
        stats = cache.get_stats()
        
        assert stats["strategy"] == "LOCAL"
        assert stats["local"]["size"] == 2
        assert stats["redis_connected"] is False


class TestCachedDecorator:
    """Tests para decorador @cached"""
    
    def test_cached_decorator(self):
        """Test decorador cachea resultados"""
        from core.distributed_cache import cached
        
        call_count = 0
        
        @cached(ttl=60)
        def expensive_function(x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        result1 = expensive_function(5)
        assert result1 == 10
        assert call_count == 1
        
        result2 = expensive_function(5)
        assert result2 == 10
        assert call_count == 1  # Cache hit
        
        result3 = expensive_function(10)
        assert result3 == 20
        assert call_count == 2  # Diferente argumento
    
    def test_cached_with_key_fn(self):
        """Test decorador con función de key personalizada"""
        from core.distributed_cache import cached
        
        call_count = 0
        
        @cached(ttl=60, key_fn=lambda user_id: f"user:{user_id}")
        def get_user(user_id):
            nonlocal call_count
            call_count += 1
            return {"id": user_id, "name": "Test"}
        
        get_user(123)
        get_user(123)
        
        assert call_count == 1
    
    def test_cached_with_tags(self):
        """Test decorador con tags para invalidación"""
        from core.distributed_cache import cached, invalidate_cache
        
        call_count = 0
        
        @cached(ttl=60, tags_fn=lambda user_id: [f"user:{user_id}"])
        def get_user_data(user_id):
            nonlocal call_count
            call_count += 1
            return {"id": user_id}
        
        get_user_data(123)
        get_user_data(123)
        assert call_count == 1
        
        # Invalidar por tag
        invalidate_cache(tag="user:123")
        
        # Próxima llamada debe computar
        get_user_data(123)
        assert call_count == 2


class TestSessionCache:
    """Tests para caché de sesión"""
    
    def test_session_cache_context(self):
        """Test context manager de sesión"""
        from core.distributed_cache import session_cache
        
        with session_cache("sess_123") as cache:
            cache.set("user", {"name": "John"})
            user = cache.get("user")
            assert user["name"] == "John"
    
    def test_session_isolation(self):
        """Test que sesiones están aisladas"""
        from core.distributed_cache import session_cache
        
        with session_cache("sess_1") as cache1:
            cache1.set("data", "session1_data")
        
        with session_cache("sess_2") as cache2:
            cache2.set("data", "session2_data")
        
        with session_cache("sess_1") as cache1:
            assert cache1.get("data") == "session1_data"
        
        with session_cache("sess_2") as cache2:
            assert cache2.get("data") == "session2_data"


class TestCacheStats:
    """Tests para estadísticas"""
    
    def test_stats_structure(self):
        """Test estructura de estadísticas"""
        from core.distributed_cache import DistributedCache, CacheStrategy
        
        cache = DistributedCache(
            redis_url=None,
            strategy=CacheStrategy.LOCAL
        )
        
        stats = cache.get_stats()
        
        assert "strategy" in stats
        assert "local" in stats
        assert "redis_connected" in stats
        assert "circuit_breaker_state" in stats
