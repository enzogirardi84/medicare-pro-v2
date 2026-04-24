"""
Tests específicos para connection_pool.py

EJECUTAR:
    python -m pytest tests/test_connection_pool.py -v
"""

import pytest
import time
import threading
from datetime import datetime, timedelta


class TestCircuitBreaker:
    """Tests para CircuitBreaker"""
    
    def test_circuit_breaker_initial_state(self):
        from core.connection_pool import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.state.value == "closed"
        assert cb.can_execute() is True
    
    def test_circuit_breaker_failure_threshold(self):
        from core.connection_pool import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3)
        
        # Registrar fallos hasta umbral
        for _ in range(3):
            cb.record_failure()
        
        assert cb.state.value == "open"
        assert cb.can_execute() is False
    
    def test_circuit_breaker_recovery(self):
        from core.connection_pool import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Abrir circuito
        cb.record_failure()
        cb.record_failure()
        assert cb.state.value == "open"
        
        # Esperar recuperación
        time.sleep(0.15)
        assert cb.can_execute() is True  # Half-open
        
        # Éxito cierra el circuito
        cb.record_success()
        assert cb.state.value == "closed"
    
    def test_circuit_breaker_half_open_failure(self):
        from core.connection_pool import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        
        # Abrir y recuperar
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        
        # Fallo en half-open vuelve a abrir
        cb.record_failure()
        assert cb.state.value == "open"


class TestConnectionPool:
    """Tests para ConnectionPool"""
    
    def test_pool_creation(self):
        from core.connection_pool import ConnectionPool
        pool = ConnectionPool(max_connections=5)
        assert pool.max_connections == 5
        assert pool.current_connections == 0
    
    def test_pool_acquire_release(self):
        from core.connection_pool import ConnectionPool
        pool = ConnectionPool(max_connections=2)
        
        # Adquirir conexiones
        conn1 = pool.acquire()
        conn2 = pool.acquire()
        
        assert pool.current_connections == 2
        assert pool.waiting_count == 0
        
        # Liberar
        pool.release(conn1)
        assert pool.current_connections == 1
    
    def test_pool_timeout(self):
        from core.connection_pool import ConnectionPool, PoolTimeoutError
        pool = ConnectionPool(max_connections=1, timeout=0.1)
        
        # Ocupar la única conexión
        pool.acquire()
        
        # Intentar adquirir debe fallar por timeout
        with pytest.raises(PoolTimeoutError):
            pool.acquire()


class TestRetryPolicy:
    """Tests para RetryPolicy"""
    
    def test_retry_with_backoff(self):
        from core.connection_pool import RetryPolicy
        policy = RetryPolicy(max_retries=3, base_delay=0.01)
        
        delays = [policy.get_delay(i) for i in range(3)]
        assert delays[1] >= delays[0]  # Backoff creciente
        assert delays[2] >= delays[1]
    
    def test_retry_jitter(self):
        from core.connection_pool import RetryPolicy
        policy = RetryPolicy(max_retries=3, base_delay=0.1, jitter=True)
        
        # Jitter hace que los delays varíen
        delays = set()
        for _ in range(10):
            d = policy.get_delay(1)
            delays.add(d)
        
        # Al menos algunos deben ser diferentes
        assert len(delays) > 1


class TestHealthCheck:
    """Tests para HealthCheck"""
    
    def test_health_check_success(self):
        from core.connection_pool import HealthCheck
        
        def healthy_check():
            return True
        
        hc = HealthCheck(check_fn=healthy_check, interval=0.1)
        assert hc.is_healthy() is True
    
    def test_health_check_failure(self):
        from core.connection_pool import HealthCheck
        
        def unhealthy_check():
            raise Exception("DB down")
        
        hc = HealthCheck(check_fn=unhealthy_check, interval=0.1)
        # Después del primer check fallido
        time.sleep(0.15)
        assert hc.is_healthy() is False


class TestConnectionManager:
    """Tests para ConnectionManager"""
    
    def test_manager_singleton(self):
        from core.connection_pool import ConnectionManager
        
        manager1 = ConnectionManager()
        manager2 = ConnectionManager()
        
        # Misma instancia (singleton)
        assert manager1 is manager2
    
    def test_manager_get_pool(self):
        from core.connection_pool import ConnectionManager
        
        manager = ConnectionManager()
        pool = manager.get_pool("supabase", max_connections=3)
        
        assert pool is not None
        assert pool.max_connections == 3
