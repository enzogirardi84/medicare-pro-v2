"""Tests para core.service_mesh_proxy — Service Mesh interno."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSlidingWindowCircuitBreaker:
    def test_initial_closed(self):
        from core.service_mesh_proxy import SlidingWindowCircuitBreaker, CircuitState
        cb = SlidingWindowCircuitBreaker(service_name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_opens_after_threshold(self):
        from core.service_mesh_proxy import SlidingWindowCircuitBreaker, CircuitState
        cb = SlidingWindowCircuitBreaker(service_name="test", window_seconds=60,
                                          failure_threshold=3, recovery_timeout=9999)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_half_open_after_timeout(self):
        from core.service_mesh_proxy import SlidingWindowCircuitBreaker, CircuitState
        cb = SlidingWindowCircuitBreaker(service_name="test", failure_threshold=2,
                                          recovery_timeout=0.01, window_seconds=60)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_success_in_half_open(self):
        from core.service_mesh_proxy import SlidingWindowCircuitBreaker, CircuitState
        cb = SlidingWindowCircuitBreaker(service_name="test", failure_threshold=2,
                                          half_open_max_requests=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        time.sleep(0.02)
        cb.allow_request()
        cb.record_success()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_error_rate(self):
        from core.service_mesh_proxy import SlidingWindowCircuitBreaker
        cb = SlidingWindowCircuitBreaker(service_name="test", window_seconds=60)
        cb._failures.extend([time.time() - 10, time.time() - 5])
        cb._successes.append(time.time())
        assert 0.66 < cb.error_rate < 0.67


class TestInternalRateLimiter:
    def test_acquire_allows_within_limit(self):
        from core.service_mesh_proxy import InternalRateLimiter
        limiter = InternalRateLimiter(service_name="test", max_rps=1000, burst=100)
        for _ in range(50):
            assert asyncio.run(limiter.acquire()) is True

    def test_acquire_blocks_when_exhausted(self):
        from core.service_mesh_proxy import InternalRateLimiter
        limiter = InternalRateLimiter(service_name="test", max_rps=0.001, burst=2)
        assert asyncio.run(limiter.acquire()) is True
        assert asyncio.run(limiter.acquire()) is True
        assert asyncio.run(limiter.acquire()) is False


class TestServiceEndpoint:
    def test_endpoint_defaults(self):
        from core.service_mesh_proxy import ServiceEndpoint
        ep = ServiceEndpoint(name="analytics", base_url="http://analytics:8000")
        assert ep.name == "analytics"
        assert ep.max_retries == 3
        assert ep.timeout == 10.0


class TestServiceMeshProxy:
    def test_register_service(self):
        from core.service_mesh_proxy import ServiceMeshProxy, ServiceEndpoint
        proxy = ServiceMeshProxy()
        proxy.register_service(ServiceEndpoint(name="evoluciones", base_url="http://evo:8000"))
        assert "evoluciones" in proxy._endpoints
        assert "evoluciones" in proxy._circuit_breakers
        assert "evoluciones" in proxy._rate_limiters

    def test_jitter_adds_randomness(self):
        from core.service_mesh_proxy import ServiceMeshProxy
        delays = [ServiceMeshProxy._jitter(1.0) for _ in range(100)]
        assert all(1.0 <= d <= 1.3 for d in delays)

    def test_request_unknown_service(self):
        from core.service_mesh_proxy import ServiceMeshProxy
        proxy = ServiceMeshProxy()
        with pytest.raises(ValueError, match="Servicio no registrado"):
            asyncio.run(proxy.request("unknown", "GET", "/health"))

    def test_request_rate_limited(self):
        from core.service_mesh_proxy import ServiceMeshProxy, ServiceEndpoint, ServiceOverloadedError
        proxy = ServiceMeshProxy()
        proxy.register_service(
            ServiceEndpoint(name="slow", base_url="http://slow:8000"),
            rate_cfg={"max_rps": 0.001, "burst": 0},
        )
        with pytest.raises(ServiceOverloadedError):
            asyncio.run(proxy.request("slow", "GET", "/health"))

    def test_request_circuit_open(self):
        from core.service_mesh_proxy import (ServiceMeshProxy, ServiceEndpoint,
                                              ServiceUnavailableError)
        proxy = ServiceMeshProxy()
        proxy.register_service(
            ServiceEndpoint(name="failing", base_url="http://fail:8000"),
            circuit_cfg={"failure_threshold": 1, "recovery_timeout": 9999},
        )
        cb = proxy._circuit_breakers["failing"]
        cb.record_failure()
        with pytest.raises(ServiceUnavailableError):
            asyncio.run(proxy.request("failing", "GET", "/health"))

    def test_request_network_error_retries(self):
        from core.service_mesh_proxy import ServiceMeshProxy, ServiceEndpoint
        proxy = ServiceMeshProxy()
        proxy.register_service(
            ServiceEndpoint(name="flaky", base_url="http://flaky:8000", max_retries=2),
        )
        with patch.object(proxy, "_get_client") as mock_client_factory:
            mock_client = MagicMock()
            mock_client.request = AsyncMock(side_effect=ConnectionError("refused"))
            mock_client_factory.return_value = mock_client
            with pytest.raises(Exception, match="refused"):
                asyncio.run(proxy.request("flaky", "GET", "/health"))
            assert mock_client.request.await_count == 2

    def test_request_success(self):
        from core.service_mesh_proxy import ServiceMeshProxy, ServiceEndpoint
        proxy = ServiceMeshProxy()
        proxy.register_service(
            ServiceEndpoint(name="ok", base_url="http://ok:8000"),
        )
        with patch.object(proxy, "_get_client") as mock_client_factory:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client = MagicMock()
            mock_client.request = AsyncMock(return_value=mock_response)
            mock_client_factory.return_value = mock_client
            resp = asyncio.run(proxy.request("ok", "GET", "/health"))
            assert resp.status_code == 200

    def test_get_stats(self):
        from core.service_mesh_proxy import ServiceMeshProxy, ServiceEndpoint
        proxy = ServiceMeshProxy()
        proxy.register_service(ServiceEndpoint(name="srv1", base_url="http://srv1:8000"))
        stats = proxy.get_stats()
        assert stats["total_services"] == 1
        assert "srv1" in stats["services"]

    def test_health_check_all(self):
        from core.service_mesh_proxy import ServiceMeshProxy, ServiceEndpoint
        proxy = ServiceMeshProxy()
        proxy.register_service(ServiceEndpoint(name="test", base_url="http://test:8000"))
        with patch.object(proxy, "request") as mock_request:
            mock_request.return_value = MagicMock(status_code=200)
            results = asyncio.run(proxy.health_check_all())
            assert results["test"] is True
