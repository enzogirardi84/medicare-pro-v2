"""Telemetria y monitoreo de rendimiento del sistema.

Mide tiempos de ejecucion de consultas, eficiencia de cache,
y expone dashboard en tiempo real para administracion.
"""

from __future__ import annotations

import time
from functools import wraps
from typing import Any, Callable, Dict, List

import streamlit as st

from core.app_logging import log_event


def track_time(metric_name: str = "") -> Callable:
    """Decorador que mide tiempo de ejecucion y lo registra en session_state.

    Uso:
        @track_time("get_pacientes")
        def fetch_pacientes():
            ...
    """
    def decorator(func: Callable) -> Callable:
        name = metric_name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            if "telemetria" not in st.session_state:
                st.session_state.telemetria = {"queries": [], "total_ops": 0, "avg_latency_ms": 0.0}

            inicio = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                fin = time.perf_counter()
                duracion_ms = (fin - inicio) * 1000

                tel = st.session_state.telemetria
                tel["queries"].append({"endpoint": name, "latencia_ms": round(duracion_ms, 2), "timestamp": time.time()})
                # Mantener solo ultimas 100 queries
                if len(tel["queries"]) > 100:
                    tel["queries"] = tel["queries"][-100:]
                tel["total_ops"] = len(tel["queries"])
                tel["avg_latency_ms"] = round(sum(q["latencia_ms"] for q in tel["queries"]) / max(len(tel["queries"]), 1), 2)

        return wrapper
    return decorator


def get_telemetria_stats() -> Dict[str, Any]:
    """Retorna estadisticas actuales de telemetria."""
    tel = st.session_state.get("telemetria", {"queries": [], "total_ops": 0, "avg_latency_ms": 0.0})
    return {
        "total_ops": tel["total_ops"],
        "avg_latency_ms": tel["avg_latency_ms"],
        "min_latency_ms": min((q["latencia_ms"] for q in tel["queries"]), default=0.0),
        "max_latency_ms": max((q["latencia_ms"] for q in tel["queries"]), default=0.0),
        "queries_recientes": tel["queries"][-10:],
    }


def render_telemetria_dashboard():
    """Renderiza dashboard de telemetria en la UI de settings."""
    stats = get_telemetria_stats()

    st.subheader("📊 Telemetria e Infraestructura Medica")

    if stats["total_ops"] == 0:
        st.info("Monitor analizando trazas de red... Las metricas apareceran al usar la aplicacion.")
        return

    col1, col2, col3 = st.columns(3)
    col1.metric("Latencia Media DB", f"{stats['avg_latency_ms']:.1f} ms",
                delta=f"{stats['min_latency_ms']:.0f}-{stats['max_latency_ms']:.0f} ms")
    col2.metric("Operaciones Registradas", str(stats["total_ops"]))

    from services.asistente_ia import get_circuit_state
    cb = get_circuit_state()
    status = "🟢 ACTIVO" if cb["state"] == "closed" else f"🔴 ABIERTO ({cb['remaining_cooldown']:.0f}s restantes)"
    col3.metric("Estado Circuit Breaker IA", status)

    with st.expander("Ultimas consultas", expanded=False):
        for q in stats["queries_recientes"][-5:]:
            st.caption(f"{q['endpoint']}: {q['latencia_ms']}ms")
