"""Tests para core.object_pool_gc — Object Pool, GC Hardening, Buffers."""
from __future__ import annotations

import gc
import json


class TestGCSettings:
    def test_disable_in_critical_section(self):
        from core.object_pool_gc import GCSettings

        @GCSettings.disable_in_critical_section
        def critical_func():
            return gc.isenabled()

        was_enabled_before = gc.isenabled()
        result = critical_func()
        assert result is False  # GC disabled durante la ejecucion
        assert gc.isenabled() == was_enabled_before  # restaurado al salir

    def test_tune_for_high_throughput(self):
        from core.object_pool_gc import GCSettings
        GCSettings.tune_for_high_throughput()
        t0, t1, t2 = gc.get_threshold()
        assert t0 >= 100000

    def test_collect_generational(self):
        from core.object_pool_gc import GCSettings
        GCSettings.collect_generational(0)  # No debe lanzar


class TestObjectPool:
    def test_borrow_returns_object(self):
        from core.object_pool_gc import ObjectPool
        pool = ObjectPool.factory(dict, prealloc=5)
        d = pool.borrow()
        assert isinstance(d, dict)
        assert pool.stats["hits"] == 1

    def test_reset_and_return_dict(self):
        from core.object_pool_gc import ObjectPool
        pool = ObjectPool.factory(dict, prealloc=2)
        d = pool.borrow()
        d["key"] = "value"
        pool.reset_and_return(d)
        d2 = pool.borrow()
        assert d2 == {}  # reseteado

    def test_pool_stats(self):
        from core.object_pool_gc import ObjectPool
        pool = ObjectPool.factory(dict, prealloc=10)
        pool.borrow()
        stats = pool.stats
        assert stats["hits"] >= 0
        assert stats["max_size"] == 20
        assert stats["hit_ratio"] >= 0

    def test_miss_when_empty(self):
        from core.object_pool_gc import ObjectPool
        pool = ObjectPool.factory(dict, prealloc=0)
        d = pool.borrow()
        assert isinstance(d, dict)
        assert pool.stats["misses"] == 1

    def test_reset_and_return_list(self):
        from core.object_pool_gc import ObjectPool
        pool = ObjectPool.factory(list, prealloc=2)
        l = pool.borrow()
        l.append(1)
        l.append(2)
        pool.reset_and_return(l)
        l2 = pool.borrow()
        assert l2 == []


class TestMsgPackBuffer:
    def test_pack_and_unpack(self):
        from core.object_pool_gc import MsgPackBuffer
        buf = MsgPackBuffer(initial_size=1024)
        obj = {"id": "test", "values": [1, 2, 3]}
        packed = buf.pack(obj)
        assert isinstance(packed, bytes)
        unpacked = buf.unpack(packed)
        assert unpacked == obj

    def test_buffer_capacity(self):
        from core.object_pool_gc import MsgPackBuffer
        buf = MsgPackBuffer(initial_size=512)
        assert buf.capacity >= 512

    def test_clear(self):
        from core.object_pool_gc import MsgPackBuffer
        buf = MsgPackBuffer()
        buf.pack({"data": "test"})
        buf.clear()  # No debe lanzar


class TestGlobalPools:
    def test_payload_dict_pool(self):
        from core.object_pool_gc import payload_dict_pool
        d = payload_dict_pool.borrow()
        assert isinstance(d, dict)
        payload_dict_pool.reset_and_return(d)

    def test_event_list_pool(self):
        from core.object_pool_gc import event_list_pool
        l = event_list_pool.borrow()
        assert isinstance(l, list)
        event_list_pool.reset_and_return(l)

    def test_get_thread_buffer(self):
        from core.object_pool_gc import get_thread_buffer
        buf = get_thread_buffer()
        assert buf.capacity >= 8192
        # Mismo hilo: mismo buffer
        buf2 = get_thread_buffer()
        assert buf is buf2
