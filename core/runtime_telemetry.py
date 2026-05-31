"""Telemetria interna del runtime: cache, object pool, GC, GIL.
Exporta metricas en formato Prometheus OpenMetrics para Grafana.
"""
from __future__ import annotations

import gc
import os
import threading
import time
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. RECOLECTOR DE METRICAS DEL RUNTIME
# ═══════════════════════════════════════════════════════════════════

class RuntimeMetricsCollector:
    """Recolecta metricas internas del runtime Python.

    - Cache L1/L2: hits, misses, hit ratio, size
    - Object Pool: borrows, returns, hit ratio, memory saved
    - GC: count by generation, thresholds, elapsed time
    - GIL: estimated contention (proxy via thread scheduling)
    - Memory: RSS, VMS del proceso
    """

    def __init__(self):
        self._gc_times: list[float] = []
        self._gc_durations: list[float] = []
        self._lock = threading.Lock()

    # ── Garbage Collector Stats ─────────────────────────────

    def collect_gc_stats(self) -> dict:
        """Metricas del Garbage Collector."""
        counts = gc.get_count()
        thresholds = gc.get_threshold()
        stats_list = gc.get_stats()
        # stats_list is list of dicts: [{"collections": N, "collected": M}, ...]
        total_collections = sum(s.get("collections", 0) for s in stats_list)
        return {
            "gen0_count": counts[0],
            "gen1_count": counts[1],
            "gen2_count": counts[2],
            "gen0_threshold": thresholds[0],
            "gen1_threshold": thresholds[1],
            "gen2_threshold": thresholds[2],
            "gc_enabled": gc.isenabled(),
            "total_collections": total_collections,
            "avg_gc_duration_ms": self._avg_gc_duration(),
        }

    def record_gc_event(self, duration_ms: float):
        """Registra un evento de GC para tracking historico."""
        with self._lock:
            self._gc_times.append(time.time())
            self._gc_durations.append(duration_ms)
            # Mantener solo ultimos 100 eventos
            if len(self._gc_times) > 100:
                self._gc_times.pop(0)
                self._gc_durations.pop(0)

    def _avg_gc_duration(self) -> float:
        with self._lock:
            if not self._gc_durations:
                return 0.0
            return round(sum(self._gc_durations) / len(self._gc_durations), 3)

    # ── Object Pool Stats ──────────────────────────────────

    @staticmethod
    def collect_pool_stats(pools: dict[str, Any]) -> list[dict]:
        """Metricas de pools de objetos.

        Args:
            pools: dict {name: ObjectPool}

        Returns:
            Lista de metricas por pool.
        """
        results = []
        for name, pool in pools.items():
            s = pool.stats
            # Estimar memoria ahorrada
            hit_ratio = s.get("hit_ratio", 0)
            estimated_saved_bytes = int(hit_ratio * 1000 * 256)  # ~256 bytes por dict evitado
            results.append({
                "pool_name": name,
                "size": s.get("size", 0),
                "hits": s.get("hits", 0),
                "misses": s.get("misses", 0),
                "hit_ratio": s.get("hit_ratio", 0),
                "estimated_memory_saved_bytes": estimated_saved_bytes,
            })
        return results

    # ── GIL Contention (estimacion) ────────────────────────

    @staticmethod
    def estimate_gil_contention() -> dict:
        """Estima contencion del GIL mediante medicion de thread scheduling.

        Nota: Es una heuristica. En produccion usar eBPF o perf.
        """
        import threading
        import time

        def _measure():
            start = time.perf_counter()
            # Operacion que requiere GIL (calculo simple)
            _ = [i ** 2 for i in range(10000)]
            return (time.perf_counter() - start) * 1000  # ms

        # Sin contencion
        t0 = _measure()

        # Con contencion simulada (varios threads)
        threads = []
        durations = []
        for _ in range(4):
            t = threading.Thread(target=lambda: durations.append(_measure()))
            threads.append(t)
            t.start()
        for t in threads:
            t.join()

        avg_contended = sum(durations) / len(durations) if durations else 0

        return {
            "uncontended_ms": round(t0, 4),
            "contended_ms": round(avg_contended, 4),
            "contention_ratio": round(avg_contended / t0, 2) if t0 > 0 else 0,
        }

    # ── System Memory ──────────────────────────────────────

    @staticmethod
    def collect_system_memory() -> dict:
        """Memoria del proceso actual."""
        import os as _os

        try:
            import psutil
            process = psutil.Process()
            mem = process.memory_info()
            return {
                "rss_bytes": mem.rss,
                "vms_bytes": mem.vms,
                "rss_mb": round(mem.rss / (1024 ** 2), 1),
                "vms_mb": round(mem.vms / (1024 ** 2), 1),
                "cpu_percent": process.cpu_percent(interval=0),
                "num_threads": process.num_threads(),
            }
        except ImportError:
            return {
                "rss_bytes": 0,
                "vms_bytes": 0,
                "note": "psutil not installed",
            }

    # ── All-in-one ─────────────────────────────────────────

    def collect_all(self, pools: Optional[dict] = None) -> dict:
        """Recolecta todas las metricas del runtime."""
        return {
            "gc": self.collect_gc_stats(),
            "pools": self.collect_pool_stats(pools or {}),
            "gil": self.estimate_gil_contention(),
            "memory": self.collect_system_memory(),
            "timestamp": time.time(),
        }


# ═══════════════════════════════════════════════════════════════════
# 2. EXPORTADOR PROMETHEUS
# ═══════════════════════════════════════════════════════════════════

class PrometheusRuntimeExporter:
    """Exporta metricas del runtime en formato Prometheus OpenMetrics.

    Uso:
        exporter = PrometheusRuntimeExporter()
        metrics = exporter.render(collector.collect_all(pools={
            "payload_dict": payload_dict_pool,
            "event_list": event_list_pool,
        }))
        # Servir en /metrics
    """

    METRIC_PREFIX = "medicare_runtime"

    @staticmethod
    def render(runtime_data: dict) -> str:
        """Renderiza metricas en formato Prometheus text.

        Args:
            runtime_data: Dict de RuntimeMetricsCollector.collect_all().

        Returns:
            String en formato Prometheus OpenMetrics.
        """
        lines: list[str] = []
        ts = int(time.time())

        # GC metrics
        gc = runtime_data.get("gc", {})
        lines.append(f"# HELP {PrometheusRuntimeExporter.METRIC_PREFIX}_gc_gen0_count Objetos en generacion 0 del GC")
        lines.append(f"# TYPE {PrometheusRuntimeExporter.METRIC_PREFIX}_gc_gen0_count gauge")
        lines.append(f'{PrometheusRuntimeExporter.METRIC_PREFIX}_gc_gen0_count {gc.get("gen0_count", 0)} {ts}')

        lines.append(f"# HELP {PrometheusRuntimeExporter.METRIC_PREFIX}_gc_enabled Estado del GC")
        lines.append(f"# TYPE {PrometheusRuntimeExporter.METRIC_PREFIX}_gc_enabled gauge")
        lines.append(f'{PrometheusRuntimeExporter.METRIC_PREFIX}_gc_enabled {1 if gc.get("gc_enabled") else 0} {ts}')

        lines.append(f"# HELP {PrometheusRuntimeExporter.METRIC_PREFIX}_gc_avg_duration_ms Duracion promedio del GC (ms)")
        lines.append(f"# TYPE {PrometheusRuntimeExporter.METRIC_PREFIX}_gc_avg_duration_ms gauge")
        lines.append(f'{PrometheusRuntimeExporter.METRIC_PREFIX}_gc_avg_duration_ms {gc.get("avg_gc_duration_ms", 0)} {ts}')

        # Pool metrics
        for pool in runtime_data.get("pools", []):
            name = pool.get("pool_name", "unknown")
            lines.append(f'# HELP {PrometheusRuntimeExporter.METRIC_PREFIX}_pool_hit_ratio Hit ratio del pool {name}')
            lines.append(f'# TYPE {PrometheusRuntimeExporter.METRIC_PREFIX}_pool_hit_ratio gauge')
            lines.append(f'{PrometheusRuntimeExporter.METRIC_PREFIX}_pool_hit_ratio{{pool="{name}"}} {pool.get("hit_ratio", 0)} {ts}')

            lines.append(f'# HELP {PrometheusRuntimeExporter.METRIC_PREFIX}_pool_memory_saved_bytes Memoria ahorrada por pool {name}')
            lines.append(f'# TYPE {PrometheusRuntimeExporter.METRIC_PREFIX}_pool_memory_saved_bytes gauge')
            lines.append(f'{PrometheusRuntimeExporter.METRIC_PREFIX}_pool_memory_saved_bytes{{pool="{name}"}} {pool.get("estimated_memory_saved_bytes", 0)} {ts}')

        # GIL metrics
        gil = runtime_data.get("gil", {})
        lines.append(f"# HELP {PrometheusRuntimeExporter.METRIC_PREFIX}_gil_contention_ratio Ratio de contencion del GIL")
        lines.append(f"# TYPE {PrometheusRuntimeExporter.METRIC_PREFIX}_gil_contention_ratio gauge")
        lines.append(f'{PrometheusRuntimeExporter.METRIC_PREFIX}_gil_contention_ratio {gil.get("contention_ratio", 0)} {ts}')

        lines.append(f"# HELP {PrometheusRuntimeExporter.METRIC_PREFIX}_gil_uncontended_ms Tiempo sin contencion (ms)")
        lines.append(f"# TYPE {PrometheusRuntimeExporter.METRIC_PREFIX}_gil_uncontended_ms gauge")
        lines.append(f'{PrometheusRuntimeExporter.METRIC_PREFIX}_gil_uncontended_ms {gil.get("uncontended_ms", 0)} {ts}')

        # System memory
        mem = runtime_data.get("memory", {})
        lines.append(f"# HELP {PrometheusRuntimeExporter.METRIC_PREFIX}_memory_rss_mb Memoria RSS del proceso (MB)")
        lines.append(f"# TYPE {PrometheusRuntimeExporter.METRIC_PREFIX}_memory_rss_mb gauge")
        lines.append(f'{PrometheusRuntimeExporter.METRIC_PREFIX}_memory_rss_mb {mem.get("rss_mb", 0)} {ts}')

        lines.append(f"# HELP {PrometheusRuntimeExporter.METRIC_PREFIX}_memory_vms_mb Memoria VMS del proceso (MB)")
        lines.append(f"# TYPE {PrometheusRuntimeExporter.METRIC_PREFIX}_memory_vms_mb gauge")
        lines.append(f'{PrometheusRuntimeExporter.METRIC_PREFIX}_memory_vms_mb {mem.get("vms_mb", 0)} {ts}')

        return "\n".join(lines) + "\n"


__all__ = [
    "RuntimeMetricsCollector",
    "PrometheusRuntimeExporter",
]
