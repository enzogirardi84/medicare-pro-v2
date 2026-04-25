"""
Tests específicos para cache_manager.py

EJECUTAR:
    python -m pytest tests/test_cache_manager.py -v
"""

import pytest
import time
from datetime import datetime, timedelta


class TestTieredCacheManager:
    """Tests para TieredCacheManager"""
    
    def test_cache_creation(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        assert cache is not None
    
    def test_l1_cache_operations(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        # Set y get
        cache.set("test", "tenant1", "test_value", ttl_seconds=60)
        hit, value = cache.get("test", "tenant1")
        
        assert hit is True
        assert value == "test_value"
    
    def test_cache_ttl_expiration(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        # Set con TTL corto
        cache.set("test", "tenant1", "value", ttl_seconds=0.1)
        
        # Verificar existencia inicial
        hit, value = cache.get("test", "tenant1")
        assert hit is True
        assert value == "value"
        
        # Esperar expiración
        time.sleep(0.15)
        
        # Verificar que expiró
        hit, value = cache.get("test", "tenant1")
        assert hit is False
        assert value is None
    
    def test_cache_delete(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        cache.set("test", "tenant1", "value", key_suffix="delete_key")
        cache.invalidate(prefix="test", tenant_key="tenant1")
        
        hit, value = cache.get("test", "tenant1", key_suffix="delete_key")
        assert hit is False
        assert value is None
    
    def test_cache_clear(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        cache.set("test", "tenant1", "value1", key_suffix="key1")
        cache.set("test", "tenant1", "value2", key_suffix="key2")
        
        cache.clear()
        
        hit1, _ = cache.get("test", "tenant1", key_suffix="key1")
        hit2, _ = cache.get("test", "tenant1", key_suffix="key2")
        assert hit1 is False
        assert hit2 is False


class TestCacheStats:
    """Tests para estadísticas de caché"""
    
    def test_hit_miss_stats(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        # Miss
        cache.get("test", "nonexistent")
        
        # Hit
        cache.set("test", "tenant1", "value", key_suffix="exists")
        cache.get("test", "tenant1", key_suffix="exists")
        
        stats = cache.get_stats()
        assert stats["hits"] >= 1
        assert stats["misses"] >= 1
    
    def test_cache_size_tracking(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        cache.set("test", "tenant1", "x" * 1000, key_suffix="key1")
        cache.set("test", "tenant1", "y" * 500, key_suffix="key2")
        
        stats = cache.get_stats()
        assert "l1_entries" in stats
        assert stats["l1_entries"] >= 0


class TestMemoryPressure:
    """Tests para manejo de presión de memoria"""
    
    def test_eviction_under_pressure(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager(max_l1_entries=2)
        
        # Llenar caché más allá del límite L1
        for i in range(5):
            cache.set("test", "tenant1", "x" * 20, key_suffix=f"key_{i}")
        
        # Verificar que se hicieron evicciones
        stats = cache.get_stats()
        assert stats["evictions"] > 0


class TestCacheInvalidation:
    """Tests para invalidación de caché"""
    
    def test_pattern_invalidation(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        cache.set("user", "1", "John", key_suffix="name")
        cache.set("user", "1", "john@example.com", key_suffix="email")
        cache.set("user", "2", "Jane", key_suffix="name")
        
        # Invalidar por patrón (substring match en la clave generada)
        cache.invalidate(pattern="user:1:")
        
        hit_name1, _ = cache.get("user", "1", key_suffix="name")
        hit_email1, _ = cache.get("user", "1", key_suffix="email")
        hit_name2, value_name2 = cache.get("user", "2", key_suffix="name")
        
        assert hit_name1 is False
        assert hit_email1 is False
        assert hit_name2 is True
        assert value_name2 == "Jane"
