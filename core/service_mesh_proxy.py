"""Service Mesh proxy interno para resiliencia de comunicacion
entre microservicios. Implementa retry con jitter, circuit breaker
con ventana deslizante y rate limiting interno por servicio.
"""
from __future__ import annotations

import asyncio
import hashlib
import os
import random
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

import httpx

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CIRCUIT BREAKER CON VENTANA DESLIZANTE
# ═══════════════════════════════════════════════════════════════════

class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class SlidingWindowCircuitBreaker:
    """Circuit breaker con ventana de tiempo deslizante.

    Cuenta fallos en una ventana de N segundos.
    Abre el circuito si se supera el umbral de error.
    """
    service_name: str
    window_seconds: float = 60.0
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    half_open_max_requests: int = 3

    def __post_init__(self):
        self._failures: deque[float] = deque()
        self._successes: deque[float] = deque()
        self.state: CircuitState = CircuitState.CLOSED
        self._last_open_time: float = 0.0
        self._half_open_count: int = 0

    def _prune_window(self):
        now = time.time()
        cutoff = now - self.window_seconds
        while self._failures and self._failures[0] < cutoff:
            self._failures.popleft()
        while self._successes and self._successes[0] < cutoff:
            self._successes.popleft()

    def record_success(self):
        self._successes.append(time.time())
        if self.state == CircuitState.HALF_OPEN:
            self._half_open_count += 1
            if self._half_open_count >= self.half_open_max_requests:
                self.state = CircuitState.CLOSED
                self._half_open_count = 0
                self._failures.clear()
        elif self.state == CircuitState.OPEN:
            self.state = CircuitState.CLOSED
            self._failures.clear()

    def record_failure(self):
        now = time.time()
        self._failures.append(now)
        self._prune_window()
        if len(self._failures) >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self._last_open_time = now
            log_event("service_mesh", f"circuit_open:{self.service_name}:{len(self._failures)} fallos")

    def allow_request(self) -> bool:
        self._prune_window()
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self._last_open_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self._half_open_count = 0
                return True
            return False
        return self._half_open_count < self.half_open_max_requests

    @property
    def error_rate(self) -> float:
        self._prune_window()
        total = len(self._failures) + len(self._successes)
        return len(self._failures) / total if total > 0 else 0.0


# ═══════════════════════════════════════════════════════════════════
# 2. RATE LIMITER INTERNO POR SERVICIO
# ═══════════════════════════════════════════════════════════════════

@dataclass
class InternalRateLimiter:
    """Rate limiter interno con token bucket por servicio.

    Protege los sockets del endpoint critico /sync/batch
    contra saturacion por procesos batch internos.
    """
    service_name: str
    max_rps: float = 50.0       # requests per second
    burst: int = 10

    def __post_init__(self):
        self._tokens: float = float(self.burst)
        self._last_refill: float = time.time()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            now = time.time()
            elapsed = now - self._last_refill
            self._tokens = min(
                float(self.burst),
                self._tokens + elapsed * self.max_rps,
            )
            self._last_refill = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False


# ═══════════════════════════════════════════════════════════════════
# 3. PROXY DE SERVICIO MESH
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ServiceEndpoint:
    """Endpoint de un servicio interno."""
    name: str
    base_url: str
    health_check_path: str = "/health"
    timeout: float = 10.0
    max_retries: int = 3


class ServiceMeshProxy:
    """Proxy helper para comunicacion interna entre microservicios.

    Caracteristicas:
    - Retry automatico con backoff exponencial + jitter
    - Circuit breaker por servicio con ventana deslizante
    - Rate limiting interno por servicio
    - Health checking automatico
    """

    BACKOFF_BASE = 0.5  # segundos
    JITTER_MAX = 0.3     # segundos

    def __init__(self):
        self._endpoints: dict[str, ServiceEndpoint] = {}
        self._circuit_breakers: dict[str, SlidingWindowCircuitBreaker] = {}
        self._rate_limiters: dict[str, InternalRateLimiter] = {}
        self._client: Optional[httpx.AsyncClient] = None
        self._health_tasks: dict[str, asyncio.Task] = {}
        self._healthy: dict[str, bool] = {}

    def register_service(self, endpoint: ServiceEndpoint,
                         circuit_cfg: Optional[dict] = None,
                         rate_cfg: Optional[dict] = None):
        """Registra un servicio interno en la malla.

        Args:
            endpoint: Configuracion del endpoint.
            circuit_cfg: {window_seconds, failure_threshold, recovery_timeout}
            rate_cfg: {max_rps, burst}
        """
        self._endpoints[endpoint.name] = endpoint
        self._circuit_breakers[endpoint.name] = SlidingWindowCircuitBreaker(
            service_name=endpoint.name,
            **(circuit_cfg or {}),
        )
        self._rate_limiters[endpoint.name] = InternalRateLimiter(
            service_name=endpoint.name,
            **(rate_cfg or {}),
        )
        self._healthy[endpoint.name] = True
        log_event("service_mesh", f"registered:{endpoint.name}:{endpoint.base_url}")

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                limits=httpx.Limits(
                    max_keepalive_connections=50,
                    max_connections=100,
                ),
            )
        return self._client

    @staticmethod
    def _jitter(delay: float) -> float:
        return delay + random.uniform(0, ServiceMeshProxy.JITTER_MAX)

    async def request(self, service_name: str, method: str, path: str,
                      **kwargs) -> httpx.Response:
        """Realiza una peticion a un servicio interno con resiliencia.

        Aplica: rate limit -> circuit breaker -> retry con backoff + jitter.

        Args:
            service_name: Nombre del servicio registrado.
            method: HTTP method.
            path: Ruta del endpoint (ej. /health).
            **kwargs: Pasados a httpx.AsyncClient.request().

        Returns:
            httpx.Response del servicio.

        Raises:
            ServiceUnavailableError: si el circuito esta abierto.
            ServiceOverloadedError: si rate limit excedido.
        """
        endpoint = self._endpoints.get(service_name)
        if not endpoint:
            raise ValueError(f"Servicio no registrado: {service_name}")

        # 1. Rate limiting
        limiter = self._rate_limiters[service_name]
        if not await limiter.acquire():
            log_event("service_mesh", f"rate_limited:{service_name}")
            raise ServiceOverloadedError(service_name)

        # 2. Circuit breaker check
        cb = self._circuit_breakers[service_name]
        if not cb.allow_request():
            log_event("service_mesh", f"circuit_blocked:{service_name}")
            raise ServiceUnavailableError(service_name)

        # 3. Retry con backoff + jitter
        client = await self._get_client()
        url = f"{endpoint.base_url.rstrip('/')}/{path.lstrip('/')}"
        last_error: Optional[Exception] = None

        for attempt in range(endpoint.max_retries):
            try:
                response = await client.request(method, url, timeout=endpoint.timeout, **kwargs)
                if response.status_code < 500:
                    cb.record_success()
                    return response
                else:
                    cb.record_failure()
                    last_error = ServiceHttpError(service_name, response.status_code)

            except (httpx.TimeoutException, httpx.ConnectError, ConnectionError) as exc:
                cb.record_failure()
                last_error = ServiceNetworkError(service_name, str(exc))

            if attempt < endpoint.max_retries - 1:
                delay = self._jitter(self.BACKOFF_BASE * (2 ** attempt))
                log_event("service_mesh", f"retry:{service_name}:attempt={attempt + 1}:delay={delay:.2f}s")
                await asyncio.sleep(delay)

        raise last_error or ServiceUnavailableError(service_name)

    async def request_json(self, service_name: str, method: str, path: str,
                           **kwargs) -> dict:
        """request() + parse JSON response."""
        response = await self.request(service_name, method, path, **kwargs)
        return response.json()

    async def health_check(self, service_name: str) -> bool:
        """Verifica salud de un servicio."""
        try:
            resp = await self.request(service_name, "GET", "/health", timeout=5.0)
            healthy = resp.status_code == 200
        except Exception:
            healthy = False
        self._healthy[service_name] = healthy
        return healthy

    async def health_check_all(self) -> dict[str, bool]:
        """Verifica salud de todos los servicios registrados."""
        results = {}
        for name in self._endpoints:
            results[name] = await self.health_check(name)
        return results

    def get_stats(self) -> dict:
        """Estadisticas de la malla."""
        return {
            "services": {
                name: {
                    "healthy": self._healthy.get(name, False),
                    "circuit_state": self._circuit_breakers[name].state.value,
                    "error_rate": round(self._circuit_breakers[name].error_rate, 3),
                }
                for name in self._endpoints
            },
            "total_services": len(self._endpoints),
        }

    async def close(self):
        for task in self._health_tasks.values():
            task.cancel()
        if self._client:
            await self._client.aclose()
            self._client = None


# ═══════════════════════════════════════════════════════════════════
# 4. EXCEPCIONES
# ═══════════════════════════════════════════════════════════════════

class ServiceMeshError(Exception):
    pass

class ServiceUnavailableError(ServiceMeshError):
    def __init__(self, service: str):
        super().__init__(f"Servicio no disponible: {service}")

class ServiceOverloadedError(ServiceMeshError):
    def __init__(self, service: str):
        super().__init__(f"Servicio sobrecargado: {service} (rate limit)")

class ServiceHttpError(ServiceMeshError):
    def __init__(self, service: str, status: int):
        super().__init__(f"Error HTTP {status} en servicio: {service}")

class ServiceNetworkError(ServiceMeshError):
    def __init__(self, service: str, detail: str):
        super().__init__(f"Error de red en servicio {service}: {detail}")


__all__ = [
    "ServiceMeshProxy",
    "ServiceEndpoint",
    "SlidingWindowCircuitBreaker",
    "InternalRateLimiter",
    "ServiceUnavailableError",
    "ServiceOverloadedError",
    "ServiceHttpError",
    "ServiceNetworkError",
]
