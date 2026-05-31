"""Tests para core.zero_downtime_maintenance — Vacuum + REINDEX."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestVacuumConfigSQL:
    def test_sql_contains_tables(self):
        from core.zero_downtime_maintenance import VACUUM_CONFIG_SQL
        assert "event_ingest_queue" in VACUUM_CONFIG_SQL
        assert "clinical_event_store" in VACUUM_CONFIG_SQL
        assert "checkins_gps" in VACUUM_CONFIG_SQL
        assert "clinical_snapshot" in VACUUM_CONFIG_SQL


class TestReindexManager:
    def test_get_candidates_empty(self):
        from core.zero_downtime_maintenance import ReindexManager
        mgr = ReindexManager()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mgr._conn = mock_conn
        candidates = asyncio.run(mgr.get_reindex_candidates())
        assert candidates == []

    def test_get_candidates_with_data(self):
        from core.zero_downtime_maintenance import ReindexManager
        mgr = ReindexManager()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"schemaname": "public", "tablename": "clinical_event_store",
             "indexname": "idx_ces_aggregate", "indexdef": "CREATE INDEX ...",
             "index_size": "256 MB", "scans": 500},
        ])
        mgr._conn = mock_conn
        candidates = asyncio.run(mgr.get_reindex_candidates())
        assert len(candidates) == 1
        assert candidates[0]["indexname"] == "idx_ces_aggregate"

    def test_reindex_index_success(self):
        from core.zero_downtime_maintenance import ReindexManager
        mgr = ReindexManager()
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock(return_value=None)
        mgr._conn = mock_conn
        result = asyncio.run(mgr.reindex_index("public", "idx_test"))
        assert result["success"] is True
        assert result["index"] == "public.idx_test"

    def test_parse_size(self):
        from core.zero_downtime_maintenance import ReindexManager
        assert ReindexManager._parse_size("256 MB") == 256
        assert ReindexManager._parse_size("1 GB") == 1
        assert ReindexManager._parse_size("") == 0


class TestBloatSQL:
    def test_bloat_sql_present(self):
        from core.zero_downtime_maintenance import BLOAT_ESTIMATE_SQL
        assert "pg_stat_user_tables" in BLOAT_ESTIMATE_SQL
        assert "n_dead_tup" in BLOAT_ESTIMATE_SQL
