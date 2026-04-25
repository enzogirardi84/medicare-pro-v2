"""
Tests para el profiler de performance.

EJECUTAR:
    python -m pytest tests/test_performance_profiler.py -v
"""

import pytest
import time
from unittest.mock import Mock, patch


class TestPerformanceProfiler:
    """Tests para PerformanceProfiler"""
    
    def test_profiler_creation(self):
        """Test creación de profiler"""
        from core.performance_profiler import PerformanceProfiler
        
        profiler = PerformanceProfiler(enabled=True)
        assert profiler.enabled is True
        assert profiler.sample_rate == 1.0
    
    def test_profile_decorator(self):
        """Test decorador de profiling"""
        from core.performance_profiler import PerformanceProfiler
        
        profiler = PerformanceProfiler(enabled=True)
        
        @profiler.profile
        def slow_function():
            time.sleep(0.01)
            return "result"
        
        result = slow_function()
        
        assert result == "result"
        # Verificar que se registró
        assert len(profiler._function_stats) == 1
    
    def test_profile_block(self):
        """Test context manager de profiling"""
        from core.performance_profiler import PerformanceProfiler
        
        profiler = PerformanceProfiler(enabled=True)
        
        with profiler.profile_block("test_block"):
            time.sleep(0.01)
        
        # No debe lanzar error
        assert True
    
    def test_disabled_profiler(self):
        """Test que disabled profiler no afecta ejecución"""
        from core.performance_profiler import PerformanceProfiler
        
        profiler = PerformanceProfiler(enabled=False)
        
        @profiler.profile
        def normal_function():
            return "ok"
        
        result = normal_function()
        assert result == "ok"
        assert len(profiler._function_stats) == 0
    
    def test_get_slow_functions(self):
        """Test detección de funciones lentas"""
        from core.performance_profiler import PerformanceProfiler
        
        profiler = PerformanceProfiler(enabled=True)
        profiler.SLOW_FUNCTION_THRESHOLD = 0.001  # 1ms para testing
        
        @profiler.profile
        def slow_func():
            time.sleep(0.01)  # 10ms > 1ms threshold
        
        slow_func()
        
        slow_functions = profiler.get_slow_functions(threshold=0.001)
        assert len(slow_functions) == 1
        assert slow_functions[0].name == "slow_func"
    
    def test_query_logging(self):
        """Test logueo de queries"""
        from core.performance_profiler import PerformanceProfiler
        
        profiler = PerformanceProfiler(enabled=True)
        
        profiler.log_query("SELECT * FROM pacientes", 0.05)
        profiler.log_query("SELECT * FROM evoluciones", 0.001)
        
        slow_queries = profiler.get_slow_queries()
        
        assert len(slow_queries) == 2
        assert slow_queries[0]["duration"] == 0.05  # Más lenta primero
    
    def test_n_plus_1_detection(self):
        """Test detección de N+1 queries"""
        from core.performance_profiler import PerformanceProfiler
        
        profiler = PerformanceProfiler(enabled=True)
        
        # Simular N+1: muchas queries similares
        for i in range(5):
            profiler.log_query(f"SELECT * FROM pacientes WHERE id = {i}", 0.001)
        
        # La siguiente query similar debería activar detección
        is_n_plus_1 = profiler._detect_n_plus_1("SELECT * FROM pacientes WHERE id = 5")
        
        assert is_n_plus_1 is True
    
    def test_export_stats_json(self):
        """Test exportación a JSON"""
        from core.performance_profiler import PerformanceProfiler
        import json
        
        profiler = PerformanceProfiler(enabled=True)
        
        @profiler.profile
        def test_func():
            return "test"
        
        test_func()
        
        json_output = profiler.export_stats("json")
        data = json.loads(json_output)
        
        assert "functions" in data
        assert "slow_functions" in data
        assert "slow_queries" in data
    
    def test_memory_usage_tracking(self):
        """Test tracking de uso de memoria"""
        from core.performance_profiler import PerformanceProfiler
        
        profiler = PerformanceProfiler(enabled=True)
        
        @profiler.profile
        def memory_intensive():
            # Crear datos en memoria
            data = [i for i in range(10000)]
            return len(data)
        
        memory_intensive()
        
        # Verificar que se registró algo
        assert len(profiler._function_stats) == 1
    
    def test_take_snapshot(self):
        """Test snapshot de performance"""
        from core.performance_profiler import PerformanceProfiler
        
        profiler = PerformanceProfiler(enabled=True)
        
        @profiler.profile
        def test_func():
            return "test"
        
        test_func()
        
        snapshot = profiler.take_snapshot()
        
        assert snapshot.timestamp > 0
        try:
            import psutil
            assert snapshot.memory_current > 0
        except ImportError:
            assert snapshot.memory_current >= 0  # psutil no disponible
        assert len(snapshot.function_stats) == 1


class TestProfiledDecorator:
    """Tests para decorador global @profiled"""
    
    def test_profiled_decorator(self):
        """Test decorador global"""
        from core.performance_profiler import profiled
        
        @profiled
        def my_function(x):
            time.sleep(0.01)
            return x * 2
        
        result = my_function(5)
        
        assert result == 10


class TestProfileBlock:
    """Tests para context manager profile_block"""
    
    def test_profile_block_context(self):
        """Test context manager global"""
        from core.performance_profiler import profile_block
        
        with profile_block("test_operation"):
            time.sleep(0.01)
        
        # No debe lanzar error
        assert True


class TestGetProfiler:
    """Tests para get_profiler singleton"""
    
    def test_get_profiler_singleton(self):
        """Test que get_profiler retorna singleton"""
        from core.performance_profiler import get_profiler
        
        profiler1 = get_profiler()
        profiler2 = get_profiler()
        
        assert profiler1 is profiler2
    
    def test_profiler_is_enabled_by_default(self):
        """Test que profiler está habilitado por defecto"""
        from core.performance_profiler import get_profiler
        
        profiler = get_profiler()
        assert profiler.enabled is True


class TestPerformanceAlerts:
    """Tests para alertas de performance"""
    
    def test_slow_function_alert(self):
        """Test alerta por función lenta"""
        from core.performance_profiler import PerformanceProfiler
        
        profiler = PerformanceProfiler(enabled=True)
        profiler.SLOW_FUNCTION_THRESHOLD = 0.001
        
        with patch.object(profiler, '_check_thresholds') as mock_check:
            @profiler.profile
            def slow_func():
                time.sleep(0.01)
            
            slow_func()
            
            # Verificar que se llamó check_thresholds
            mock_check.assert_called()
    
    def test_high_memory_alert(self):
        """Test alerta por alto uso de memoria"""
        from core.performance_profiler import PerformanceProfiler
        
        profiler = PerformanceProfiler(enabled=True)
        profiler.MEMORY_ALERT_THRESHOLD = 1  # 1 byte para testing
        
        # Simular alto uso de memoria
        with patch.object(profiler, '_get_memory_usage', return_value=100):
            profiler._check_thresholds("test_func", 0.001, 99)
            
            # No debe lanzar error
            assert True
