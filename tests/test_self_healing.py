"""Tests para scripts.self_healing_engine — Self-Healing Engine."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestSelfHealingEngine:
    """Tests unitarios para SelfHealingEngine con alertas simuladas."""

    def test_import(self):
        from scripts.self_healing_engine import SelfHealingEngine, RemediationAction
        assert SelfHealingEngine is not None
        assert RemediationAction is not None

    def test_degradar_tenant_redis_error(self):
        from scripts.self_healing_engine import SelfHealingEngine
        engine = SelfHealingEngine()
        engine._get_redis = AsyncMock(return_value=None)
        result = asyncio.run(engine.degradar_tenant("test_tenant", "abuso"))
        assert result is True

    def test_aislar_registro_error_conexion(self):
        from scripts.self_healing_engine import SelfHealingEngine
        engine = SelfHealingEngine()
        with patch("asyncpg.connect", side_effect=Exception("conn_error")):
            with pytest.raises(Exception, match="conn_error"):
                asyncio.run(engine.aislar_registro("evoluciones", "123", "tenant_1"))

    def test_procesar_alerta_integrity_failure(self):
        from scripts.self_healing_engine import SelfHealingEngine
        engine = SelfHealingEngine()
        engine.aislar_registro = AsyncMock(return_value=True)
        alerta = {
            "alertname": "IntegrityFailure",
            "labels": {"tenant": "t1", "registro_id": "r123", "tabla": "evoluciones"},
        }
        action = asyncio.run(engine.procesar_alerta(alerta))
        assert action is not None
        assert action.tipo == "aislar_registro"
        assert action.target == "r123"

    def test_procesar_alerta_rate_limit(self):
        from scripts.self_healing_engine import SelfHealingEngine
        engine = SelfHealingEngine()
        engine.degradar_tenant = AsyncMock(return_value=True)
        alerta = {
            "alertname": "RateLimit",
            "labels": {"tenant": "t1"},
        }
        action = asyncio.run(engine.procesar_alerta(alerta))
        assert action is not None
        assert action.tipo == "degradar_tenant"
        assert action.target == "t1"

    def test_procesar_alerta_optimistic_lock(self):
        from scripts.self_healing_engine import SelfHealingEngine
        engine = SelfHealingEngine()
        alerta = {
            "alertname": "OptimisticLock",
            "labels": {"tenant": "t1"},
        }
        action = asyncio.run(engine.procesar_alerta(alerta))
        assert action is not None
        assert action.tipo == "reintentar"

    def test_procesar_alerta_desconocida(self):
        from scripts.self_healing_engine import SelfHealingEngine
        engine = SelfHealingEngine()
        alerta = {"alertname": "UnknownAlert", "labels": {}}
        action = asyncio.run(engine.procesar_alerta(alerta))
        assert action is None

    def test_aislar_registro_success(self):
        from scripts.self_healing_engine import SelfHealingEngine
        mock_conn = MagicMock()
        mock_conn.execute = AsyncMock()
        mock_conn.close = AsyncMock()
        with patch("asyncpg.connect", return_value=mock_conn):
            engine = SelfHealingEngine()
            result = asyncio.run(engine.aislar_registro("evoluciones", "r123", "t1"))
        assert result is True

    def test_restaurar_tenant(self):
        from scripts.self_healing_engine import SelfHealingEngine
        mock_redis = AsyncMock()
        engine = SelfHealingEngine()
        engine._get_redis = AsyncMock(return_value=mock_redis)
        result = asyncio.run(engine.restaurar_tenant("t1"))
        assert result is True
        mock_redis.delete.assert_awaited_once_with("rate_limit:t1")

    def test_degradar_tenant_redis_sets_fields(self):
        from scripts.self_healing_engine import SelfHealingEngine
        mock_redis = AsyncMock()
        engine = SelfHealingEngine()
        engine._get_redis = AsyncMock(return_value=mock_redis)
        result = asyncio.run(engine.degradar_tenant("t1", "test"))
        assert result is True
        mock_redis.hset.assert_awaited_once()
        mock_redis.expire.assert_awaited_once_with("rate_limit:t1", 1800)

    def test_loop_escucha_no_crash_sin_redis(self):
        from scripts.self_healing_engine import SelfHealingEngine
        engine = SelfHealingEngine()
        engine._get_redis = AsyncMock(return_value=None)
        engine.loop_escucha = AsyncMock()
        result = asyncio.run(engine.loop_escucha())
        engine.loop_escucha.assert_awaited_once()
