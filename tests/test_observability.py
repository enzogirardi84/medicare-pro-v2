"""
Tests para el módulo de observabilidad

EJECUTAR:
    python -m pytest tests/test_observability.py -v
"""

import pytest
import json
import time
from unittest.mock import Mock, patch


class TestStructuredLogFormatter:
    """Tests para StructuredLogFormatter"""
    
    def test_json_output(self):
        """Test que el output es JSON válido"""
        from core.observability import StructuredLogFormatter, get_correlation_id
        import logging
        
        formatter = StructuredLogFormatter()
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        output = formatter.format(record)
        
        # Verificar que es JSON válido
        parsed = json.loads(output)
        assert parsed["level"] == "INFO"
        assert parsed["message"] == "Test message"
        assert "timestamp" in parsed
        assert "correlation_id" in parsed
    
    def test_exception_formatting(self):
        """Test formato de excepciones"""
        from core.observability import StructuredLogFormatter
        import logging
        
        formatter = StructuredLogFormatter()
        
        try:
            raise ValueError("Test error")
        except:
            record = logging.LogRecord(
                name="test_logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=True
            )
        
        output = formatter.format(record)
        parsed = json.loads(output)
        
        assert "exception" in parsed
        assert "Test error" in parsed["exception"]


class TestCorrelationId:
    """Tests para correlation ID"""
    
    def test_get_correlation_id_generates_if_none(self):
        """Test que genera ID si no existe"""
        from core.observability import get_correlation_id, clear_correlation_id
        
        clear_correlation_id()
        corr_id = get_correlation_id()
        
        assert corr_id is not None
        assert len(corr_id) == 16
    
    def test_get_correlation_id_returns_existing(self):
        """Test que retorna ID existente"""
        from core.observability import get_correlation_id, set_correlation_id, clear_correlation_id
        
        clear_correlation_id()
        set_correlation_id("test-id-123")
        corr_id = get_correlation_id()
        
        assert corr_id == "test-id-123"
    
    def test_clear_correlation_id(self):
        """Test que limpia el ID"""
        from core.observability import clear_correlation_id, get_correlation_id
        
        set_correlation_id("test-id")
        clear_correlation_id()
        
        # Al limpiar, el próximo get genera uno nuevo
        corr_id = get_correlation_id()
        assert corr_id != "test-id"


class TestMetricsCollector:
    """Tests para MetricsCollector"""
    
    def test_counter_increment(self):
        """Test incremento de contador"""
        from core.observability import MetricsCollector
        
        metrics = MetricsCollector()
        metrics.increment("requests_total", 1, tags={"endpoint": "/api"})
        
        stats = metrics.get_stats()
        assert stats["counters"]["requests_total{endpoint=/api}"] == 1
    
    def test_gauge_set(self):
        """Test establecer gauge"""
        from core.observability import MetricsCollector
        
        metrics = MetricsCollector()
        metrics.gauge("active_users", 42.0, tags={"region": "us-east"})
        
        stats = metrics.get_stats()
        assert stats["gauges"]["active_users{region=us-east}"] == 42.0
    
    def test_histogram_record(self):
        """Test registro en histograma"""
        from core.observability import MetricsCollector
        
        metrics = MetricsCollector()
        metrics.histogram("request_duration", 0.234)
        metrics.histogram("request_duration", 0.345)
        
        stats = metrics.get_stats()
        assert stats["histograms"]["request_duration"]["count"] == 2
        assert stats["histograms"]["request_duration"]["avg"] == pytest.approx(0.2895, 0.01)
    
    def test_prometheus_format(self):
        """Test formato Prometheus"""
        from core.observability import MetricsCollector
        
        metrics = MetricsCollector()
        metrics.increment("requests_total", 5)
        metrics.gauge("active_users", 10.0)
        metrics.histogram("duration", 0.5)
        
        output = metrics.get_prometheus_format()
        
        assert "requests_total" in output
        assert "active_users" in output
        assert "duration_count" in output
        assert "duration_sum" in output


class TestTrackMetric:
    """Tests para track_metric helper"""
    
    def test_track_metric_counter(self):
        """Test tracking de contador"""
        from core.observability import track_metric, get_metrics
        
        track_metric("login_attempts_total", 1, tags={"status": "success"})
        
        stats = get_metrics().get_stats()
        assert stats["counters"]["login_attempts_total{status=success}"] == 1
    
    def test_track_metric_histogram(self):
        """Test tracking de histograma por nombre"""
        from core.observability import track_metric, get_metrics
        
        track_metric("api_latency_seconds", 0.5)
        
        stats = get_metrics().get_stats()
        assert "api_latency_seconds" in stats["histograms"]


class TestTimedDecorator:
    """Tests para decorador timed"""
    
    def test_timed_success(self):
        """Test medición de función exitosa"""
        from core.observability import timed, get_metrics
        
        @timed("test_operation")
        def test_func():
            time.sleep(0.01)
            return "success"
        
        result = test_func()
        
        assert result == "success"
        stats = get_metrics().get_stats()
        assert "test_operation_duration_seconds" in stats["histograms"]
    
    def test_timed_error(self):
        """Test medición de función con error"""
        from core.observability import timed, get_metrics
        
        @timed("test_operation_error")
        def test_func():
            time.sleep(0.01)
            raise ValueError("Test error")
        
        with pytest.raises(ValueError):
            test_func()
        
        # Aún debe registrar la métrica
        stats = get_metrics().get_stats()
        assert "test_operation_error_duration_seconds" in stats["histograms"]


class TestTracingContext:
    """Tests para TracingContext"""
    
    def test_tracing_context_success(self):
        """Test contexto de trazabilidad exitoso"""
        from core.observability import TracingContext, get_correlation_id
        
        with TracingContext("test_operation", user_id="123"):
            corr_id = get_correlation_id()
            assert corr_id is not None
            time.sleep(0.01)
    
    def test_tracing_context_exception(self):
        """Test contexto con excepción"""
        from core.observability import TracingContext
        
        with pytest.raises(ValueError):
            with TracingContext("failing_operation"):
                raise ValueError("Test error")


class TestLogUserAction:
    """Tests para log_user_action"""
    
    def test_log_user_action(self):
        """Test logging de acción de usuario"""
        from core.observability import log_user_action, get_metrics
        
        log_user_action("login", "user_123", {"ip": "127.0.0.1"})
        
        # Verificar que se trackeó métrica
        stats = get_metrics().get_stats()
        assert any("user_actions" in key for key in stats["counters"].keys())


class TestLogSecurityEvent:
    """Tests para log_security_event"""
    
    def test_log_security_event(self):
        """Test logging de evento de seguridad"""
        from core.observability import log_security_event, get_metrics
        
        log_security_event("failed_login", "warning", {"ip": "192.168.1.1"})
        
        # Verificar que se trackeó métrica
        stats = get_metrics().get_stats()
        assert any("security_events" in key for key in stats["counters"].keys())


class TestGetLogger:
    """Tests para get_logger"""
    
    def test_get_logger_returns_logger(self):
        """Test que retorna un logger"""
        from core.observability import get_logger
        
        logger = get_logger("test_module")
        assert logger is not None
        assert logger.name == "test_module"
    
    def test_get_logger_has_handler(self):
        """Test que el logger tiene handler"""
        from core.observability import get_logger
        
        logger = get_logger("test_handler")
        assert len(logger.handlers) > 0
