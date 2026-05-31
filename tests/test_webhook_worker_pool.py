"""Tests para core.webhook_worker_pool — Worker Pool de alta densidad."""
from __future__ import annotations

import asyncio
from unittest.mock import patch

import pytest


class TestCircuitBreaker:
    def test_initial_state_closed(self):
        from core.webhook_worker_pool import CircuitBreaker, CircuitState
        cb = CircuitBreaker(url="https://example.com/webhook")
        assert cb.state == CircuitState.CLOSED
        assert cb.allow_request() is True

    def test_opens_after_threshold_failures(self):
        from core.webhook_worker_pool import CircuitBreaker, CircuitState
        cb = CircuitBreaker(url="https://example.com/webhook", failure_threshold=3, recovery_timeout=9999)
        for _ in range(3):
            cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert cb.allow_request() is False

    def test_half_open_after_recovery_timeout(self):
        from core.webhook_worker_pool import CircuitBreaker, CircuitState
        cb = CircuitBreaker(url="https://example.com/webhook", failure_threshold=2, recovery_timeout=0.01)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        import time
        time.sleep(0.02)
        assert cb.allow_request() is True
        assert cb.state == CircuitState.HALF_OPEN

    def test_closes_after_success(self):
        from core.webhook_worker_pool import CircuitBreaker, CircuitState
        cb = CircuitBreaker(url="https://example.com/webhook", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.last_failure_time = 0
        cb.allow_request()
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0


class TestWebhookChannel:
    def test_channel_key(self):
        from core.webhook_worker_pool import WebhookChannel
        ch = WebhookChannel(channel_key="t1:checkin.realizado")
        assert ch.channel_key == "t1:checkin.realizado"
        assert ch.queue.qsize() == 0

    def test_get_circuit_breaker_creates_new(self):
        from core.webhook_worker_pool import WebhookChannel
        ch = WebhookChannel(channel_key="t1:evt")
        cb = ch.get_circuit_breaker("https://example.com/hook")
        assert cb.url == "https://example.com/hook"
        assert cb is ch.get_circuit_breaker("https://example.com/hook")


class TestWebhookJob:
    def test_job_defaults(self):
        from core.webhook_worker_pool import WebhookJob
        job = WebhookJob(event_type="checkin.realizado", tenant_id="t1",
                         url="https://hook.example", secreto="sec",
                         payload_bytes=b"{}")
        assert job.intento == 0
        assert job.max_intentos == 5
        assert job.timestamp > 0


class TestWebhookWorkerPool:
    def test_import(self):
        from core.webhook_worker_pool import WebhookWorkerPool, get_pool, close_pool
        assert WebhookWorkerPool is not None

    def test_enqueue_sin_urls_retorna_false(self):
        from core.webhook_worker_pool import WebhookWorkerPool
        pool = WebhookWorkerPool()
        result = asyncio.run(pool.enqueue("tenant_sin_url", "test.event", {"data": 1}))
        assert result is False

    @patch.dict("os.environ", {
        "WEBHOOK_TENANT1_URL": "https://hook.example/callback",
        "WEBHOOK_TENANT1_SECRET": "shh-secret",
    })
    def test_enqueue_con_urls_retorna_true(self):
        from core.webhook_worker_pool import WebhookWorkerPool
        pool = WebhookWorkerPool()
        result = asyncio.run(pool.enqueue("tenant1", "test.event", {"data": 1}))
        assert result is True
        pool._channels.clear()

    def test_get_channel_creates_new(self):
        from core.webhook_worker_pool import WebhookWorkerPool
        pool = WebhookWorkerPool()
        ch = pool._get_channel("t1", "evt")
        assert ch.channel_key == "t1:evt"
        assert ch is pool._get_channel("t1", "evt")

    def test_ensure_workers_adds_tasks(self):
        import asyncio
        from core.webhook_worker_pool import WebhookWorkerPool, WebhookChannel, WebhookJob

        async def run():
            pool = WebhookWorkerPool()
            ch = WebhookChannel(channel_key="t1:evt")
            for _ in range(3):
                ch.queue.put_nowait(WebhookJob(
                    event_type="evt", tenant_id="t1",
                    url="https://hook.example", secreto="s",
                    payload_bytes=b"{}",
                ))
            pool._ensure_workers(ch)
            assert len(ch.workers) > 0
            for task in ch.workers:
                task.cancel()
            return True

        assert asyncio.run(run()) is True

    def test_firmar_payload(self):
        from core.webhook_worker_pool import WebhookWorkerPool
        pool = WebhookWorkerPool()
        sig = pool._firmar_payload(b'{"a":1}', "secret")
        assert len(sig) == 64
        assert isinstance(sig, str)

    @patch.dict("os.environ", {
        "WEBHOOK_TENANT2_URL": "https://hook.test/wh",
        "WEBHOOK_TENANT2_SECRET": "test-secret",
    })
    def test_enqueue_multiple_urls(self):
        from core.webhook_worker_pool import WebhookWorkerPool
        pool = WebhookWorkerPool()
        result = asyncio.run(pool.enqueue("tenant2", "multi.event", {"key": "val"}))
        assert result is True
        pool._channels.clear()

    def test_stats_empty_pool(self):
        from core.webhook_worker_pool import WebhookWorkerPool
        pool = WebhookWorkerPool()
        stats = asyncio.run(pool.get_stats())
        assert stats["channel_count"] == 0
        assert stats["total_workers"] == 0

    def test_close_pool(self):
        from core.webhook_worker_pool import WebhookWorkerPool, get_pool, close_pool
        pool = get_pool()
        assert pool is not None
        asyncio.run(close_pool())
