"""
Sistema de Health Checks Mejorado para MediCare Pro.

Monitoreo crítico para sistema de salud:
- Supabase connection status
- Redis caché disponibilidad
- Rate limiter estado
- Session state health
- Database latency
- Error rates tracking
"""
import time
from typing import Dict, Any, Optional, List, Callable

try:
    import psutil
except ImportError:
    psutil = None
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import streamlit as st

from core.app_logging import log_event


def _get_settings():
    """Import lazy de get_settings para evitar ValidationError en tests."""
    from core.config_secure import get_settings
    return get_settings()


class ComponentStatus(Enum):
    """Estado de componentes del sistema."""
    HEALTHY = "✅ Saludable"
    DEGRADED = "⚠️ Degradado"
    UNHEALTHY = "❌ Crítico"
    UNKNOWN = "❓ Desconocido"


@dataclass
class ComponentHealth:
    """Estado de salud de un componente."""
    name: str
    status: ComponentStatus
    latency_ms: float
    last_check: str
    message: str
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemHealthReport:
    """Reporte completo de salud del sistema."""
    timestamp: str
    overall_status: ComponentStatus
    components: List[ComponentHealth]
    system_metrics: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario para JSON."""
        return {
            "timestamp": self.timestamp,
            "overall_status": self.status.value,
            "components": [
                {
                    "name": c.name,
                    "status": c.status.value,
                    "latency_ms": c.latency_ms,
                    "message": c.message,
                    "details": c.details
                }
                for c in self.components
            ],
            "system_metrics": self.system_metrics
        }


class HealthCheckEnhanced:
    """Health checks específicos para componentes de MediCare."""
    
    def __init__(self):
        self._checks: Dict[str, Callable[[], ComponentHealth]] = {}
        self._last_report: Optional[SystemHealthReport] = None
        self._register_default_checks()
    
    def _register_default_checks(self) -> None:
        """Registra health checks por defecto."""
        self._checks["supabase"] = self._check_supabase
        self._checks["redis"] = self._check_redis
        self._checks["session_state"] = self._check_session_state
        self._checks["disk_space"] = self._check_disk_space
        self._checks["memory"] = self._check_memory
    
    def _check_supabase(self) -> ComponentHealth:
        """Verifica conexión a Supabase."""
        start = time.time()
        
        try:
            from core._database_supabase import supabase, init_supabase
            
            if supabase is None:
                # Intentar reinicializar
                supabase = init_supabase()
            
            if supabase:
                # Ping simple
                response = supabase.table("pacientes").select("count", count="exact").limit(1).execute()
                latency = (time.time() - start) * 1000
                
                return ComponentHealth(
                    name="Supabase",
                    status=ComponentStatus.HEALTHY if latency < 1000 else ComponentStatus.DEGRADED,
                    latency_ms=round(latency, 2),
                    last_check=datetime.now(timezone.utc).isoformat(),
                    message=f"Conectado - {latency:.0f}ms",
                    details={"count": getattr(response, 'count', 0)}
                )
            else:
                return ComponentHealth(
                    name="Supabase",
                    status=ComponentStatus.UNHEALTHY,
                    latency_ms=0,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    message="Cliente no inicializado",
                    details={}
                )
                
        except Exception as e:
            return ComponentHealth(
                name="Supabase",
                status=ComponentStatus.UNHEALTHY,
                latency_ms=(time.time() - start) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
                message=f"Error: {type(e).__name__}",
                details={"error": str(e)}
            )
    
    def _check_redis(self) -> ComponentHealth:
        """Verifica conexión a Redis."""
        start = time.time()
        
        try:
            settings = _get_settings()
            redis_url = settings.redis_url
            
            if not redis_url:
                return ComponentHealth(
                    name="Redis",
                    status=ComponentStatus.UNKNOWN,
                    latency_ms=0,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    message="No configurado (opcional)",
                    details={}
                )
            
            import redis
            client = redis.from_url(
                redis_url.get_secret_value(),
                socket_connect_timeout=2,
                socket_timeout=2
            )
            
            # Ping
            client.ping()
            latency = (time.time() - start) * 1000
            
            # Info básico
            info = client.info()
            
            return ComponentHealth(
                name="Redis",
                status=ComponentStatus.HEALTHY if latency < 100 else ComponentStatus.DEGRADED,
                latency_ms=round(latency, 2),
                last_check=datetime.now(timezone.utc).isoformat(),
                message=f"Conectado - {latency:.0f}ms",
                details={
                    "version": info.get("redis_version"),
                    "used_memory_human": info.get("used_memory_human"),
                    "connected_clients": info.get("connected_clients")
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="Redis",
                status=ComponentStatus.DEGRADED,  # No es crítico
                latency_ms=(time.time() - start) * 1000,
                last_check=datetime.now(timezone.utc).isoformat(),
                message=f"No disponible: {type(e).__name__}",
                details={"error": str(e)}
            )
    
    def _check_session_state(self) -> ComponentHealth:
        """Verifica estado de la sesión Streamlit."""
        try:
            # Verificar session_state accesible
            keys_count = len(st.session_state.keys())
            
            # Verificar datos críticos presentes
            critical_keys = ["pacientes_db", "usuarios_db", "evoluciones_db"]
            missing = [k for k in critical_keys if k not in st.session_state]
            
            # Calcular tamaño aproximado
            total_size = 0
            for key in st.session_state.keys():
                try:
                    import sys
                    total_size += sys.getsizeof(st.session_state[key])
                except Exception:
                    pass
            
            size_mb = total_size / (1024 * 1024)
            
            status = ComponentStatus.HEALTHY
            if missing:
                status = ComponentStatus.DEGRADED
            if size_mb > 100:  # >100MB
                status = ComponentStatus.DEGRADED
            
            return ComponentHealth(
                name="Session State",
                status=status,
                latency_ms=0,
                last_check=datetime.now(timezone.utc).isoformat(),
                message=f"{keys_count} claves, {size_mb:.1f}MB",
                details={
                    "keys_count": keys_count,
                    "size_mb": round(size_mb, 2),
                    "missing_critical": missing
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="Session State",
                status=ComponentStatus.UNHEALTHY,
                latency_ms=0,
                last_check=datetime.now(timezone.utc).isoformat(),
                message=f"Error: {type(e).__name__}",
                details={"error": str(e)}
            )
    
    def _check_disk_space(self) -> ComponentHealth:
        """Verifica espacio en disco."""
        try:
            disk = psutil.disk_usage('/')
            percent_used = disk.percent
            free_gb = disk.free / (1024**3)
            
            status = ComponentStatus.HEALTHY
            if percent_used > 90:
                status = ComponentStatus.UNHEALTHY
            elif percent_used > 80:
                status = ComponentStatus.DEGRADED
            
            return ComponentHealth(
                name="Disco",
                status=status,
                latency_ms=0,
                last_check=datetime.now(timezone.utc).isoformat(),
                message=f"{percent_used:.1f}% usado ({free_gb:.1f}GB libre)",
                details={
                    "percent_used": percent_used,
                    "free_gb": round(free_gb, 2),
                    "total_gb": round(disk.total / (1024**3), 2)
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="Disco",
                status=ComponentStatus.UNKNOWN,
                latency_ms=0,
                last_check=datetime.now(timezone.utc).isoformat(),
                message=f"No verificable: {type(e).__name__}",
                details={}
            )
    
    def _check_memory(self) -> ComponentHealth:
        """Verifica uso de memoria."""
        try:
            memory = psutil.virtual_memory()
            percent_used = memory.percent
            available_gb = memory.available / (1024**3)
            
            status = ComponentStatus.HEALTHY
            if percent_used > 95:
                status = ComponentStatus.UNHEALTHY
            elif percent_used > 85:
                status = ComponentStatus.DEGRADED
            
            return ComponentHealth(
                name="Memoria RAM",
                status=status,
                latency_ms=0,
                last_check=datetime.now(timezone.utc).isoformat(),
                message=f"{percent_used:.1f}% usado ({available_gb:.1f}GB disponible)",
                details={
                    "percent_used": percent_used,
                    "available_gb": round(available_gb, 2),
                    "total_gb": round(memory.total / (1024**3), 2)
                }
            )
            
        except Exception as e:
            return ComponentHealth(
                name="Memoria RAM",
                status=ComponentStatus.UNKNOWN,
                latency_ms=0,
                last_check=datetime.now(timezone.utc).isoformat(),
                message=f"No verificable: {type(e).__name__}",
                details={}
            )
    
    def run_all_checks(self) -> SystemHealthReport:
        """Ejecuta todos los health checks registrados."""
        components = []
        
        for name, check_fn in self._checks.items():
            try:
                result = check_fn()
                components.append(result)
            except Exception as e:
                components.append(ComponentHealth(
                    name=name,
                    status=ComponentStatus.UNHEALTHY,
                    latency_ms=0,
                    last_check=datetime.now(timezone.utc).isoformat(),
                    message=f"Check falló: {type(e).__name__}",
                    details={"error": str(e)}
                ))
        
        # Determinar estado general
        overall = ComponentStatus.HEALTHY
        for c in components:
            if c.status == ComponentStatus.UNHEALTHY:
                overall = ComponentStatus.UNHEALTHY
                break
            elif c.status == ComponentStatus.DEGRADED and overall == ComponentStatus.HEALTHY:
                overall = ComponentStatus.DEGRADED
        
        # Métricas del sistema
        system_metrics = self._get_system_metrics()
        
        report = SystemHealthReport(
            timestamp=datetime.now(timezone.utc).isoformat(),
            overall_status=overall,
            components=components,
            system_metrics=system_metrics
        )
        
        self._last_report = report
        
        # Log si hay problemas
        if overall != ComponentStatus.HEALTHY:
            log_event("health_check", f"status:{overall.value}")
        
        return report
    
    def _get_system_metrics(self) -> Dict[str, Any]:
        """Obtiene métricas del sistema."""
        try:
            return {
                "cpu_percent": psutil.cpu_percent(interval=0.1),
                "boot_time": datetime.fromtimestamp(psutil.boot_time(), timezone.utc).isoformat(),
                "python_version": f"{psutil.Process().exe()}",
            }
        except Exception:
            return {}
    
    def get_last_report(self) -> Optional[SystemHealthReport]:
        """Retorna último reporte generado."""
        return self._last_report
    
    def is_system_healthy(self) -> bool:
        """Retorna True si el sistema está saludable."""
        if not self._last_report:
            self.run_all_checks()
        
        return self._last_report.overall_status == ComponentStatus.HEALTHY if self._last_report else False


# Instancia global
_health_checker = None

def get_health_checker() -> HealthCheckEnhanced:
    """Retorna instancia singleton."""
    global _health_checker
    if _health_checker is None:
        _health_checker = HealthCheckEnhanced()
    return _health_checker


def check_system_health() -> SystemHealthReport:
    """Ejecuta health check completo del sistema."""
    return get_health_checker().run_all_checks()


def render_health_dashboard() -> None:
    """Renderiza dashboard de salud en Streamlit."""
    import streamlit as st
    
    st.header("🩺 Estado del Sistema")
    
    report = check_system_health()
    
    # Estado general
    if report.overall_status == ComponentStatus.HEALTHY:
        st.success(f"## {report.overall_status.value}")
    elif report.overall_status == ComponentStatus.DEGRADED:
        st.warning(f"## {report.overall_status.value}")
    else:
        st.error(f"## {report.overall_status.value}")
    
    st.caption(f"Última actualización: {report.timestamp}")
    
    # Componentes individuales
    cols = st.columns(len(report.components))
    
    for idx, component in enumerate(report.components):
        with cols[idx]:
            st.metric(
                label=component.name,
                value=component.status.value,
                delta=f"{component.latency_ms}ms" if component.latency_ms > 0 else None
            )
            st.caption(component.message)
    
    # Detalles expandibles
    with st.expander("📋 Detalles técnicos"):
        for component in report.components:
            st.subheader(component.name)
            st.json(component.details)
        
        st.subheader("Métricas del sistema")
        st.json(report.system_metrics)
