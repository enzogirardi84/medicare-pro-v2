"""Tests para core.incremental_snapshot — IVM y agregados."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestIVMSQL:
    def test_schema_contains_tables(self):
        from core.incremental_snapshot import IVM_SQL
        assert "agg_epidemiologia_mensual" in IVM_SQL
        assert "agg_eventos_por_tipo" in IVM_SQL
        assert "ivm_update_snapshot" in IVM_SQL
        assert "ivm_update_epidemiologia" in IVM_SQL
        assert "trg_ivm_snapshot" in IVM_SQL
        assert "trg_ivm_epidemiologia" in IVM_SQL

    def test_schema_has_apply_function_ref(self):
        from core.incremental_snapshot import IVM_SQL
        assert "apply_event_to_state" in IVM_SQL


class TestIncrementalSnapshotManager:
    def test_import(self):
        from core.incremental_snapshot import IncrementalSnapshotManager
        assert IncrementalSnapshotManager is not None

    def test_install_triggers(self):
        from core.incremental_snapshot import IncrementalSnapshotManager
        mgr = IncrementalSnapshotManager()
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "snapshot_installed": True, "epi_installed": True,
        })
        mgr._conn = mock_conn
        result = asyncio.run(mgr.install_triggers())
        assert result["snapshot_trigger"] is True

    def test_remove_triggers(self):
        from core.incremental_snapshot import IncrementalSnapshotManager
        mgr = IncrementalSnapshotManager()
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mgr._conn = mock_conn
        result = asyncio.run(mgr.remove_triggers())
        assert result["snapshot_removed"] is True

    def test_get_snapshot_not_found(self):
        from core.incremental_snapshot import IncrementalSnapshotManager
        mgr = IncrementalSnapshotManager()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mgr._conn = mock_conn
        result = asyncio.run(mgr.get_snapshot("evolucion", "nonexistent"))
        assert result is None

    def test_get_snapshot_found(self):
        from core.incremental_snapshot import IncrementalSnapshotManager
        mgr = IncrementalSnapshotManager()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "state": '{"d":"test"}', "version": 3, "checksum": "abc",
            "updated_at": None,
        })
        mgr._conn = mock_conn
        result = asyncio.run(mgr.get_snapshot("evolucion", "evo-1"))
        assert result["version"] == 3
        assert result["state"]["d"] == "test"

    def test_get_monthly_epidemiologia_not_found(self):
        from core.incremental_snapshot import IncrementalSnapshotManager
        mgr = IncrementalSnapshotManager()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        mgr._conn = mock_conn
        result = asyncio.run(mgr.get_monthly_epidemiologia("t1", "2026-06"))
        assert result is None

    def test_get_event_type_counts_empty(self):
        from core.incremental_snapshot import IncrementalSnapshotManager
        mgr = IncrementalSnapshotManager()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mgr._conn = mock_conn
        result = asyncio.run(mgr.get_event_type_counts("t1"))
        assert result == []

    def test_refresh_full_snapshot(self):
        from core.incremental_snapshot import IncrementalSnapshotManager
        mgr = IncrementalSnapshotManager()
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()

        # Mock for ClinicalEventStore.replay
        with patch("core.clinical_event_store.ClinicalEventStore.replay",
                   return_value={"state": {"d": "test"}, "version": 5, "checksum": "abc"}):
            mgr._conn = mock_conn
            result = asyncio.run(mgr.refresh_full_snapshot("evolucion", "evo-1"))
            assert result["version"] == 5

    def test_close(self):
        from core.incremental_snapshot import IncrementalSnapshotManager
        mgr = IncrementalSnapshotManager()
        mock_conn = MagicMock()
        mock_conn.close = AsyncMock()
        mgr._conn = mock_conn
        asyncio.run(mgr.close())
        mock_conn.close.assert_awaited_once()


class TestAggregatedQueryCache:
    def test_get_miss(self):
        from core.incremental_snapshot import AggregatedQueryCache
        cache = AggregatedQueryCache()
        result = cache.get("report", "t1", month="2026-06")
        assert result is None

    def test_set_and_get(self):
        from core.incremental_snapshot import AggregatedQueryCache
        cache = AggregatedQueryCache()
        cache.set("report", "t1", {"total": 100}, month="2026-06")
        result = cache.get("report", "t1", month="2026-06")
        assert result == {"total": 100}

    def test_invalidate_tenant(self):
        from core.incremental_snapshot import AggregatedQueryCache
        cache = AggregatedQueryCache()
        cache.set("r1", "t1", "data1")
        cache.set("r2", "t2", "data2")
        cache.invalidate_tenant("t1")
        assert cache.get("r1", "t1") is None
        assert cache.get("r2", "t2") == "data2"

    def test_cache_eviction(self):
        from core.incremental_snapshot import AggregatedQueryCache
        cache = AggregatedQueryCache(max_size=2)
        cache.set("r1", "t1", "a")
        cache.set("r2", "t1", "b")
        cache.set("r3", "t1", "c")
        assert cache.get("r1", "t1") is None  # should have been evicted
