"""Tests para core.data_virtualization — Auditoria SQLite efimero."""
from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestAuditExportRequest:
    def test_request_defaults(self):
        from core.data_virtualization import AuditExportRequest
        req = AuditExportRequest(aggregate_type="evolucion", aggregate_id="evo-1",
                                  tenant_id="t1")
        assert req.format == "sqlite"
        assert req.include_snapshot is True


class TestAuditVirtualizationEngine:
    def _check_sqlite(self, data: bytes, expected_events: int = 1,
                      has_snapshot: bool = False):
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".check.db")
        tmp.write(data)
        tmp.close()
        try:
            conn = sqlite3.connect(tmp.name)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM events")
            assert cursor.fetchone()[0] == expected_events
            cursor.execute("SELECT name FROM sqlite_master WHERE type='view' AND name='replay'")
            assert cursor.fetchone() is not None
            if has_snapshot:
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='snapshot'")
                assert cursor.fetchone() is not None
            conn.close()
        finally:
            os.unlink(tmp.name)

    def test_export_to_sqlite_creates_valid_db(self):
        from core.data_virtualization import AuditVirtualizationEngine, AuditExportRequest
        engine = AuditVirtualizationEngine()

        mock_events = [
            {"event_version": 1, "event_type": "EvolucionCreada", "tenant_id": "t1",
             "actor_id": "p1", "payload": {"d": "neumonia"}, "checksum": "abc",
             "prev_event_id": None, "created_at": None},
        ]
        engine._fetch_events = AsyncMock(return_value=mock_events)
        engine._fetch_snapshot = AsyncMock(return_value=None)
        engine._fetch_lineage = AsyncMock(return_value=[])

        req = AuditExportRequest("evolucion", "evo-1", "t1")
        result = asyncio.run(engine.export_to_sqlite(req))

        assert result.format == "sqlite"
        assert result.event_count == 1
        assert result.checksum is not None
        assert result.data is not None
        self._check_sqlite(result.data, expected_events=1)

    def test_export_to_sqlite_with_snapshot(self):
        from core.data_virtualization import AuditVirtualizationEngine, AuditExportRequest
        engine = AuditVirtualizationEngine()
        engine._fetch_events = AsyncMock(return_value=[
            {"event_version": 1, "event_type": "EvolucionCreada", "tenant_id": "t1",
             "actor_id": "p1", "payload": {"d": "test"}, "checksum": "abc",
             "prev_event_id": None, "created_at": None},
        ])
        engine._fetch_snapshot = AsyncMock(return_value={
            "state": {"d": "test"}, "version": 1, "checksum": "abc", "updated_at": None,
        })
        engine._fetch_lineage = AsyncMock(return_value=[])

        req = AuditExportRequest("evolucion", "evo-1", "t1", include_snapshot=True)
        result = asyncio.run(engine.export_to_sqlite(req))
        self._check_sqlite(result.data, expected_events=1, has_snapshot=True)

    def test_export_to_encrypted_json(self):
        from core.data_virtualization import AuditVirtualizationEngine, AuditExportRequest
        engine = AuditVirtualizationEngine()
        engine._fetch_events = AsyncMock(return_value=[
            {"event_version": 1, "event_type": "EvolucionCreada", "tenant_id": "t1",
             "actor_id": "p1", "payload": {"d": "secret"}, "checksum": "abc",
             "prev_event_id": None, "created_at": None},
        ])
        engine._fetch_snapshot = AsyncMock(return_value=None)

        req = AuditExportRequest("evolucion", "evo-1", "t1", auditor_id="auditor-1",
                                  reason="auditoria anual")
        result, key = asyncio.run(engine.export_to_encrypted_json(req))

        assert result.format == "json.encrypted"
        assert result.event_count == 1
        assert len(key) == 32
        assert result.data[:12] != b'{"metadata"'  # encriptado != plano

    def test_verify_export_valid(self):
        from core.data_virtualization import AuditVirtualizationEngine, AuditExportRequest
        engine = AuditVirtualizationEngine()
        engine._fetch_events = AsyncMock(return_value=[])
        engine._fetch_snapshot = AsyncMock(return_value=None)
        engine._fetch_lineage = AsyncMock(return_value=[])

        req = AuditExportRequest("evolucion", "evo-v", "t1")
        result = asyncio.run(engine.export_to_sqlite(req))
        verification = engine.verify_export(result.export_id)
        assert verification["valid"] is True

    def test_verify_export_not_found(self):
        from core.data_virtualization import AuditVirtualizationEngine
        engine = AuditVirtualizationEngine()
        assert engine.verify_export("nonexistent") is None

    def test_get_export_not_found(self):
        from core.data_virtualization import AuditVirtualizationEngine
        engine = AuditVirtualizationEngine()
        assert engine.get_export("nonexistent") is None


class TestLocalReplaySQL:
    def test_replay_sql_available(self):
        from core.data_virtualization import LOCAL_REPLAY_SQL
        assert "replay" in LOCAL_REPLAY_SQL.lower()
