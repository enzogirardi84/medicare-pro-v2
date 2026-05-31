"""Worker Pool asincrono para webhooks de alta densidad.
Colas independientes por canal (tenant+event_type), circuit breaker,
backpressure y aislamiento de fallos entre canales.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

import httpx

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. ESTADOS DEL CIRCUIT BREAKER
# ═══════════════════════════════════════════════════════════════════

class CircuitState(Enum):
    CLOSED = "closed"       # Funcionando normalmente
    OPEN = "open"           # Fallos detectados, rechazar peticiones
    HALF_OPEN = "half_open" # Probando recuperacion


@dataclass
class CircuitBreaker:
    """Circuit breaker por URL de webhook.

    Abre el circuito tras N fallos consecutivos,
    reintenta tras un timeout de recuperacion.
    """
    url: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    half_open_attempts: int = 0
    max_half_open_attempts: int = 2

    def record_success(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.half_open_attempts = 0

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_time = time.time()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            log_event("circuit_breaker", f"OPEN:{self.url[:40]}:{self.failure_count} fallos")

    def allow_request(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_attempts = 0
                return True
            return False
        # HALF_OPEN: permitir un numero limitado
        if self.half_open_attempts < self.max_half_open_attempts:
            self.half_open_attempts += 1
            return True
        return False


# ═══════════════════════════════════════════════════════════════════
# 2. MODELO DE TRABAJO (WEBHOOK JOB)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class WebhookJob:
    """Unidad de trabajo para el worker pool."""
    event_type: str
    tenant_id: str
    url: str
    secreto: str
    payload_bytes: bytes
    timestamp: float = field(default_factory=time.time)
    intento: int = 0
    max_intentos: int = 5


# ═══════════════════════════════════════════════════════════════════
# 3. CANAL: COLA INDEPENDIENTE POR (tenant_id, event_type)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class WebhookChannel:
    """Canal aislado con su propia cola y workers."""
    channel_key: str  # "{tenant_id}:{event_type}"
    queue: asyncio.Queue = field(default_factory=lambda: asyncio.Queue(maxsize=5000))
    workers: set[asyncio.Task] = field(default_factory=set)
    max_workers: int = 5
    circuit_breakers: dict[str, CircuitBreaker] = field(default_factory=dict)
    dropped_count: int = 0
    processed_count: int = 0

    def get_circuit_breaker(self, url: str) -> CircuitBreaker:
        if url not in self.circuit_breakers:
            self.circuit_breakers[url] = CircuitBreaker(url=url)
        return self.circuit_breakers[url]


# ═══════════════════════════════════════════════════════════════════
# 4. WORKER POOL PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

class WebhookWorkerPool:
    """Pool de workers asincronos con colas independientes por canal.

    Caracteristicas:
    - Cola separada por (tenant_id, event_type)
    - Circuit breaker por URL de destino
    - Workers dinamicos: hasta max_workers por canal
    - Backpressure: cola con maxsize, descarta si se llena
    - Timeout configurable por peticion
    """

    TIMEOUT = 10.0
    BACKOFF_BASE = 2.0
    GLOBAL_MAX_WORKERS = 200

    def __init__(self):
        self._channels: dict[str, WebhookChannel] = {}
        self._client: Optional[httpx.AsyncClient] = None
        self._global_semaphore = asyncio.Semaphore(self.GLOBAL_MAX_WORKERS)

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.TIMEOUT,
                limits=httpx.Limits(
                    max_keepalive_connections=100,
                    max_connections=200,
                    keepalive_expiry=30.0,
                ),
            )
        return self._client

    def _get_channel(self, tenant_id: str, event_type: str) -> WebhookChannel:
        key = f"{tenant_id}:{event_type}"
        if key not in self._channels:
            self._channels[key] = WebhookChannel(channel_key=key)
        return self._channels[key]

    def _firmar_payload(self, payload: bytes, secreto: str) -> str:
        return hmac.new(
            secreto.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

    async def _get_webhook_urls(self, tenant_id: str) -> list[tuple[str, str]]:
        """Obtiene URLs configuradas para un tenant."""
        urls = []
        env_url = os.environ.get(f"WEBHOOK_{tenant_id.upper()}_URL")
        env_secret = os.environ.get(f"WEBHOOK_{tenant_id.upper()}_SECRET")
        if env_url and env_secret:
            urls.append((env_url, env_secret))
        return urls

    async def enqueue(self, tenant_id: str, event_type: str,
                      payload: dict[str, Any]) -> bool:
        """Encola un evento para ser despachado.

        Args:
            tenant_id: ID del tenant.
            event_type: Tipo de evento (ej. 'checkin.realizado').
            payload: Datos del evento.

        Returns:
            True si se encolo exitosamente, False si la cola esta llena.
        """
        urls = await self._get_webhook_urls(tenant_id)
        if not urls:
            return False

        payload_bytes = json.dumps({
            "event_type": event_type,
            "tenant_id": tenant_id,
            "timestamp": time.time(),
            "data": payload,
        }, ensure_ascii=False, default=str).encode("utf-8")

        channel = self._get_channel(tenant_id, event_type)
        job_count = 0

        for url, secreto in urls:
            job = WebhookJob(
                event_type=event_type,
                tenant_id=tenant_id,
                url=url,
                secreto=secreto,
                payload_bytes=payload_bytes,
            )
            try:
                channel.queue.put_nowait(job)
                job_count += 1
            except asyncio.QueueFull:
                channel.dropped_count += 1
                log_event("webhook_pool", f"queue_full:{tenant_id}:{event_type}:{url[:40]}")

        # Asegurar workers activos
        self._ensure_workers(channel)
        return job_count > 0

    def _ensure_workers(self, channel: WebhookChannel):
        """Agrega workers si el canal tiene menos del maximo."""
        active = {t for t in channel.workers if not t.done()}
        channel.workers = active
        needed = min(channel.max_workers - len(active), channel.queue.qsize())
        for _ in range(needed):
            task = asyncio.create_task(self._worker_loop(channel))
            channel.workers.add(task)

    async def _worker_loop(self, channel: WebhookChannel):
        """Loop del worker: consume jobs de la cola del canal."""
        client = await self._get_client()

        while True:
            try:
                job = await asyncio.wait_for(channel.queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                # Cola vacia por 1s, worker se retira
                if channel.queue.empty():
                    break
                continue

            async with self._global_semaphore:
                await self._process_job(client, channel, job)

    async def _process_job(self, client: httpx.AsyncClient,
                           channel: WebhookChannel, job: WebhookJob):
        """Procesa un job individual con circuit breaker."""
        cb = channel.get_circuit_breaker(job.url)

        if not cb.allow_request():
            log_event("webhook_pool", f"circuit_open:{job.url[:40]}")
            # Reencolar para reintentar despues
            if job.intento < job.max_intentos:
                job.intento += 1
                await asyncio.sleep(self.BACKOFF_BASE * (2 ** job.intento))
                try:
                    channel.queue.put_nowait(job)
                except asyncio.QueueFull:
                    channel.dropped_count += 1
            return

        firma = self._firmar_payload(job.payload_bytes, job.secreto)

        try:
            response = await client.post(
                job.url,
                content=job.payload_bytes,
                headers={
                    "Content-Type": "application/json",
                    "X-Hub-Signature-256": f"sha256={firma}",
                    "X-Tenant-Id": job.tenant_id,
                    "X-Event-Type": job.event_type,
                    "User-Agent": "MediCare-WebhookPool/1.0",
                },
            )

            if response.status_code == 200:
                cb.record_success()
                channel.processed_count += 1
                log_event("webhook_pool", f"ok:{job.url[:40]}:{job.event_type}")
            else:
                log_event("webhook_pool", f"http_{response.status_code}:{job.url[:40]}")
                self._handle_retry(channel, job)

        except (httpx.TimeoutException, httpx.ConnectionError) as exc:
            cb.record_failure()
            log_event("webhook_pool", f"error:{job.url[:40]}:{type(exc).__name__}")
            self._handle_retry(channel, job)

    def _handle_retry(self, channel: WebhookChannel, job: WebhookJob):
        """Reintenta el job con backoff exponencial."""
        if job.intento < job.max_intentos:
            job.intento += 1
            delay = self.BACKOFF_BASE * (2 ** job.intento)
            asyncio.create_task(self._delayed_retry(channel, job, delay))
        else:
            log_event("webhook_pool", f"max_retries:{job.url[:40]}:{job.event_type}")

    async def _delayed_retry(self, channel: WebhookChannel, job: WebhookJob, delay: float):
        await asyncio.sleep(delay)
        try:
            channel.queue.put_nowait(job)
        except asyncio.QueueFull:
            channel.dropped_count += 1

    async def get_stats(self) -> dict:
        """Estadisticas del pool."""
        return {
            "channel_count": len(self._channels),
            "total_workers": sum(len(ch.workers) for ch in self._channels.values()),
            "total_processed": sum(ch.processed_count for ch in self._channels.values()),
            "total_dropped": sum(ch.dropped_count for ch in self._channels.values()),
            "channels": {
                k: {
                    "queue_size": ch.queue.qsize(),
                    "workers": len(ch.workers),
                    "processed": ch.processed_count,
                    "dropped": ch.dropped_count,
                    "circuit_breakers": sum(1 for cb in ch.circuit_breakers.values()
                                            if cb.state == CircuitState.OPEN),
                }
                for k, ch in self._channels.items()
            },
        }

    async def close(self):
        """Cierra el pool y libera recursos."""
        for channel in self._channels.values():
            for task in channel.workers:
                task.cancel()
            await asyncio.gather(*channel.workers, return_exceptions=True)
        if self._client:
            await self._client.aclose()
            self._client = None
        self._channels.clear()


# ═══════════════════════════════════════════════════════════════════
# 5. SINGLETON GLOBAL
# ═══════════════════════════════════════════════════════════════════

_pool: Optional[WebhookWorkerPool] = None


def get_pool() -> WebhookWorkerPool:
    """Retorna el pool singleton."""
    global _pool
    if _pool is None:
        _pool = WebhookWorkerPool()
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None


__all__ = [
    "WebhookWorkerPool",
    "WebhookJob",
    "WebhookChannel",
    "CircuitBreaker",
    "CircuitState",
    "get_pool",
    "close_pool",
]
