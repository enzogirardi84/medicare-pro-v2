"""Middleware de observabilidad para FastAPI/Streamlit.
Expone metricas Prometheus: latencia sync, fallos criptograficos,
errores de concurrencia, tasa de aciertos de cache.
"""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from typing import Any, Callable

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. COLECTOR DE METRICAS EN MEMORIA
# ═══════════════════════════════════════════════════════════════════

class MetricsCollector:
    """Recolector liviano de metricas en memoria.

    Expone metricas en formato Prometheus para scraping.
    """

    def __init__(self):
        self._metrics: dict[str, Any] = {
            "sync_requests_total": 0,
            "sync_errors_total": 0,
            "sync_latency_ms": [],
            "integrity_failures_total": 0,
            "optimistic_lock_errors_total": 0,
            "cache_hits_total": 0,
            "cache_misses_total": 0,
        }

    def increment(self, metric: str, value: int = 1) -> None:
        if metric in self._metrics:
            if isinstance(self._metrics[metric], list):
                self._metrics[metric].append(value)
            else:
                self._metrics[metric] += value

    def record_latency(self, ms: float) -> None:
        self._metrics["sync_latency_ms"].append(ms)
        if len(self._metrics["sync_latency_ms"]) > 1000:
            self._metrics["sync_latency_ms"] = self._metrics["sync_latency_ms"][-1000:]

    def integrity_failure(self, detail: str = "") -> None:
        self.increment("integrity_failures_total")
        log_event("observability", f"INTEGRITY_FAILURE:{detail}")

    def lock_error(self, detail: str = "") -> None:
        self.increment("optimistic_lock_errors_total")
        log_event("observability", f"OPTIMISTIC_LOCK_ERROR:{detail}")

    def to_prometheus(self) -> str:
        """Exporta metricas en formato Prometheus."""
        p95 = sorted(self._metrics["sync_latency_ms"])
        p95_val = p95[int(len(p95) * 0.95)] if p95 else 0

        lines = [
            "# HELP medicare_sync_requests_total Total de requests de sync",
            "# TYPE medicare_sync_requests_total counter",
            f"medicare_sync_requests_total {self._metrics['sync_requests_total']}",
            "",
            "# HELP medicare_sync_errors_total Total de errores de sync",
            "# TYPE medicare_sync_errors_total counter",
            f"medicare_sync_errors_total {self._metrics['sync_errors_total']}",
            "",
            "# HELP medicare_sync_latency_p95_ms Latencia p95 del sync en ms",
            "# TYPE medicare_sync_latency_p95_ms gauge",
            f"medicare_sync_latency_p95_ms {p95_val}",
            "",
            "# HELP medicare_integrity_failures_total Fallos de integridad criptografica",
            "# TYPE medicare_integrity_failures_total counter",
            f"medicare_integrity_failures_total {self._metrics['integrity_failures_total']}",
            "",
            "# HELP medicare_optimistic_lock_errors_total Errores de concurrencia optimista",
            "# TYPE medicare_optimistic_lock_errors_total counter",
            f"medicare_optimistic_lock_errors_total {self._metrics['optimistic_lock_errors_total']}",
            "",
            "# HELP medicare_cache_ratio Tasa de aciertos del cache",
            "# TYPE medicare_cache_ratio gauge",
            f"medicare_cache_ratio {self._cache_ratio()}",
        ]
        return "\n".join(lines)

    def _cache_ratio(self) -> float:
        total = self._metrics["cache_hits_total"] + self._metrics["cache_misses_total"]
        if total == 0:
            return 1.0
        return round(self._metrics["cache_hits_total"] / total, 3)

    def to_json(self) -> str:
        return json.dumps({
            "sync_requests": self._metrics["sync_requests_total"],
            "sync_errors": self._metrics["sync_errors_total"],
            "integrity_failures": self._metrics["integrity_failures_total"],
            "lock_errors": self._metrics["optimistic_lock_errors_total"],
            "cache_ratio": self._cache_ratio(),
        }, indent=2)


# ═══════════════════════════════════════════════════════════════════
# 2. DECORADOR DE MONITOREO PARA FASTAPI
# ═══════════════════════════════════════════════════════════════════

_metrics_collector: MetricsCollector | None = None


def get_metrics() -> MetricsCollector:
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def monitor_sync_endpoint(func: Callable) -> Callable:
    """Decorador para monitorear endpoints de sincronizacion.

    Mide latencia, cuenta errores, detecta fallos criptograficos.
    """
    import functools

    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        metrics = get_metrics()
        metrics.increment("sync_requests_total")
        t0 = time.perf_counter()

        try:
            result = await func(*args, **kwargs)
            dt = (time.perf_counter() - t0) * 1000
            metrics.record_latency(dt)
            return result

        except Exception as exc:
            metrics.increment("sync_errors_total")
            error_str = str(exc)
            if "hash_integridad" in error_str or "firma_ecdsa" in error_str:
                metrics.integrity_failure(error_str[:200])
            if "version" in error_str and "conflict" in error_str.lower():
                metrics.lock_error(error_str[:200])
            raise

    return wrapper


# ═══════════════════════════════════════════════════════════════════
# 3. HEALTH CHECK ENDPOINT (para el ALB)
# ═══════════════════════════════════════════════════════════════════

def health_check_response() -> dict:
    """Genera respuesta JSON para el health check."""
    metrics = get_metrics()
    return {
        "status": "healthy",
        "timestamp": time.time(),
        "metrics": {
            "sync_requests": metrics._metrics["sync_requests_total"],
            "integrity_failures": metrics._metrics["integrity_failures_total"],
            "cache_ratio": metrics._cache_ratio(),
        },
    }
