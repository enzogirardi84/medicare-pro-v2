"""
Sistema de Health Checks y Monitoreo para millones de usuarios.

- Health checks múltiples: DB, API, caché, rate limiter
- Métricas agregadas por tenant
- Alertas automáticas por umbrales
- Dashboard de estado del sistema
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple

import streamlit as st

from core.app_logging import log_event


class HealthStatus(Enum):
    """Estados de salud de componentes."""
    HEALTHY = "healthy"      # Funcionando normal
    DEGRADED = "degraded"    # Funcionando con problemas
    UNHEALTHY = "unhealthy"  # No funcional
    UNKNOWN = "unknown"      # Sin información


class Severity(Enum):
    """Niveles de severidad para alertas."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class HealthCheckResult:
    """Resultado de un health check individual."""
    component: str
    status: HealthStatus
    response_time_ms: float
    last_check: float
    message: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class SystemMetrics:
    """Métricas del sistema agregadas."""
    timestamp: float
    active_users: int = 0
    requests_per_minute: float = 0.0
    avg_response_time_ms: float = 0.0
    error_rate: float = 0.0
    cache_hit_rate: float = 0.0
    db_connection_count: int = 0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0


@dataclass
class Alert:
    """Alerta del sistema."""
    id: str
    severity: Severity
    component: str
    message: str
    timestamp: float
    resolved: bool = False
    resolved_at: Optional[float] = None


class HealthCheck:
    """Definición de un health check."""

    def __init__(
        self,
        name: str,
        check_fn: Callable[[], Tuple[HealthStatus, str, Dict[str, Any]]],
        interval_seconds: float = 60.0,
        timeout_seconds: float = 5.0,
        critical: bool = True,
    ):
        self.name = name
        self.check_fn = check_fn
        self.interval = interval_seconds
        self.timeout = timeout_seconds
        self.critical = critical
        self._last_result: Optional[HealthCheckResult] = None
        self._last_check_time: float = 0.0

    def run(self) -> HealthCheckResult:
        """Ejecuta el health check."""
        start = time.time()

        try:
            status, message, details = self.check_fn()
            response_time = (time.time() - start) * 1000

            result = HealthCheckResult(
                component=self.name,
                status=status,
                response_time_ms=response_time,
                last_check=start,
                message=message,
                details=details,
            )
        except Exception as e:
            result = HealthCheckResult(
                component=self.name,
                status=HealthStatus.UNHEALTHY,
                response_time_ms=(time.time() - start) * 1000,
                last_check=start,
                message=f"Error ejecutando check: {str(e)}",
                details={"error": str(e)},
            )

        self._last_result = result
        self._last_check_time = start
        return result

    def should_run(self) -> bool:
        """Determina si debe ejecutarse según el intervalo."""
        return time.time() - self._last_check_time >= self.interval


class HealthMonitor:
    """
    Monitor de salud del sistema con checks periódicos.
    """

    def __init__(
        self,
        check_interval: float = 30.0,
        metrics_window_seconds: float = 300.0,
    ):
        self.check_interval = check_interval
        self.metrics_window = metrics_window_seconds
        self._checks: Dict[str, HealthCheck] = {}
        self._check_results: Dict[str, HealthCheckResult] = {}
        self._metrics_history: List[SystemMetrics] = []
        self._alerts: List[Alert] = []
        self._alert_thresholds: Dict[str, Tuple[float, Severity]] = {}
        self._lock = threading.Lock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

    def register_check(self, check: HealthCheck):
        """Registra un nuevo health check."""
        with self._lock:
            self._checks[check.name] = check

    def set_alert_threshold(
        self,
        metric_name: str,
        threshold: float,
        severity: Severity = Severity.WARNING,
    ):
        """Configura umbral de alerta para una métrica."""
        self._alert_thresholds[metric_name] = (threshold, severity)

    def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Ejecuta todos los health checks pendientes."""
        results = {}

        for name, check in self._checks.items():
            if check.should_run():
                result = check.run()
                with self._lock:
                    self._check_results[name] = result
                results[name] = result

                # Generar alertas si es necesario
                self._evaluate_alert(result)

        return results

    def _evaluate_alert(self, result: HealthCheckResult):
        """Evalúa si se debe generar una alerta."""
        if result.status == HealthStatus.HEALTHY:
            # Resolver alertas abiertas para este componente
            for alert in self._alerts:
                if alert.component == result.component and not alert.resolved:
                    alert.resolved = True
                    alert.resolved_at = time.time()
            return

        # Determinar severidad
        severity = (
            Severity.CRITICAL
            if result.status == HealthStatus.UNHEALTHY
            else Severity.WARNING
        )

        # Verificar si ya existe alerta similar no resuelta
        existing = any(
            alert.component == result.component
            and not alert.resolved
            for alert in self._alerts
        )

        if not existing:
            import uuid
            alert = Alert(
                id=str(uuid.uuid4())[:8],
                severity=severity,
                component=result.component,
                message=result.message,
                timestamp=time.time(),
            )
            self._alerts.append(alert)
            log_event("health_alert", f"{severity.value}:{result.component}:{result.message}")

    def get_system_health(self) -> Tuple[HealthStatus, Dict[str, Any]]:
        """
        Obtiene estado de salud general del sistema.

        Returns:
            (estado_global, detalles_por_componente)
        """
        with self._lock:
            results = dict(self._check_results)

        if not results:
            return HealthStatus.UNKNOWN, {}

        # Determinar estado global
        critical_unhealthy = sum(
            1 for r in results.values()
            if r.status == HealthStatus.UNHEALTHY and self._checks[r.component].critical
        )
        total_degraded = sum(
            1 for r in results.values() if r.status == HealthStatus.DEGRADED
        )

        if critical_unhealthy > 0:
            overall = HealthStatus.UNHEALTHY
        elif total_degraded > 0:
            overall = HealthStatus.DEGRADED
        else:
            overall = HealthStatus.HEALTHY

        details = {
            "checks": {name: {
                "status": r.status.value,
                "response_ms": round(r.response_time_ms, 2),
                "message": r.message,
                "last_check": r.last_check,
            } for name, r in results.items()},
            "summary": {
                "total": len(results),
                "healthy": sum(1 for r in results.values() if r.status == HealthStatus.HEALTHY),
                "degraded": total_degraded,
                "unhealthy": sum(1 for r in results.values() if r.status == HealthStatus.UNHEALTHY),
            },
        }

        return overall, details

    def record_metrics(self, metrics: SystemMetrics):
        """Registra métricas del sistema."""
        with self._lock:
            self._metrics_history.append(metrics)

            # Mantener solo métricas dentro de la ventana
            cutoff = time.time() - self.metrics_window
            self._metrics_history = [
                m for m in self._metrics_history if m.timestamp > cutoff
            ]

        # Evaluar umbrales
        self._evaluate_metric_thresholds(metrics)

    def _evaluate_metric_thresholds(self, metrics: SystemMetrics):
        """Evalúa métricas contra umbrales configurados."""
        metric_values = {
            "response_time": metrics.avg_response_time_ms,
            "error_rate": metrics.error_rate,
            "active_users": metrics.active_users,
            "memory_usage": metrics.memory_usage_mb,
            "cpu_usage": metrics.cpu_usage_percent,
        }

        for metric_name, (threshold, severity) in self._alert_thresholds.items():
            value = metric_values.get(metric_name, 0)
            if value > threshold:
                # Verificar si ya existe alerta
                existing = any(
                    alert.component == f"metric:{metric_name}" and not alert.resolved
                    for alert in self._alerts
                )
                if not existing:
                    import uuid
                    alert = Alert(
                        id=str(uuid.uuid4())[:8],
                        severity=severity,
                        component=f"metric:{metric_name}",
                        message=f"{metric_name} = {value:.2f} (umbral: {threshold})",
                        timestamp=time.time(),
                    )
                    self._alerts.append(alert)

    def get_metrics_summary(self) -> Dict[str, Any]:
        """Obtiene resumen de métricas."""
        with self._lock:
            if not self._metrics_history:
                return {}

            metrics = self._metrics_history

            return {
                "current": {
                    "active_users": metrics[-1].active_users if metrics else 0,
                    "requests_per_min": metrics[-1].requests_per_minute if metrics else 0,
                    "avg_response_ms": metrics[-1].avg_response_time_ms if metrics else 0,
                    "error_rate": metrics[-1].error_rate if metrics else 0,
                },
                "avg_5min": {
                    "requests_per_min": sum(m.requests_per_minute for m in metrics[-5:]) / min(5, len(metrics)) if metrics else 0,
                    "response_ms": sum(m.avg_response_time_ms for m in metrics) / len(metrics) if metrics else 0,
                    "error_rate": sum(m.error_rate for m in metrics) / len(metrics) if metrics else 0,
                },
                "peak": {
                    "active_users": max(m.active_users for m in metrics) if metrics else 0,
                    "requests_per_min": max(m.requests_per_minute for m in metrics) if metrics else 0,
                },
            }

    def get_active_alerts(self, resolved: bool = False) -> List[Alert]:
        """Obtiene alertas activas o resueltas."""
        return [a for a in self._alerts if a.resolved == resolved]

    def resolve_alert(self, alert_id: str) -> bool:
        """Resuelve una alerta manualmente."""
        for alert in self._alerts:
            if alert.id == alert_id and not alert.resolved:
                alert.resolved = True
                alert.resolved_at = time.time()
                return True
        return False

    def start_monitoring(self):
        """Inicia monitoreo en segundo plano."""
        if self._running:
            return

        self._running = True
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def stop_monitoring(self):
        """Detiene monitoreo."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5.0)

    def _monitor_loop(self):
        """Loop de monitoreo periódico."""
        while self._running:
            try:
                self.run_all_checks()
            except Exception as e:
                log_event("health_monitor", f"error:{e}")

            time.sleep(self.check_interval)


# Funciones de utilidad para crear checks comunes

def create_db_health_check(db_check_fn: Callable[[], bool]) -> HealthCheck:
    """Crea health check para base de datos."""
    def check():
        start = time.time()
        try:
            ok = db_check_fn()
            elapsed = (time.time() - start) * 1000
            if ok:
                return HealthStatus.HEALTHY, f"DB OK ({elapsed:.0f}ms)", {"response_ms": elapsed}
            return HealthStatus.UNHEALTHY, "DB no responde", {}
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Error DB: {str(e)}", {}

    return HealthCheck("database", check, interval_seconds=30.0)


def create_cache_health_check(cache_stats_fn: Callable[[], Dict[str, Any]]) -> HealthCheck:
    """Crea health check para sistema de caché."""
    def check():
        try:
            stats = cache_stats_fn()
            hit_rate = stats.get("hit_rate", 0)

            if hit_rate > 0.8:
                return HealthStatus.HEALTHY, f"Caché OK (hit rate: {hit_rate:.1%})", stats
            elif hit_rate > 0.5:
                return HealthStatus.DEGRADED, f"Caché degradado (hit rate: {hit_rate:.1%})", stats
            return HealthStatus.UNHEALTHY, f"Caché ineficiente (hit rate: {hit_rate:.1%})", stats
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Error caché: {str(e)}", {}

    return HealthCheck("cache", check, interval_seconds=60.0, critical=False)


def create_rate_limiter_health_check(metrics_fn: Callable[[], Dict[str, Any]]) -> HealthCheck:
    """Crea health check para rate limiter."""
    def check():
        try:
            metrics = metrics_fn()
            active_penalties = metrics.get("active_penalties", 0)
            violations = metrics.get("total_violations", 0)

            status = HealthStatus.HEALTHY
            message = f"Rate limiter OK ({active_penalties} penalizaciones activas)"

            if violations > 100:
                status = HealthStatus.DEGRADED
                message = f"Alta tasa de violaciones: {violations}"

            return status, message, metrics
        except Exception as e:
            return HealthStatus.UNHEALTHY, f"Error rate limiter: {str(e)}", {}

    return HealthCheck("rate_limiter", check, interval_seconds=60.0, critical=False)


# Instancia global
_monitor_instance: Optional[HealthMonitor] = None
_monitor_lock = threading.Lock()


def get_health_monitor() -> HealthMonitor:
    """Obtiene instancia global del monitor de salud."""
    global _monitor_instance
    if _monitor_instance is None:
        with _monitor_lock:
            if _monitor_instance is None:
                _monitor_instance = HealthMonitor()
    return _monitor_instance


def quick_health_check() -> Tuple[HealthStatus, str]:
    """Health check rápido para uso en UI."""
    monitor = get_health_monitor()
    status, details = monitor.get_system_health()

    if status == HealthStatus.HEALTHY:
        return status, "✅ Sistema operativo"
    elif status == HealthStatus.DEGRADED:
        degraded = [c for c, d in details.get("checks", {}).items() if d.get("status") != "healthy"]
        return status, f"⚠️ Degradado: {', '.join(degraded)}"
    return status, "❌ Problemas detectados"
