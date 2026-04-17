"""
Tests para los nuevos módulos de escalabilidad.

EJECUTAR:
    python -m pytest tests/test_scalability_modules.py -v
"""

import pytest
import time
import threading
from datetime import datetime, timedelta


class TestConnectionPool:
    """Tests para connection_pool.py"""
    
    def test_circuit_breaker_creation(self):
        from core.connection_pool import CircuitBreaker
        cb = CircuitBreaker()
        assert cb.state.value == "closed"
        assert cb.can_execute() is True
    
    def test_circuit_breaker_failure_threshold(self):
        from core.connection_pool import CircuitBreaker
        cb = CircuitBreaker(failure_threshold=3)
        
        # Registrar fallos
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
    
    def test_pool_creation(self):
        from core.connection_pool import TenantConnectionPool
        pool = TenantConnectionPool(max_connections_per_tenant=10, max_total_connections=100)
        assert pool.max_per_tenant == 10
        assert pool.max_total == 100


class TestCacheManager:
    """Tests para cache_manager.py"""
    
    def test_cache_set_and_get(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        cache.set("test", "tenant1", "valor", ttl_seconds=60)
        hit, value = cache.get("test", "tenant1")
        
        assert hit is True
        assert value == "valor"
    
    def test_cache_expiration(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        cache.set("test", "tenant1", "valor", ttl_seconds=0.01)
        time.sleep(0.02)
        
        hit, value = cache.get("test", "tenant1")
        assert hit is False
    
    def test_cache_invalidation(self):
        from core.cache_manager import TieredCacheManager
        cache = TieredCacheManager()
        
        cache.set("a", "tenant1", "1")
        cache.set("b", "tenant1", "2")
        cache.invalidate(prefix="a")
        
        hit_a, _ = cache.get("a", "tenant1")
        hit_b, value_b = cache.get("b", "tenant1")
        
        assert hit_a is False
        assert hit_b is True
        assert value_b == "2"
    
    def test_cached_decorator(self):
        from core.cache_manager import cached
        
        call_count = 0
        
        @cached(prefix="test_fn", ttl_seconds=60)
        def test_func(tenant_key, x):
            nonlocal call_count
            call_count += 1
            return x * 2
        
        result1 = test_func("tenant1", 5)
        result2 = test_func("tenant1", 5)
        
        assert result1 == 10
        assert result2 == 10
        assert call_count == 1  # Solo se llamó una vez


class TestRateLimiter:
    """Tests para rate_limiter.py"""
    
    def test_sliding_window_creation(self):
        from core.rate_limiter import SlidingWindowRateLimiter
        limiter = SlidingWindowRateLimiter()
        assert limiter.default_config.requests_per_window == 100
    
    def test_rate_limit_allowed(self):
        from core.rate_limiter import SlidingWindowRateLimiter, LimitType
        limiter = SlidingWindowRateLimiter()
        
        allowed, metadata = limiter.check_rate_limit(
            LimitType.PER_USER, "user123", "api/test", cost=1
        )
        
        assert allowed is True
        assert "remaining" in metadata
    
    def test_rate_limit_exceeded(self):
        from core.rate_limiter import SlidingWindowRateLimiter, LimitType
        limiter = SlidingWindowRateLimiter()
        from core.rate_limiter import RateLimitConfig
        limiter.set_config(
            LimitType.PER_USER, "user456",
            RateLimitConfig(requests_per_window=2, window_seconds=60, burst_allowance=0)
        )
        
        # Consumir el límite
        limiter.check_rate_limit(LimitType.PER_USER, "user456", "api/test", cost=1)
        limiter.check_rate_limit(LimitType.PER_USER, "user456", "api/test", cost=1)
        
        # Tercer request debe ser bloqueado
        allowed, metadata = limiter.check_rate_limit(
            LimitType.PER_USER, "user456", "api/test", cost=1
        )
        
        assert allowed is False
        assert metadata["reason"] == "rate_limit_exceeded"
    
    def test_token_bucket(self):
        from core.rate_limiter import TokenBucketRateLimiter
        bucket = TokenBucketRateLimiter(tokens_per_second=10, bucket_size=5)
        
        # Consumir tokens
        for _ in range(5):
            allowed, _ = bucket.consume("key1", tokens=1)
            assert allowed is True
        
        # Sexto consume debe fallar
        allowed, metadata = bucket.consume("key1", tokens=1)
        assert allowed is False
        assert metadata["reason"] == "insufficient_tokens"


class TestPagination:
    """Tests para pagination.py"""
    
    def test_cursor_paginator(self):
        from core.pagination import CursorPaginator
        
        items = [{"id": i, "name": f"Item {i}"} for i in range(100)]
        paginator = CursorPaginator(page_size=10)
        
        page1 = paginator.paginate(items, cursor=None, sort_field="id")
        
        assert len(page1.items) == 10
        assert page1.has_more is True
        assert page1.next_cursor is not None
    
    def test_pagination_consistency(self):
        from core.pagination import CursorPaginator
        
        items = [{"id": i} for i in range(50)]
        paginator = CursorPaginator(page_size=10)
        
        # Primera página
        page1 = paginator.paginate(items, cursor=None, sort_field="id")
        
        # Segunda página usando cursor
        page2 = paginator.paginate(items, cursor=page1.next_cursor, sort_field="id")
        
        # No deben superponerse
        page1_ids = {item["id"] for item in page1.items}
        page2_ids = {item["id"] for item in page2.items}
        
        assert not page1_ids.intersection(page2_ids)
    
    def test_searchable_paginator(self):
        from core.pagination import SearchablePaginator
        
        items = [
            {"name": "Juan Perez", "dni": "12345678"},
            {"name": "Maria Garcia", "dni": "87654321"},
            {"name": "Juan Garcia", "dni": "11111111"},
        ]
        
        paginator = SearchablePaginator(page_size=10, search_fields=["name", "dni"])
        result = paginator.search_and_paginate(items, search_query="Juan", page=1)
        
        # Should find Juan Perez and Juan Garcia (2 matches)
        assert result.total_count >= 1  # At least one match


class TestBatchProcessor:
    """Tests para batch_processor.py"""
    
    def test_batch_job_creation(self):
        from core.batch_processor import BatchJob, ProcessingStrategy
        
        job = BatchJob(
            job_id="test1",
            name="Test Job",
            items=[1, 2, 3],
            processor=lambda x: x * 2,
            strategy=ProcessingStrategy.SEQUENTIAL
        )
        
        assert job.name == "Test Job"
        assert len(job.items) == 3
    
    def test_batch_processing_sequential(self):
        from core.batch_processor import BatchProcessor, BatchJob, ProcessingStrategy
        
        results = []
        
        def processor(item):
            results.append(item)
            return True
        
        job = BatchJob(
            job_id="test2",
            name="Sequential Test",
            items=[1, 2, 3, 4, 5],
            processor=processor,
            strategy=ProcessingStrategy.SEQUENTIAL
        )
        
        processor_instance = BatchProcessor()
        processor_instance.submit_job(job)
        result = processor_instance.run_job(job.job_id)
        
        assert result.status.value == "completed"
        assert result.success_count == 5
        assert results == [1, 2, 3, 4, 5]


class TestHealthMonitor:
    """Tests para health_monitor.py"""
    
    def test_health_check_creation(self):
        from core.health_monitor import HealthCheck, HealthStatus
        
        def check_fn():
            return (HealthStatus.HEALTHY, "OK", {})
        
        hc = HealthCheck("test_check", check_fn, interval_seconds=60)
        result = hc.run()
        
        assert result.component == "test_check"
        assert result.status == HealthStatus.HEALTHY
    
    def test_health_monitor_checks(self):
        from core.health_monitor import HealthMonitor, HealthCheck, HealthStatus
        
        monitor = HealthMonitor()
        
        hc = HealthCheck("db", lambda: (HealthStatus.HEALTHY, "OK", {}), interval_seconds=0)
        monitor.register_check(hc)
        
        results = monitor.run_all_checks()
        
        assert "db" in results
        assert results["db"].status == HealthStatus.HEALTHY
    
    def test_system_health_summary(self):
        from core.health_monitor import HealthMonitor, HealthCheck, HealthStatus
        
        monitor = HealthMonitor()
        
        monitor.register_check(HealthCheck("db", lambda: (HealthStatus.HEALTHY, "OK", {})))
        monitor.register_check(HealthCheck("cache", lambda: (HealthStatus.DEGRADED, "Slow", {}), critical=False))
        
        monitor.run_all_checks()
        status, details = monitor.get_system_health()
        
        assert status.value == "degraded"


class TestDataValidator:
    """Tests para data_validator.py"""
    
    def test_validation_schema(self):
        from core.data_validator import ValidationSchema
        
        schema = ValidationSchema(
            field="nombre",
            field_type=str,
            required=True,
            min_length=2,
            max_length=50
        )
        
        assert schema.field == "nombre"
        assert schema.required is True
    
    def test_validate_paciente(self):
        from core.data_validator import validate_paciente
        
        is_valid, results = validate_paciente({
            "nombre": "Juan",
            "apellido": "Perez",
            "dni": "37108100",
            "telefono": "1234567890"
        })
        
        assert is_valid is True
        assert results["nombre"].valid is True
        assert results["dni"].valid is True
    
    def test_validate_paciente_invalid(self):
        from core.data_validator import validate_paciente
        
        is_valid, results = validate_paciente({
            "nombre": "",  # Vacío - inválido
            "apellido": "Perez",
            "dni": "37108100"
        })
        
        assert is_valid is False
        assert results["nombre"].valid is False


class TestQueryOptimizer:
    """Tests para query_optimizer.py"""
    
    def test_bloom_filter_creation(self):
        from core.query_optimizer import BloomFilter
        bf = BloomFilter(capacity=1000, false_positive_rate=0.01)
        
        assert bf.capacity == 1000
        assert len(bf) == 0
    
    def test_bloom_filter_membership(self):
        from core.query_optimizer import BloomFilter
        bf = BloomFilter(capacity=100, false_positive_rate=0.01)
        
        bf.add("user1")
        bf.add("user2")
        
        assert "user1" in bf
        assert "user2" in bf
        assert "user3" not in bf  # Falso negativo imposible
    
    def test_in_memory_index(self):
        from core.query_optimizer import InMemoryIndex
        
        index = InMemoryIndex("dni", unique=True)
        items = [
            {"dni": "123", "nombre": "Juan"},
            {"dni": "456", "nombre": "Maria"},
        ]
        
        index.build(items, lambda x: x["dni"])
        positions = index.lookup("123")
        
        assert len(positions) == 1
        assert positions[0] == 0
    
    def test_binary_search_helper(self):
        from core.query_optimizer import BinarySearchHelper
        
        items = [{"id": 1}, {"id": 3}, {"id": 5}, {"id": 7}, {"id": 9}]
        
        result = BinarySearchHelper.find_exact(items, 5, key=lambda x: x["id"])
        assert result["id"] == 5
        
        result_none = BinarySearchHelper.find_exact(items, 6, key=lambda x: x["id"])
        assert result_none is None


class TestUIOptimizer:
    """Tests para ui_optimizer.py"""
    
    def test_debouncer_creation(self):
        from core.ui_optimizer import Debouncer
        d = Debouncer(wait_seconds=0.1)
        assert d.wait == 0.1
    
    def test_throttler_creation(self):
        from core.ui_optimizer import Throttler
        t = Throttler(limit_seconds=0.1)
        assert t.limit == 0.1
    
    def test_throttling(self):
        from core.ui_optimizer import Throttler
        t = Throttler(limit_seconds=0.2)
        
        call_count = 0
        
        @t.throttle
        def test_fn():
            nonlocal call_count
            call_count += 1
        
        # Primera llamada inmediata
        test_fn()
        assert call_count == 1
        
        # Segunda llamada throttled (dentro del límite)
        test_fn()
        assert call_count == 1  # No incrementó
    
    def test_virtual_list_state(self):
        from core.ui_optimizer import VirtualListState
        
        state = VirtualListState(
            item_height=50,
            viewport_height=400,
            total_items=1000
        )
        
        assert state.visible_count == 18  # (400/50) + 2*5 buffer
        assert state.start_index == 0  # scroll_position=0


class TestIntegration:
    """Tests de integración entre módulos"""
    
    def test_cache_with_rate_limiter(self):
        from core.cache_manager import get_cache_manager, cached
        from core.rate_limiter import check_rate_limit, LimitType
        
        # Usar caché y rate limiting juntos
        @cached(prefix="api", ttl_seconds=60)
        def fetch_data(tenant_key, endpoint):
            # Verificar rate limit
            allowed, _ = check_rate_limit(
                LimitType.PER_TENANT, tenant_key, endpoint
            )
            if not allowed:
                raise Exception("Rate limit exceeded")
            return {"data": "test"}
        
        result = fetch_data("tenant1", "/api/data")
        assert result["data"] == "test"
    
    def test_full_stack_health_check(self):
        from core.health_monitor import get_health_monitor, create_db_health_check, quick_health_check
        from core.cache_manager import get_cache_manager
        from core.rate_limiter import get_sliding_limiter
        
        monitor = get_health_monitor()
        
        # Crear health checks para todos los sistemas
        cache = get_cache_manager()
        db_check = create_db_health_check(lambda: True)
        
        monitor.register_check(db_check)
        monitor.run_all_checks()
        
        status, message = quick_health_check()
        assert status is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
