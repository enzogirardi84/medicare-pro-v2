"""Tests para scripts.delta_sync — Delta Sync con MessagePack."""
from __future__ import annotations

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestDeltaModels:
    """Tests para modelos DeltaRequest y DeltaResponse."""

    def test_delta_request_defaults(self):
        from scripts.delta_sync import DeltaRequest
        req = DeltaRequest(tenant_id="t1")
        assert req.tenant_id == "t1"
        assert req.ultimo_timestamp == 0.0
        assert req.ultimas_versiones == {}

    def test_delta_request_con_valores(self):
        from scripts.delta_sync import DeltaRequest
        req = DeltaRequest("t1", 100.0, {"evo_1": 5})
        assert req.ultimo_timestamp == 100.0
        assert req.ultimas_versiones == {"evo_1": 5}

    def test_delta_response_init(self):
        from scripts.delta_sync import DeltaResponse
        resp = DeltaResponse()
        assert resp.cambios == {}
        assert resp.eliminados == {}
        assert resp.timestamp_servidor > 0


class TestDeltaClient:
    """Tests para el cliente movil DeltaClient."""

    def test_get_cached_version_defaults(self):
        from scripts.delta_sync import DeltaClient
        ts, versiones = DeltaClient.get_cached_version()
        assert ts == 0.0
        assert versiones == {}

    def test_apply_changes_vacio(self):
        from scripts.delta_sync import DeltaClient
        import msgpack
        payload = msgpack.packb({"cambios": {}, "eliminados": {}, "timestamp": time.time()})
        total = DeltaClient.apply_changes(payload)
        assert total == 0

    def test_apply_changes_con_registros(self):
        from scripts.delta_sync import DeltaClient
        import msgpack
        payload = msgpack.packb({
            "cambios": {"evoluciones": [{"id": "1"}, {"id": "2"}]},
            "eliminados": {},
            "timestamp": time.time(),
        })
        total = DeltaClient.apply_changes(payload)
        assert total == 2


class TestSyncEndpoint:
    """Tests de integracion para el endpoint POST /sync/delta."""

    def test_sync_delta_respuesta_msgpack(self):
        from scripts.delta_sync import sync_delta
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.close = AsyncMock()
        with patch("asyncpg.connect", return_value=mock_conn):
            result = asyncio.run(sync_delta("t1", 0.0, None))

        import msgpack
        data = msgpack.unpackb(result, raw=False)
        assert "cambios" in data
        assert "eliminados" in data
        assert "timestamp" in data
        assert data["cambios"] == {}
        assert data["eliminados"] == {}

    def test_sync_delta_con_cambios(self):
        from scripts.delta_sync import sync_delta

        fake_row = {
            "id": "1", "tenant_id": "t1", "diagnostico": "prueba",
            "created_at": "2026-05-31T10:00:00", "updated_at": "2026-05-31T10:00:00",
        }

        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[fake_row])
        mock_conn.close = AsyncMock()
        with patch("asyncpg.connect", return_value=mock_conn):
            result = asyncio.run(sync_delta("t1", 0.0, None))

        import msgpack
        data = msgpack.unpackb(result, raw=False)
        assert "evoluciones" in data["cambios"]

    def test_sync_delta_cierra_conexion_siempre(self):
        from scripts.delta_sync import sync_delta
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(side_effect=Exception("db_error"))
        mock_conn.close = AsyncMock()
        with patch("asyncpg.connect", return_value=mock_conn):
            with pytest.raises(Exception):
                asyncio.run(sync_delta("t1", 0.0, None))

    def test_sync_delta_ultimo_timestamp_filtra(self):
        from scripts.delta_sync import sync_delta
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.close = AsyncMock()
        with patch("asyncpg.connect", return_value=mock_conn):
            asyncio.run(sync_delta("t1", 500.0, {"evo_1": 2}))

        for call in mock_conn.fetch.await_args_list:
            sql = call.args[0]
            assert "tenant_id" in sql
