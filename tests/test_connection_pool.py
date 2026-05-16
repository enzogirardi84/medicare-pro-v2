import pytest
import time

from core.connection_pool import CircuitBreaker, CircuitState, TenantConnectionPool


class TestCircuitBreaker:

    def test_circuit_breaker_initial_state(self):
        cb = CircuitBreaker()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute() is True

    def test_circuit_breaker_failure_threshold(self):
        cb = CircuitBreaker(failure_threshold=3)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.can_execute() is False

    def test_circuit_breaker_recovery(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.15)
        assert cb.can_execute() is True
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_circuit_breaker_half_open_failure(self):
        cb = CircuitBreaker(failure_threshold=2, recovery_timeout=0.1)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.15)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN


class TestTenantConnectionPool:

    def test_pool_creation(self):
        pool = TenantConnectionPool(max_connections_per_tenant=5, max_total_connections=100)
        assert pool.max_per_tenant == 5
        metrics = pool.get_metrics("test_tenant")
        assert metrics["active"] == 0

    def test_pool_acquire_release(self):
        pool = TenantConnectionPool(max_connections_per_tenant=2, max_total_connections=10)
        with pool.acquire("tenant1") as conn1:
            with pool.acquire("tenant1") as conn2:
                metrics = pool.get_metrics("tenant1")
                assert metrics["active"] == 2
        assert len(pool._in_use.get("tenant1", set())) == 0

    def test_pool_timeout(self):
        pool = TenantConnectionPool(max_connections_per_tenant=1, max_total_connections=10, connection_timeout=0.1)
        with pool.acquire("tenant1"):
            with pytest.raises(TimeoutError):
                with pool.acquire("tenant1", timeout=0.05):
                    pass
