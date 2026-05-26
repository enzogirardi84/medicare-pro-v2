"""Monitoreo proactivo: alertas automaticas de salud del sistema.

Si la latencia supera un umbral o hay errores recurrentes,
notifica al administrador via log, toast o email.
Incluye panel de estado de servicios externos.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List

import streamlit as st

from core.app_logging import log_event


class ProactiveMonitor:
    """Monitorea la salud del sistema y genera alertas automaticas."""
    
    def __init__(self, latency_threshold_ms: float = 2000.0, error_threshold: int = 5):
        self.latency_threshold = latency_threshold_ms
        self.error_threshold = error_threshold
        self._window_minutes = 5
    
    def check_latency(self) -> List[Dict[str, Any]]:
        """Revisa si hay latencia alta en las ultimas queries."""
        alerts = []
        tel = st.session_state.get("telemetria", {})
        queries = tel.get("queries", [])
        
        recent = [q for q in queries if q.get("timestamp", 0) > time.time() - (self._window_minutes * 60)]
        slow = [q for q in recent if q.get("latencia_ms", 0) > self.latency_threshold]
        
        if slow:
            for q in slow[:3]:
                alerts.append({
                    "tipo": "latencia",
                    "severidad": "alta",
                    "mensaje": f"Latencia alta en {q['endpoint']}: {q['latencia_ms']:.0f}ms",
                    "timestamp": time.time(),
                })
                log_event("monitoreo", f"latencia_alta:{q['endpoint']}:{q['latencia_ms']:.0f}ms")
        
        return alerts
    
    def check_errors(self) -> List[Dict[str, Any]]:
        """Revisa errores frecuentes en los logs recientes."""
        alerts = []
        error_count = st.session_state.get("_monitoreo_error_count", 0)
        
        if error_count >= self.error_threshold:
            alerts.append({
                "tipo": "errores",
                "severidad": "critica",
                "mensaje": f"{error_count} errores detectados en los ultimos minutos",
                "timestamp": time.time(),
            })
            log_event("monitoreo", f"error_count_alto:{error_count}")
            st.session_state["_monitoreo_error_count"] = 0
        
        return alerts
    
    def check_circuit_breaker(self) -> List[Dict[str, Any]]:
        """Revisa el estado del Circuit Breaker de IA."""
        from services.asistente_ia import get_circuit_state
        state = get_circuit_state()
        
        if state["state"] == "open":
            return [{
                "tipo": "circuit_breaker",
                "severidad": "alta",
                "mensaje": f"Circuit Breaker IA abierto ({state['remaining_cooldown']:.0f}s restantes)",
                "timestamp": time.time(),
            }]
        return []
    
    def check_memory(self) -> List[Dict[str, Any]]:
        """Revisa uso de memoria del sistema."""
        alerts = []
        try:
            import psutil
            mem = psutil.virtual_memory()
            if mem.percent > 90:
                alerts.append({
                    "tipo": "memoria",
                    "severidad": "critica",
                    "mensaje": f"RAM al {mem.percent}% ({mem.used/1e9:.1f}/{mem.total/1e9:.1f} GB)",
                    "timestamp": time.time(),
                })
            elif mem.percent > 75:
                alerts.append({
                    "tipo": "memoria",
                    "severidad": "alta",
                    "mensaje": f"RAM al {mem.percent}% ({mem.used/1e9:.1f}/{mem.total/1e9:.1f} GB)",
                    "timestamp": time.time(),
                })
        except Exception:
            pass
        return alerts
    
    def check_session_state_size(self) -> List[Dict[str, Any]]:
        """Estima el tamano de session_state."""
        alerts = []
        try:
            import sys
            total = sum(sys.getsizeof(v) for v in st.session_state.values())
            if total > 50 * 1024 * 1024:
                alerts.append({
                    "tipo": "session_size",
                    "severidad": "alta",
                    "mensaje": f"SessionState grande: ~{total/1e6:.1f} MB",
                    "timestamp": time.time(),
                })
        except Exception:
            pass
        return alerts
    
    def run_all_checks(self) -> List[Dict[str, Any]]:
        """Ejecuta todas las verificaciones y retorna alertas."""
        alerts = []
        alerts.extend(self.check_latency())
        alerts.extend(self.check_errors())
        alerts.extend(self.check_circuit_breaker())
        alerts.extend(self.check_memory())
        alerts.extend(self.check_session_state_size())
        return alerts


def render_monitoreo_dashboard():
    """Renderiza el dashboard de monitoreo proactivo en settings."""
    monitor = ProactiveMonitor()
    alerts = monitor.run_all_checks()
    
    st.subheader("🚨 Monitoreo Proactivo")
    
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Umbral latencia", f"{monitor.latency_threshold:.0f}ms")
    col2.metric("Ventana", f"{monitor._window_minutes}min")
    col3.metric("Alertas", str(len(alerts)))
    col4.metric("Umbral errores", str(monitor.error_threshold))
    
    if alerts:
        for alert in alerts:
            sev = alert["severidad"]
            if sev == "critica":
                st.error(f"**{alert['tipo']}**: {alert['mensaje']}")
            elif sev == "alta":
                st.warning(f"**{alert['tipo']}**: {alert['mensaje']}")
            else:
                st.info(f"**{alert['tipo']}**: {alert['mensaje']}")
    else:
        st.success("Sistema saludable. Sin alertas activas.")
    
    if st.button("🔄 Forzar verificacion ahora", use_container_width=True):
        alerts = monitor.run_all_checks()
        if not alerts:
            st.success("Verificacion completada: 0 alertas.")
            st.rerun()


def track_error():
    """Incrementa contador de errores para el monitoreo."""
    st.session_state["_monitoreo_error_count"] = st.session_state.get("_monitoreo_error_count", 0) + 1
