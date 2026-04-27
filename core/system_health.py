"""
Monitoreo de Salud del Sistema para Medicare Pro.

Verifica:
- Conectividad a bases de datos
- Estado de caché
- Espacio en disco
- Memoria disponible
- Tiempo de respuesta
- Dependencias externas

Proporciona:
- Health checks periódicos
- Alertas automáticas
- Dashboard de estado
- Recomendaciones de optimización
"""

from __future__ import annotations

import os
import psutil
import sqlite3
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum, auto
from pathlib import Path

import streamlit as st

from core.app_logging import log_event
from core.distributed_cache import get_cache
from core.audit_trail import audit_log, AuditEventType


class HealthStatus(Enum):
    """Estados de salud posibles."""
    HEALTHY = "healthy"      # Todo OK
    DEGRADED = "degraded"    # Funcionando pero con problemas
    UNHEALTHY = "unhealthy"  # Fallo crítico
    UNKNOWN = "unknown"       # No se pudo verificar


@dataclass
class HealthCheck:
    """Resultado de un health check individual."""
    name: str
    status: HealthStatus
    response_time_ms: float
    message: str
    details: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    suggestions: List[str] = field(default_factory=list)


@dataclass
class SystemHealthReport:
    """Reporte completo de salud del sistema."""
    overall_status: HealthStatus
    checks: List[HealthCheck]
    timestamp: datetime
    uptime_seconds: float
    version: str
    environment: str
    
    @property
    def healthy_count(self) -> int:
        return sum(1 for c in self.checks if c.status == HealthStatus.HEALTHY)
    
    @property
    def degraded_count(self) -> int:
        return sum(1 for c in self.checks if c.status == HealthStatus.DEGRADED)
    
    @property
    def unhealthy_count(self) -> int:
        return sum(1 for c in self.checks if c.status == HealthStatus.UNHEALTHY)


class SystemHealthMonitor:
    """
    Monitor de salud del sistema.
    
    Ejecuta checks periódicos y genera reportes.
    """
    
    # Umbrales de alerta
    DISK_WARNING_PERCENT = 85
    DISK_CRITICAL_PERCENT = 95
    MEMORY_WARNING_PERCENT = 80
    MEMORY_CRITICAL_PERCENT = 95
    RESPONSE_TIME_WARNING_MS = 500
    RESPONSE_TIME_CRITICAL_MS = 2000
    
    def __init__(self):
        self._checks: Dict[str, Callable[[], HealthCheck]] = {}
        self._last_report: Optional[SystemHealthReport] = None
        self._start_time = datetime.now()
        
        # Registrar checks por defecto
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Registra los checks de salud por defecto."""
        self.register_check("database", self._check_database)
        self.register_check("cache", self._check_cache)
        self.register_check("disk", self._check_disk_space)
        self.register_check("memory", self._check_memory)
        self.register_check("session_state", self._check_session_state)
        self.register_check("supabase", self._check_supabase)
    
    def register_check(self, name: str, check_fn: Callable[[], HealthCheck]):
        """Registra un nuevo check de salud."""
        self._checks[name] = check_fn
    
    def run_health_check(self, check_name: Optional[str] = None) -> SystemHealthReport:
        """
        Ejecuta health checks.
        
        Args:
            check_name: Si especificado, solo ejecuta ese check
        
        Returns:
            SystemHealthReport con resultados
        """
        checks_to_run = {check_name: self._checks[check_name]} if check_name else self._checks
        
        results = []
        overall_status = HealthStatus.HEALTHY
        
        for name, check_fn in checks_to_run.items():
            try:
                start_time = time.time()
                check = check_fn()
                check.response_time_ms = (time.time() - start_time) * 1000
                results.append(check)
                
                # Determinar overall status
                if check.status == HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.UNHEALTHY
                elif check.status == HealthStatus.DEGRADED and overall_status != HealthStatus.UNHEALTHY:
                    overall_status = HealthStatus.DEGRADED
                    
            except Exception as e:
                results.append(HealthCheck(
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    response_time_ms=0,
                    message=f"Check failed with exception: {str(e)}",
                    details={"error": str(e)}
                ))
                overall_status = HealthStatus.UNHEALTHY
        
        # Calcular uptime
        uptime = (datetime.now() - self._start_time).total_seconds()
        
        report = SystemHealthReport(
            overall_status=overall_status,
            checks=results,
            timestamp=datetime.now(),
            uptime_seconds=uptime,
            version=self._get_version(),
            environment=os.getenv("MEDICARE_ENV", "unknown")
        )
        
        self._last_report = report
        
        # Log si hay problemas
        if overall_status != HealthStatus.HEALTHY:
            log_event("health_check", f"System health degraded: {overall_status.value}")
        
        return report
    
    def _check_database(self) -> HealthCheck:
        """Verifica conectividad a base de datos local."""
        start_time = time.time()
        
        try:
            # Intentar acceder a session_state como proxy de DB
            _ = st.session_state.get("pacientes_db", {})
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheck(
                name="database",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                message="Local database accessible",
                details={"type": "session_state"}
            )
            
        except Exception as e:
            return HealthCheck(
                name="database",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                message=f"Database access failed: {str(e)}",
                suggestions=["Verificar permisos de escritura", "Reiniciar aplicación"]
            )
    
    def _check_cache(self) -> HealthCheck:
        """Verifica estado de caché."""
        start_time = time.time()
        
        try:
            cache = get_cache()
            
            # Intentar operación simple
            cache.set("health_check_test", "test_value", ttl=10)
            value = cache.get("health_check_test")
            
            response_time = (time.time() - start_time) * 1000
            
            if value == "test_value":
                stats = cache.get_stats()
                
                return HealthCheck(
                    name="cache",
                    status=HealthStatus.HEALTHY,
                    response_time_ms=response_time,
                    message="Cache operational",
                    details=stats
                )
            else:
                return HealthCheck(
                    name="cache",
                    status=HealthStatus.DEGRADED,
                    response_time_ms=response_time,
                    message="Cache read/write mismatch",
                    suggestions=["Verificar configuración de Redis"]
                )
                
        except Exception as e:
            return HealthCheck(
                name="cache",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                message=f"Cache error: {str(e)}",
                suggestions=["Verificar conexión a Redis", "Revisar REDIS_URL"]
            )
    
    def _check_disk_space(self) -> HealthCheck:
        """Verifica espacio en disco."""
        start_time = time.time()
        
        try:
            disk = psutil.disk_usage('/')
            percent_used = disk.percent
            
            response_time = (time.time() - start_time) * 1000
            
            if percent_used >= self.DISK_CRITICAL_PERCENT:
                status = HealthStatus.UNHEALTHY
                message = f"CRITICAL: Disk {percent_used}% full"
            elif percent_used >= self.DISK_WARNING_PERCENT:
                status = HealthStatus.DEGRADED
                message = f"WARNING: Disk {percent_used}% full"
            else:
                status = HealthStatus.HEALTHY
                message = f"Disk space OK ({percent_used}% used)"
            
            return HealthCheck(
                name="disk",
                status=status,
                response_time_ms=response_time,
                message=message,
                details={
                    "total_gb": disk.total / (1024**3),
                    "used_gb": disk.used / (1024**3),
                    "free_gb": disk.free / (1024**3),
                    "percent_used": percent_used
                },
                suggestions=["Limpiar logs antiguos", "Eliminar backups viejos"] if status != HealthStatus.HEALTHY else []
            )
            
        except Exception as e:
            return HealthCheck(
                name="disk",
                status=HealthStatus.UNKNOWN,
                response_time_ms=0,
                message=f"Cannot check disk: {str(e)}"
            )
    
    def _check_memory(self) -> HealthCheck:
        """Verifica uso de memoria."""
        start_time = time.time()
        
        try:
            memory = psutil.virtual_memory()
            percent_used = memory.percent
            
            response_time = (time.time() - start_time) * 1000
            
            if percent_used >= self.MEMORY_CRITICAL_PERCENT:
                status = HealthStatus.UNHEALTHY
                message = f"CRITICAL: Memory {percent_used}% used"
            elif percent_used >= self.MEMORY_WARNING_PERCENT:
                status = HealthStatus.DEGRADED
                message = f"WARNING: Memory {percent_used}% used"
            else:
                status = HealthStatus.HEALTHY
                message = f"Memory OK ({percent_used}% used)"
            
            return HealthCheck(
                name="memory",
                status=status,
                response_time_ms=response_time,
                message=message,
                details={
                    "total_gb": memory.total / (1024**3),
                    "available_gb": memory.available / (1024**3),
                    "percent_used": percent_used
                },
                suggestions=["Reiniciar aplicación", "Verificar fugas de memoria"] if status != HealthStatus.HEALTHY else []
            )
            
        except Exception as e:
            return HealthCheck(
                name="memory",
                status=HealthStatus.UNKNOWN,
                response_time_ms=0,
                message=f"Cannot check memory: {str(e)}"
            )
    
    def _check_session_state(self) -> HealthCheck:
        """Verifica estado de session_state."""
        start_time = time.time()
        
        try:
            # Contar elementos en session_state
            total_keys = len(st.session_state.keys())
            
            # Verificar tamaño aproximado
            size_estimate = 0
            for key in ['pacientes_db', 'evoluciones_db', 'vitales_db', 'usuarios_db']:
                if key in st.session_state:
                    data = st.session_state[key]
                    if isinstance(data, dict):
                        size_estimate += len(data)
                    elif isinstance(data, list):
                        size_estimate += len(data)
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheck(
                name="session_state",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                message=f"Session state healthy ({total_keys} keys, ~{size_estimate} records)",
                details={
                    "total_keys": total_keys,
                    "estimated_records": size_estimate
                }
            )
            
        except Exception as e:
            return HealthCheck(
                name="session_state",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start_time) * 1000,
                message=f"Session state error: {str(e)}"
            )
    
    def _check_supabase(self) -> HealthCheck:
        """Verifica conectividad a Supabase."""
        start_time = time.time()
        
        supabase_url = os.getenv("SUPABASE_URL", "")
        if not supabase_url:
            return HealthCheck(
                name="supabase",
                status=HealthStatus.UNKNOWN,
                response_time_ms=0,
                message="Supabase not configured"
            )
        
        try:
            # Intentar importar y conectar
            from core._database_supabase import get_supabase_client
            
            client = get_supabase_client()
            
            # Query simple de prueba
            response = client.table("pacientes").select("count", count="exact").limit(1).execute()
            
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheck(
                name="supabase",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                message="Supabase connection OK",
                details={"url": supabase_url.split("@")[-1] if "@" in supabase_url else supabase_url}
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            
            return HealthCheck(
                name="supabase",
                status=HealthStatus.DEGRADED,  # Degraded, no crítico
                response_time_ms=response_time,
                message=f"Supabase connection issue: {str(e)}",
                suggestions=["Verificar SUPABASE_URL", "Verificar SUPABASE_KEY", "Verificar conectividad"]
            )
    
    def _get_version(self) -> str:
        """Obtiene versión de la aplicación."""
        try:
            from core.release_notes import RELEASES
            return RELEASES[0]["version"] if RELEASES else "unknown"
        except (ImportError, IndexError, KeyError):
            return "unknown"
    
    def render_health_dashboard(self):
        """Renderiza dashboard de salud en Streamlit."""
        st.title("🏥 System Health Monitor")
        
        # Ejecutar checks
        report = self.run_health_check()
        
        # Header con status general
        status_colors = {
            HealthStatus.HEALTHY: "🟢",
            HealthStatus.DEGRADED: "🟡",
            HealthStatus.UNHEALTHY: "🔴",
            HealthStatus.UNKNOWN: "⚪"
        }
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            emoji = status_colors.get(report.overall_status, "⚪")
            st.metric(
                "Overall Status",
                f"{emoji} {report.overall_status.value.upper()}"
            )
        
        with col2:
            st.metric("Healthy", report.healthy_count)
        
        with col3:
            st.metric("Degraded", report.degraded_count)
        
        with col4:
            st.metric("Unhealthy", report.unhealthy_count)
        
        # Uptime
        uptime_hours = report.uptime_seconds / 3600
        st.caption(f"⏱️ Uptime: {uptime_hours:.1f} hours | Version: {report.version} | Env: {report.environment}")
        
        st.divider()
        
        # Checks individuales
        st.subheader("Health Checks")
        
        for check in report.checks:
            with st.container():
                col1, col2, col3 = st.columns([1, 3, 1])
                
                with col1:
                    emoji = status_colors.get(check.status, "⚪")
                    st.markdown(f"### {emoji}")
                
                with col2:
                    st.markdown(f"**{check.name.upper()}**")
                    st.text(check.message)
                    
                    if check.suggestions:
                        with st.expander("💡 Suggestions"):
                            for suggestion in check.suggestions:
                                st.markdown(f"- {suggestion}")
                
                with col3:
                    st.caption(f"{check.response_time_ms:.1f}ms")
                    st.caption(check.timestamp.strftime("%H:%M:%S"))
            
            st.divider()
        
        # Botón de refresh
        if st.button("🔄 Refresh Health Check"):
            pass
        
        # Exportar reporte
        if st.button("📥 Export Health Report"):
            report_json = json.dumps({
                "overall_status": report.overall_status.value,
                "timestamp": report.timestamp.isoformat(),
                "uptime_seconds": report.uptime_seconds,
                "version": report.version,
                "environment": report.environment,
                "checks": [
                    {
                        "name": c.name,
                        "status": c.status.value,
                        "message": c.message,
                        "response_time_ms": c.response_time_ms
                    }
                    for c in report.checks
                ]
            }, indent=2)
            
            st.download_button(
                "Download JSON",
                report_json,
                file_name=f"health_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                mime="application/json"
            )


# Singleton
_health_monitor: Optional[SystemHealthMonitor] = None


def get_health_monitor() -> SystemHealthMonitor:
    """Obtiene instancia del monitor de salud."""
    global _health_monitor
    if _health_monitor is None:
        _health_monitor = SystemHealthMonitor()
    return _health_monitor


def quick_health_check() -> Dict[str, str]:
    """Health check rápido para usar en otras partes."""
    monitor = get_health_monitor()
    report = monitor.run_health_check()
    
    return {
        "status": report.overall_status.value,
        "healthy": str(report.healthy_count),
        "degraded": str(report.degraded_count),
        "unhealthy": str(report.unhealthy_count)
    }
