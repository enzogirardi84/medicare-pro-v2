"""Tests para core.zero_lock_postgres — Zero-Lock Ingestion."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestZeroLockSQL:
    def test_sql_contains_tables(self):
        from core.zero_lock_postgres import ZERO_LOCK_SQL
        assert "event_ingest_queue" in ZERO_LOCK_SQL
        assert "consume_ingest_batch" in ZERO_LOCK_SQL
        assert "consolidate_ingest_batch" in ZERO_LOCK_SQL
        assert "deferred_ivm_update" in ZERO_LOCK_SQL
        assert "SKIP LOCKED" in ZERO_LOCK_SQL


class TestZeroLockIngestion:
    def test_enqueue_event(self):
        from core.zero_lock_postgres import ZeroLockIngestion
        ing = ZeroLockIngestion()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value={"id": 42})
        ing._conn = mock_conn
        result = asyncio.run(ing.enqueue_event(
            "evolucion", "evo-1", "EvolucionCreada",
            "t1", "actor-1", {"diagnostico": "test"},
            checksum="abc", vector_clock="local:1",
        ))
        assert result == 42

    def test_consume_and_consolidate_empty(self):
        from core.zero_lock_postgres import ZeroLockIngestion
        ing = ZeroLockIngestion()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        ing._conn = mock_conn
        result = asyncio.run(ing.consume_and_consolidate(100))
        assert result == 0

    def test_consume_and_consolidate_with_data(self):
        from core.zero_lock_postgres import ZeroLockIngestion
        ing = ZeroLockIngestion()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"id": 1, "aggregate_type": "evo", "aggregate_id": "a1"},
            {"id": 2, "aggregate_type": "evo", "aggregate_id": "a2"},
        ])
        mock_conn.fetchval = AsyncMock(return_value=2)
        ing._conn = mock_conn
        result = asyncio.run(ing.consume_and_consolidate(100))
        assert result == 2

    def test_run_deferred_ivm(self):
        from core.zero_lock_postgres import ZeroLockIngestion
        ing = ZeroLockIngestion()
        mock_conn = MagicMock()
        mock_conn.fetchval = AsyncMock(return_value=5)
        ing._conn = mock_conn
        result = asyncio.run(ing.run_deferred_ivm(500))
        assert result == 5

    def test_get_queue_depth(self):
        from core.zero_lock_postgres import ZeroLockIngestion
        ing = ZeroLockIngestion()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "pending": 10, "processing": 2, "errors": 0,
        })
        ing._conn = mock_conn
        depth = asyncio.run(ing.get_queue_depth())
        assert depth["pending"] == 10
        assert depth["errors"] == 0

    def test_close(self):
        from core.zero_lock_postgres import ZeroLockIngestion
        ing = ZeroLockIngestion()
        mock_conn = MagicMock()
        mock_conn.close = AsyncMock()
        ing._conn = mock_conn
        asyncio.run(ing.close())
        mock_conn.close.assert_awaited_once()
