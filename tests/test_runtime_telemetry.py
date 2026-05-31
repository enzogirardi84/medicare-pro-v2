"""Tests para core.runtime_telemetry — Runtime + Prometheus metrics."""
from __future__ import annotations

import gc


class TestRuntimeMetricsCollector:
    def test_collect_gc_stats(self):
        from core.runtime_telemetry import RuntimeMetricsCollector
        collector = RuntimeMetricsCollector()
        stats = collector.collect_gc_stats()
        assert "gen0_count" in stats
        assert "gc_enabled" in stats
        assert "avg_gc_duration_ms" in stats

    def test_record_gc_event(self):
        from core.runtime_telemetry import RuntimeMetricsCollector
        collector = RuntimeMetricsCollector()
        collector.record_gc_event(5.2)
        collector.record_gc_event(3.1)
        stats = collector.collect_gc_stats()
        assert stats["avg_gc_duration_ms"] > 0

    def test_collect_pool_stats_empty(self):
        from core.runtime_telemetry import RuntimeMetricsCollector
        results = RuntimeMetricsCollector.collect_pool_stats({})
        assert results == []

    def test_collect_pool_stats_with_data(self):
        from core.runtime_telemetry import RuntimeMetricsCollector
        from core.object_pool_gc import ObjectPool
        pool = ObjectPool.factory(dict, prealloc=10)
        pool.borrow()
        results = RuntimeMetricsCollector.collect_pool_stats({"test_pool": pool})
        assert len(results) == 1
        assert results[0]["pool_name"] == "test_pool"
        assert results[0]["hits"] == 1

    def test_estimate_gil_contention(self):
        from core.runtime_telemetry import RuntimeMetricsCollector
        gil = RuntimeMetricsCollector.estimate_gil_contention()
        assert "contention_ratio" in gil
        assert "uncontended_ms" in gil
        assert gil["uncontended_ms"] > 0

    def test_collect_system_memory(self):
        from core.runtime_telemetry import RuntimeMetricsCollector
        mem = RuntimeMetricsCollector.collect_system_memory()
        assert "rss_bytes" in mem
        assert "vms_bytes" in mem

    def test_collect_all(self):
        from core.runtime_telemetry import RuntimeMetricsCollector
        collector = RuntimeMetricsCollector()
        data = collector.collect_all()
        assert "gc" in data
        assert "pools" in data
        assert "gil" in data
        assert "memory" in data


class TestPrometheusRuntimeExporter:
    def test_render_empty(self):
        from core.runtime_telemetry import PrometheusRuntimeExporter
        data = {
            "gc": {"gen0_count": 0, "gc_enabled": True, "avg_gc_duration_ms": 0},
            "pools": [],
            "gil": {"contention_ratio": 0, "uncontended_ms": 0},
            "memory": {"rss_mb": 0, "vms_mb": 0},
        }
        text = PrometheusRuntimeExporter.render(data)
        assert "medicare_runtime_gc_gen0_count" in text
        assert "medicare_runtime_gil_contention_ratio" in text
        assert "medicare_runtime_memory_rss_mb" in text
        assert text.endswith("\n")

    def test_render_with_pools(self):
        from core.runtime_telemetry import PrometheusRuntimeExporter
        data = {
            "gc": {"gen0_count": 5000, "gc_enabled": True, "avg_gc_duration_ms": 2.5},
            "pools": [{"pool_name": "payload_dict", "hit_ratio": 0.85,
                       "estimated_memory_saved_bytes": 218000}],
            "gil": {"contention_ratio": 1.5, "uncontended_ms": 0.3},
            "memory": {"rss_mb": 128.5, "vms_mb": 256.0},
        }
        text = PrometheusRuntimeExporter.render(data)
        assert 'pool="payload_dict"' in text
        assert "medicare_runtime_pool_hit_ratio" in text
        assert "medicare_runtime_pool_memory_saved_bytes" in text
