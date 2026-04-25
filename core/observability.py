"""
Observability: Logging estructurado y métricas para Medicare Pro.

- Logging JSON estructurado
- Correlation IDs para trazabilidad
- Métricas con tags
- Exportación a Prometheus/Grafana compatible
"""

from __future__ import annotations

import json
import logging
import sys
import time
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from functools import wraps
from typing import Any, Callable, Dict, List, Optional

import streamlit as st

# Context variable para correlation ID
_correlation_id: ContextVar[str] = ContextVar('correlation_id', default='')


class StructuredLogFormatter(logging.Formatter):
    """Formatter que emite logs en formato JSON."""
    
    def format(self, record: logging.LogRecord) -> str:
        log_data = {
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
            'module': record.module,
            'function': record.funcName,
            'line': record.lineno,
            'correlation_id': _correlation_id.get() or 'none',
        }
        
        # Agregar extra fields si existen
        if hasattr(record, 'extra_data'):
            log_data['extra'] = record.extra_data
        
        # Agregar exception info si existe
        if record.exc_info:
            if isinstance(record.exc_info, tuple):
                log_data['exception'] = self.formatException(record.exc_info)
            elif record.exc_info is True:
                import sys
                exc_info = sys.exc_info()
                if exc_info[0] is not None:
                    log_data['exception'] = self.formatException(exc_info)
                else:
                    log_data['exception'] = 'exc_info_present'
            else:
                log_data['exception'] = 'exc_info_present'
        
        return json.dumps(log_data, ensure_ascii=False, default=str)


class LoggerAdapter(logging.LoggerAdapter):
    """Adapter que agrega correlation ID automáticamente."""
    
    def process(self, msg, kwargs):
        extra = kwargs.get('extra', {})
        extra['correlation_id'] = _correlation_id.get() or 'none'
        kwargs['extra'] = extra
        return msg, kwargs


def get_logger(name: str) -> logging.Logger:
    """Obtiene un logger con formateo JSON."""
    logger = logging.getLogger(name)
    
    # Configurar si no tiene handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredLogFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    
    return logger


def get_correlation_id() -> str:
    """Obtiene o genera correlation ID actual."""
    corr_id = _correlation_id.get()
    if not corr_id:
        corr_id = str(uuid.uuid4())[:16]
        _correlation_id.set(corr_id)
    return corr_id


def set_correlation_id(corr_id: str):
    """Establece correlation ID para el contexto actual."""
    _correlation_id.set(corr_id)


def clear_correlation_id():
    """Limpia correlation ID del contexto."""
    _correlation_id.set('')


class MetricsCollector:
    """
    Colector de métricas compatible con Prometheus.
    
    Soporta:
    - Counters: métricas que solo incrementan
    - Gauges: métricas que pueden subir o bajar
    - Histograms: distribución de valores
    """
    
    def __init__(self):
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._labels: Dict[str, Dict[str, str]] = {}
    
    def increment(self, metric_name: str, value: int = 1, tags: Optional[Dict[str, str]] = None):
        """Incrementa un contador."""
        key = self._make_key(metric_name, tags)
        self._counters[key] = self._counters.get(key, 0) + value
        self._labels[key] = tags or {}
        
        # También loggear eventos importantes
        if metric_name in ['login_failed', 'security_alert', 'error_rate']:
            logger = get_logger('metrics')
            logger.warning(f"Metric {metric_name} incremented", extra={
                'extra_data': {'metric': metric_name, 'value': value, 'tags': tags}
            })
    
    def gauge(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Establece un valor de gauge."""
        key = self._make_key(metric_name, tags)
        self._gauges[key] = value
        self._labels[key] = tags or {}
    
    def histogram(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None):
        """Agrega un valor a un histograma."""
        key = self._make_key(metric_name, tags)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._labels[key] = tags or {}
    
    def _make_key(self, metric_name: str, tags: Optional[Dict[str, str]]) -> str:
        """Crea una key única incluyendo tags."""
        if not tags:
            return metric_name
        tag_str = ','.join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{metric_name}{{{tag_str}}}"
    
    def get_prometheus_format(self) -> str:
        """Exporta métricas en formato Prometheus."""
        lines = []
        
        # Counters
        for key, value in self._counters.items():
            metric_name = key.split('{')[0]
            lines.append(f"# TYPE {metric_name} counter")
            lines.append(f"{key} {value}")
        
        # Gauges
        for key, value in self._gauges.items():
            metric_name = key.split('{')[0]
            lines.append(f"# TYPE {metric_name} gauge")
            lines.append(f"{key} {value}")
        
        # Histograms (simplificado: solo count y sum)
        for key, values in self._histograms.items():
            if values:
                metric_name = key.split('{')[0]
                lines.append(f"# TYPE {metric_name} histogram")
                lines.append(f"{key}_count {len(values)}")
                lines.append(f"{key}_sum {sum(values)}")
        
        return '\n'.join(lines)
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de métricas."""
        return {
            'counters': dict(self._counters),
            'gauges': dict(self._gauges),
            'histograms': {
                k: {'count': len(v), 'avg': sum(v)/len(v) if v else 0, 'min': min(v) if v else 0, 'max': max(v) if v else 0}
                for k, v in self._histograms.items()
            }
        }


# Singleton global
_metrics_instance: Optional[MetricsCollector] = None


def get_metrics() -> MetricsCollector:
    """Obtiene instancia global del colector de métricas."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = MetricsCollector()
    return _metrics_instance


def track_metric(metric_name: str, value: float = 1, tags: Optional[Dict[str, str]] = None):
    """Tracking rápido de una métrica."""
    metrics = get_metrics()
    
    # Inferir tipo de métrica por nombre
    if any(s in metric_name for s in ['_total', '_count', '_errors', '_requests']):
        metrics.increment(metric_name, int(value), tags)
    elif any(s in metric_name for s in ['_duration', '_time', '_latency']):
        metrics.histogram(metric_name, value, tags)
    else:
        metrics.gauge(metric_name, value, tags)


def timed(metric_name: str, tags: Optional[Dict[str, str]] = None):
    """Decorador para medir tiempo de ejecución."""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                status = 'success'
                return result
            except Exception as e:
                status = 'error'
                raise
            finally:
                duration = time.time() - start
                merged_tags = {**(tags or {}), 'status': status}
                track_metric(f"{metric_name}_duration_seconds", duration, merged_tags)
        return wrapper
    return decorator


class TracingContext:
    """Context manager para trazabilidad de operaciones."""
    
    def __init__(self, operation: str, **context):
        self.operation = operation
        self.context = context
        self.logger = get_logger('tracing')
        self.start_time: Optional[float] = None
        self.corr_id: Optional[str] = None
    
    def __enter__(self):
        self.corr_id = get_correlation_id()
        self.start_time = time.time()
        
        self.logger.info(f"Starting {self.operation}", extra={
            'extra_data': {
                'operation': self.operation,
                'context': self.context,
                'correlation_id': self.corr_id
            }
        })
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time
        
        if exc_type:
            self.logger.error(f"Failed {self.operation}", extra={
                'extra_data': {
                    'operation': self.operation,
                    'duration_ms': duration * 1000,
                    'error': str(exc_val),
                    'correlation_id': self.corr_id
                }
            })
        else:
            self.logger.info(f"Completed {self.operation}", extra={
                'extra_data': {
                    'operation': self.operation,
                    'duration_ms': duration * 1000,
                    'correlation_id': self.corr_id
                }
            })
        
        # Limpiar correlation ID
        clear_correlation_id()


def log_user_action(action: str, user_id: str, details: Dict[str, Any]):
    """Log específico para acciones de usuarios (auditoría)."""
    logger = get_logger('audit')
    logger.info(f"User action: {action}", extra={
        'extra_data': {
            'action': action,
            'user_id': user_id,
            'details': details,
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', ''),
            'correlation_id': get_correlation_id()
        }
    })
    
    # También trackear como métrica
    track_metric('user_actions_total', 1, tags={'action': action, 'user_id': user_id[:8]})


def log_security_event(event_type: str, severity: str, details: Dict[str, Any]):
    """Log específico para eventos de seguridad."""
    logger = get_logger('security')
    
    log_func = getattr(logger, severity.lower(), logger.warning)
    log_func(f"Security event: {event_type}", extra={
        'extra_data': {
            'event_type': event_type,
            'severity': severity,
            'details': details,
            'timestamp': datetime.now(timezone.utc).isoformat().replace('+00:00', ''),
            'correlation_id': get_correlation_id()
        }
    })
    
    # Métrica de seguridad
    track_metric('security_events_total', 1, tags={'event_type': event_type, 'severity': severity})


# Funciones de utilidad para Streamlit

def init_observability_for_session():
    """Inicializa observabilidad para sesión de Streamlit."""
    # Generar correlation ID para esta sesión
    session_id = st.session_state.get('session_id')
    if not session_id:
        session_id = str(uuid.uuid4())[:16]
        st.session_state['session_id'] = session_id
    
    set_correlation_id(session_id)


def render_metrics_dashboard():
    """Renderiza dashboard de métricas en Streamlit."""
    import streamlit as st
    
    st.subheader("📊 Métricas del Sistema")
    
    metrics = get_metrics()
    stats = metrics.get_stats()
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Contadores", len(stats['counters']))
    
    with col2:
        st.metric("Gauges", len(stats['gauges']))
    
    with col3:
        st.metric("Histograms", len(stats['histograms']))
    
    # Mostrar métricas detalladas
    if stats['counters']:
        with st.expander("Contadores"):
            for key, value in list(stats['counters'].items())[:20]:
                st.text(f"{key}: {value}")
    
    if stats['histograms']:
        with st.expander("Latencias (avg)"):
            for key, hist in list(stats['histograms'].items())[:10]:
                if hist['count'] > 0:
                    st.text(f"{key}: {hist['avg']:.3f}s (n={hist['count']})")


# Ejemplo de uso
if __name__ == "__main__":
    # Demo de logging estructurado
    logger = get_logger("demo")
    logger.info("Aplicación iniciada")
    
    # Demo de trazabilidad
    with TracingContext("procesar_paciente", paciente_id="123"):
        logger.info("Procesando paciente...")
        time.sleep(0.1)
    
    # Demo de métricas
    track_metric("pacientes_creados", 1, tags={"empresa": "clinica_a"})
    track_metric("api_latency", 0.234, tags={"endpoint": "/api/pacientes"})
    
    # Mostrar métricas
    print("\nMétricas:")
    print(get_metrics().get_prometheus_format())
