"""
Performance Profiler para Medicare Pro.

Características:
- Profiling de funciones lentas
- APM (Application Performance Monitoring)
- Alertas de latencia
- Detección de queries N+1
- Memory profiling
- Export a formatos estándar (JSON, pstats)
"""

from __future__ import annotations

import cProfile
import functools
import gc
import io
import json
import pstats
import sys
import time
import tracemalloc
from contextlib import contextmanager
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Union
from collections import defaultdict

import streamlit as st

from core.app_logging import log_event
from core.observability import track_metric, timed


@dataclass
class FunctionProfile:
    """Perfil de ejecución de una función."""
    name: str
    filename: str
    lineno: int
    
    call_count: int = 0
    total_time: float = 0.0
    min_time: float = float('inf')
    max_time: float = 0.0
    avg_time: float = 0.0
    
    # Memory
    memory_usage: int = 0
    peak_memory: int = 0
    
    # Queries (si aplica)
    db_queries: int = 0
    db_time: float = 0.0


@dataclass
class PerformanceSnapshot:
    """Snapshot de performance del sistema."""
    timestamp: float
    function_stats: Dict[str, FunctionProfile]
    
    # Memoria
    memory_current: int
    memory_peak: int
    gc_collections: int
    
    # Queries
    total_queries: int
    slow_queries: List[Dict[str, Any]]
    
    # Alertas
    alerts: List[str] = field(default_factory=list)


class PerformanceProfiler:
    """
    Profiler de performance con APM integrado.
    
    Uso:
        profiler = PerformanceProfiler()
        
        @profiler.profile
        def mi_funcion():
            pass
        
        # O con context manager
        with profiler.profile_block("operacion"):
            operacion()
    """
    
    # Umbral de alerta (en segundos)
    SLOW_FUNCTION_THRESHOLD = 0.5  # 500ms
    SLOW_QUERY_THRESHOLD = 0.1     # 100ms
    MEMORY_ALERT_THRESHOLD = 100 * 1024 * 1024  # 100MB
    
    def __init__(self, enabled: bool = True, sample_rate: float = 1.0):
        self.enabled = enabled
        self.sample_rate = sample_rate  # 1.0 = 100% de requests
        
        self._function_stats: Dict[str, FunctionProfile] = defaultdict(
            lambda: FunctionProfile("", "", 0)
        )
        self._query_log: List[Dict] = []
        self._snapshots: List[PerformanceSnapshot] = []
        
        # Query detection
        self._query_count = 0
        self._query_start_time: Optional[float] = None
        
        # Memory tracking
        self._memory_tracking = False
    
    def profile(self, func: Callable) -> Callable:
        """
        Decorador para perfilar una función.
        
        Captura tiempo de ejecución, uso de memoria, y queries.
        """
        if not self.enabled:
            return func
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Sample rate check
            if self.sample_rate < 1.0 and hash(func.__name__) % 100 > self.sample_rate * 100:
                return func(*args, **kwargs)
            
            # Pre-execution
            gc.collect()
            mem_before = self._get_memory_usage()
            start_time = time.perf_counter()
            
            query_count_before = self._query_count
            
            try:
                result = func(*args, **kwargs)
                status = "success"
                return result
            except Exception as e:
                status = "error"
                raise
            finally:
                # Post-execution
                end_time = time.perf_counter()
                duration = end_time - start_time
                mem_after = self._get_memory_usage()
                
                # Update stats
                self._update_function_stats(
                    func=func,
                    duration=duration,
                    memory_delta=mem_after - mem_before,
                    db_queries=self._query_count - query_count_before,
                    status=status
                )
                
                # Check thresholds
                self._check_thresholds(func.__name__, duration, mem_after - mem_before)
        
        return wrapper
    
    @contextmanager
    def profile_block(self, name: str, tags: Optional[Dict] = None):
        """
        Context manager para perfilar un bloque de código.
        
        Uso:
            with profiler.profile_block("db_query"):
                resultado = db.query(...)
        """
        if not self.enabled:
            yield
            return
        
        start_time = time.perf_counter()
        mem_before = self._get_memory_usage()
        
        try:
            yield
        finally:
            duration = time.perf_counter() - start_time
            mem_delta = self._get_memory_usage() - mem_before
            
            # Track as metric
            track_metric(f"block_{name}_duration", duration, tags)
            
            if duration > self.SLOW_FUNCTION_THRESHOLD:
                log_event("perf_slow_block", f"{name}: {duration:.3f}s")
    
    def _update_function_stats(
        self,
        func: Callable,
        duration: float,
        memory_delta: int,
        db_queries: int,
        status: str
    ):
        """Actualiza estadísticas de función."""
        key = f"{func.__module__}.{func.__name__}"
        
        if key not in self._function_stats:
            self._function_stats[key] = FunctionProfile(
                name=func.__name__,
                filename=func.__code__.co_filename,
                lineno=func.__code__.co_firstlineno
            )
        
        stats = self._function_stats[key]
        stats.call_count += 1
        stats.total_time += duration
        stats.min_time = min(stats.min_time, duration)
        stats.max_time = max(stats.max_time, duration)
        stats.avg_time = stats.total_time / stats.call_count
        stats.memory_usage += memory_delta
        stats.peak_memory = max(stats.peak_memory, memory_delta)
        stats.db_queries += db_queries
        
        # Track as metric
        track_metric(f"function_{func.__name__}_duration", duration, tags={"status": status})
    
    def _check_thresholds(self, func_name: str, duration: float, memory_delta: int):
        """Verifica umbrales y genera alertas."""
        alerts = []
        
        if duration > self.SLOW_FUNCTION_THRESHOLD:
            alert = f"🐌 Función lenta: {func_name} ({duration:.3f}s)"
            alerts.append(alert)
            log_event("perf_slow_function", f"{func_name}: {duration:.3f}s")
        
        if memory_delta > self.MEMORY_ALERT_THRESHOLD:
            alert = f"💾 Alto uso de memoria: {func_name} ({memory_delta / 1024 / 1024:.1f}MB)"
            alerts.append(alert)
            log_event("perf_high_memory", f"{func_name}: {memory_delta} bytes")
        
        # Notificar si hay alertas
        if alerts and hasattr(st, 'session_state'):
            if '_perf_alerts' not in st.session_state:
                st.session_state['_perf_alerts'] = []
            st.session_state['_perf_alerts'].extend(alerts)
    
    def _get_memory_usage(self) -> int:
        """Obtiene uso actual de memoria en bytes. Fallback si psutil no está disponible."""
        try:
            import psutil
            process = psutil.Process()
            return process.memory_info().rss
        except ImportError:
            # Fallback: tracemalloc si está activo, sino 0
            try:
                import tracemalloc
                if tracemalloc.is_tracing():
                    current, _ = tracemalloc.get_traced_memory()
                    return current
            except Exception:
                pass
            return 0
    
    def log_query(self, query: str, duration: float, params: Optional[Dict] = None):
        """
        Loguea una query de base de datos.
        
        Uso:
            profiler.log_query("SELECT * FROM pacientes", duration=0.05)
        """
        self._query_count += 1
        
        query_info = {
            "query": query[:200],  # Truncar queries largas
            "duration": duration,
            "params": params,
            "timestamp": time.time()
        }
        
        self._query_log.append(query_info)
        
        # Detectar queries lentas
        if duration > self.SLOW_QUERY_THRESHOLD:
            log_event("perf_slow_query", f"{duration:.3f}s: {query[:100]}")
            
            # Detectar N+1 queries
            if self._detect_n_plus_1(query):
                log_event("perf_n_plus_1", f"Posible N+1 detectado: {query[:100]}")
    
    def _detect_n_plus_1(self, query: str) -> bool:
        """Detecta patrón N+1 queries."""
        # Simple heuristic: muchas queries similares en poco tiempo
        recent_queries = [
            q for q in self._query_log[-10:]
            if time.time() - q["timestamp"] < 1.0
        ]
        
        if len(recent_queries) < 5:
            return False
        
        # Contar queries similares
        query_pattern = query.split("WHERE")[0]  # Normalizar
        similar_count = sum(
            1 for q in recent_queries
            if q["query"].split("WHERE")[0] == query_pattern
        )
        
        return similar_count >= 5
    
    def get_slow_functions(self, threshold: Optional[float] = None) -> List[FunctionProfile]:
        """Retorna funciones lentas ordenadas por tiempo total."""
        threshold = threshold or self.SLOW_FUNCTION_THRESHOLD
        
        slow = [
            stats for stats in self._function_stats.values()
            if stats.avg_time > threshold
        ]
        
        return sorted(slow, key=lambda x: x.total_time, reverse=True)
    
    def get_slow_queries(self, limit: int = 10) -> List[Dict]:
        """Retorna queries más lentas."""
        sorted_queries = sorted(
            self._query_log,
            key=lambda x: x["duration"],
            reverse=True
        )
        return sorted_queries[:limit]
    
    def take_snapshot(self) -> PerformanceSnapshot:
        """Toma snapshot actual del sistema."""
        gc.collect()
        
        snapshot = PerformanceSnapshot(
            timestamp=time.time(),
            function_stats=dict(self._function_stats),
            memory_current=self._get_memory_usage(),
            memory_peak=max((s.peak_memory for s in self._function_stats.values()), default=0),
            gc_collections=gc.get_count()[0],
            total_queries=self._query_count,
            slow_queries=self.get_slow_queries(5),
            alerts=getattr(st.session_state, '_perf_alerts', [])
        )
        
        self._snapshots.append(snapshot)
        
        # Limpiar alerts
        if hasattr(st, 'session_state'):
            st.session_state['_perf_alerts'] = []
        
        return snapshot
    
    def export_stats(self, format: str = "json") -> str:
        """Exporta estadísticas a string."""
        if format == "json":
            data = {
                "functions": {
                    name: {
                        "call_count": s.call_count,
                        "total_time": s.total_time,
                        "avg_time": s.avg_time,
                        "max_time": s.max_time,
                        "db_queries": s.db_queries
                    }
                    for name, s in self._function_stats.items()
                },
                "slow_functions": [
                    {
                        "name": s.name,
                        "avg_time": s.avg_time,
                        "total_time": s.total_time
                    }
                    for s in self.get_slow_functions()[:10]
                ],
                "slow_queries": self.get_slow_queries(10)
            }
            return json.dumps(data, indent=2)
        
        elif format == "pstats":
            # Exportar formato compatible con pstats
            stats = pstats.Stats()
            # ... (implementar si es necesario)
            return ""
        
        else:
            raise ValueError(f"Formato no soportado: {format}")
    
    def render_performance_dashboard(self):
        """Renderiza dashboard de performance en Streamlit."""
        import streamlit as st
        
        st.subheader("📊 Performance Dashboard")
        
        # Stats generales
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_calls = sum(s.call_count for s in self._function_stats.values())
            st.metric("Total Calls", total_calls)
        
        with col2:
            slow_count = len(self.get_slow_functions())
            st.metric("Slow Functions", slow_count, delta="⚠️" if slow_count > 0 else None)
        
        with col3:
            st.metric("DB Queries", self._query_count)
        
        with col4:
            mem_mb = self._get_memory_usage() / 1024 / 1024
            st.metric("Memory", f"{mem_mb:.1f} MB")
        
        # Funciones lentas
        if self.get_slow_functions():
            with st.expander("🐌 Slow Functions", expanded=True):
                slow_funcs = self.get_slow_functions()[:10]
                for func in slow_funcs:
                    st.text(
                        f"{func.name}: "
                        f"avg={func.avg_time:.3f}s, "
                        f"total={func.total_time:.3f}s, "
                        f"calls={func.call_count}"
                    )
        
        # Queries lentas
        if self.get_slow_queries():
            with st.expander("🐌 Slow Queries"):
                for query in self.get_slow_queries(10):
                    st.text(f"{query['duration']:.3f}s: {query['query'][:80]}")
        
        # Botón de snapshot
        if st.button("📸 Take Snapshot"):
            snapshot = self.take_snapshot()
            st.success(f"Snapshot taken! Memory: {snapshot.memory_current / 1024 / 1024:.1f}MB")
        
        # Exportar
        if st.button("📥 Export Stats"):
            stats_json = self.export_stats("json")
            st.download_button(
                "Download JSON",
                stats_json,
                file_name="performance_stats.json",
                mime="application/json"
            )


# Decorador global para fácil uso
def profiled(func: Callable) -> Callable:
    """Decorador simple para perfilar funciones."""
    profiler = get_profiler()
    return profiler.profile(func)


# Singleton global
_profiler_instance: Optional[PerformanceProfiler] = None


def get_profiler() -> PerformanceProfiler:
    """Obtiene instancia global del profiler."""
    global _profiler_instance
    if _profiler_instance is None:
        _profiler_instance = PerformanceProfiler()
    return _profiler_instance


# Context manager global
@contextmanager
def profile_block(name: str):
    """Context manager para perfilar bloques de código."""
    profiler = get_profiler()
    with profiler.profile_block(name):
        yield


def log_query(query: str, duration: float, params: Optional[Dict] = None):
    """Helper para loguear queries."""
    profiler = get_profiler()
    profiler.log_query(query, duration, params)
