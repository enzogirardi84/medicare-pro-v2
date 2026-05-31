"""Tests para core.l1_l2_cache — Two-Level Cache + Invalidation Broadcast."""
from __future__ import annotations

import asyncio
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestL1Cache:
    def test_get_miss(self):
        from core.l1_l2_cache import L1Cache
        cache = L1Cache()
        assert cache.get("nonexistent") is None

    def test_set_and_get(self):
        from core.l1_l2_cache import L1Cache
        cache = L1Cache(default_ttl=60)
        cache.set("k1", "value1")
        assert cache.get("k1") == "value1"

    def test_expired_entry(self):
        from core.l1_l2_cache import L1Cache
        import time
        cache = L1Cache()
        cache.set("k", "v", ttl=0.01)
        time.sleep(0.02)
        assert cache.get("k") is None

    def test_invalidate(self):
        from core.l1_l2_cache import L1Cache
        cache = L1Cache()
        cache.set("k", "v")
        cache.invalidate("k")
        assert cache.get("k") is None

    def test_invalidate_pattern(self):
        from core.l1_l2_cache import L1Cache
        cache = L1Cache()
        cache.set("patient:123", "v1")
        cache.set("patient:456", "v2")
        cache.set("other", "v3")
        cache.invalidate_pattern("patient:")
        assert cache.get("patient:123") is None
        assert cache.get("patient:456") is None
        assert cache.get("other") == "v3"

    def test_clear(self):
        from core.l1_l2_cache import L1Cache
        cache = L1Cache()
        cache.set("k1", "v1")
        cache.set("k2", "v2")
        cache.clear()
        assert cache.get("k1") is None
        assert cache.stats["size"] == 0

    def test_lru_eviction(self):
        from core.l1_l2_cache import L1Cache
        cache = L1Cache(max_size=2)
        cache.set("a", "1")
        cache.set("b", "2")
        cache.set("c", "3")
        assert cache.get("a") is None  # should be evicted
        assert cache.get("b") == "2"
        assert cache.get("c") == "3"

    def test_stats(self):
        from core.l1_l2_cache import L1Cache
        cache = L1Cache()
        cache.get("miss")
        cache.set("hit", "v")
        cache.get("hit")
        stats = cache.stats
        assert stats["hits"] == 1
        assert stats["misses"] >= 1


class TestL2Cache:
    def test_get_no_redis(self):
        from core.l1_l2_cache import L2Cache
        cache = L2Cache()
        result = asyncio.run(cache.get("k"))
        assert result is None

    def test_set_no_redis(self):
        from core.l1_l2_cache import L2Cache
        cache = L2Cache()
        asyncio.run(cache.set("k", b"v"))  # no debe lanzar

    def test_invalidate_no_redis(self):
        from core.l1_l2_cache import L2Cache
        cache = L2Cache()
        asyncio.run(cache.invalidate("k"))  # no debe lanzar


class TestCacheDispatcher:
    def test_get_miss_no_fetch(self):
        from core.l1_l2_cache import CacheDispatcher
        disp = CacheDispatcher()
        result = asyncio.run(disp.get("k"))
        assert result is None

    def test_get_with_fetch(self):
        from core.l1_l2_cache import CacheDispatcher
        disp = CacheDispatcher()

        async def fetch(key):
            return f"fetched:{key}"

        disp.set_fetch_function(fetch)
        result = asyncio.run(disp.get("test-key"))
        assert result == "fetched:test-key"

    def test_set_and_get(self):
        from core.l1_l2_cache import CacheDispatcher
        disp = CacheDispatcher()
        asyncio.run(disp.set("k", "v"))
        # Should be in L1 now
        assert disp._l1.get("k") == "v"

    def test_invalidate_clears_l1(self):
        from core.l1_l2_cache import CacheDispatcher
        disp = CacheDispatcher()
        asyncio.run(disp.set("k", "v"))
        asyncio.run(disp.invalidate("k"))
        assert disp._l1.get("k") is None

    def test_get_stats(self):
        from core.l1_l2_cache import CacheDispatcher
        disp = CacheDispatcher()
        stats = disp.get_stats()
        assert "l1" in stats
        assert "instance_id" in stats

    def test_close(self):
        from core.l1_l2_cache import CacheDispatcher
        disp = CacheDispatcher()
        asyncio.run(disp.close())
