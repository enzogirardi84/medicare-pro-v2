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
        cache.set("test_key", "test_value", ttl_seconds=60)
        value = cache.get("test_key")
        
        assert value == "test_value"
    
    def test_cache_ttl_expiration(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        # Set con TTL corto
        cache.set("expiring_key", "value", ttl_seconds=0.1)
        
        # Verificar existencia inicial
        assert cache.get("expiring_key") == "value"
        
        # Esperar expiración
        time.sleep(0.15)
        
        # Verificar que expiró
        assert cache.get("expiring_key") is None
    
    def test_cache_delete(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        cache.set("delete_key", "value")
        cache.delete("delete_key")
        
        assert cache.get("delete_key") is None
    
    def test_cache_clear(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        
        cache.clear()
        
        assert cache.get("key1") is None
        assert cache.get("key2") is None


class TestCacheStats:
    """Tests para estadísticas de caché"""
    
    def test_hit_miss_stats(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        # Miss
        cache.get("nonexistent")
        
        # Hit
        cache.set("exists", "value")
        cache.get("exists")
        
        stats = cache.get_stats()
        assert stats["l1_hits"] >= 1
        assert stats["l1_misses"] >= 1
    
    def test_cache_size_tracking(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        cache.set("key1", "x" * 1000)
        cache.set("key2", "y" * 500)
        
        stats = cache.get_stats()
        assert "size_bytes" in stats


class TestMemoryPressure:
    """Tests para manejo de presión de memoria"""
    
    def test_eviction_under_pressure(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager(max_size_bytes=1000)
        
        # Llenar caché
        for i in range(100):
            cache.set(f"key_{i}", "x" * 20)
        
        # Verificar que se hicieron evicciones
        stats = cache.get_stats()
        assert stats["evictions"] > 0


class TestCacheInvalidation:
    """Tests para invalidación de caché"""
    
    def test_pattern_invalidation(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        cache.set("user:1:name", "John")
        cache.set("user:1:email", "john@example.com")
        cache.set("user:2:name", "Jane")
        
        # Invalidar por patrón
        cache.invalidate_pattern("user:1:*")
        
        assert cache.get("user:1:name") is None
        assert cache.get("user:1:email") is None
        assert cache.get("user:2:name") == "Jane"
