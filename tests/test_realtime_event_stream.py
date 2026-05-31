"""Tests para core.realtime_event_stream — WebSockets + Redis Pub/Sub."""
from __future__ import annotations

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestRealtimeMessage:
    def test_message_defaults(self):
        from core.realtime_event_stream import RealtimeMessage
        msg = RealtimeMessage(event_type="test", tenant_id="t1", professional_id="p1")
        assert msg.event_type == "test"
        assert msg.priority == 0
        assert msg.ttl_seconds == 300
        assert msg.id is not None

    def test_to_json_contains_fields(self):
        from core.realtime_event_stream import RealtimeMessage
        msg = RealtimeMessage(event_type="alerta.news2", tenant_id="t1",
                               professional_id="p1", payload={"score": 7})
        j = msg.to_json()
        d = json.loads(j)
        assert d["event_type"] == "alerta.news2"
        assert d["payload"]["score"] == 7

    def test_from_json_roundtrip(self):
        from core.realtime_event_stream import RealtimeMessage
        original = RealtimeMessage(event_type="ruta.cambio", tenant_id="t1",
                                    professional_id="p1", payload={"dir": "nueva"},
                                    priority=1, ttl_seconds=600)
        restored = RealtimeMessage.from_json(original.to_json())
        assert restored.event_type == "ruta.cambio"
        assert restored.priority == 1
        assert restored.ttl_seconds == 600


class TestWebSocketManager:
    def test_connect_creates_queue(self):
        from core.realtime_event_stream import WebSocketManager
        mgr = WebSocketManager()
        q = asyncio.run(mgr.connect("t1", "p1"))
        assert q is not None
        assert mgr.get_connected_count()["connections"] == 1

    def test_disconnect_removes_queue(self):
        from core.realtime_event_stream import WebSocketManager
        mgr = WebSocketManager()
        q = asyncio.run(mgr.connect("t1", "p1"))
        asyncio.run(mgr.disconnect("t1", "p1", q))
        assert mgr.get_connected_count()["connections"] == 0

    def test_send_to_professional(self):
        from core.realtime_event_stream import WebSocketManager, RealtimeMessage
        mgr = WebSocketManager()
        q = asyncio.run(mgr.connect("t1", "p1"))
        msg = RealtimeMessage(event_type="test", tenant_id="t1", professional_id="p1")
        delivered = asyncio.run(mgr.send_to_professional("t1", "p1", msg))
        assert delivered == 1
        # Verificar que el mensaje llego a la cola
        received = asyncio.run(asyncio.wait_for(q.get(), timeout=1.0))
        assert received.event_type == "test"

    def test_send_to_unknown_professional(self):
        from core.realtime_event_stream import WebSocketManager, RealtimeMessage
        mgr = WebSocketManager()
        msg = RealtimeMessage(event_type="test", tenant_id="t1", professional_id="unknown")
        delivered = asyncio.run(mgr.send_to_professional("t1", "unknown", msg))
        assert delivered == 0

    def test_send_to_tenant_broadcast(self):
        from core.realtime_event_stream import WebSocketManager, RealtimeMessage
        mgr = WebSocketManager()
        asyncio.run(mgr.connect("t1", "p1"))
        asyncio.run(mgr.connect("t1", "p2"))
        msg = RealtimeMessage(event_type="broadcast", tenant_id="t1", professional_id="")
        total = asyncio.run(mgr.send_to_tenant("t1", msg))
        assert total == 2

    def test_get_connected_count_empty(self):
        from core.realtime_event_stream import WebSocketManager
        mgr = WebSocketManager()
        stats = mgr.get_connected_count()
        assert stats["connections"] == 0
        assert stats["tenants"] == 0


class TestRedisPubSubBridge:
    def test_publish_no_redis(self):
        from core.realtime_event_stream import RedisPubSubBridge, WebSocketManager, RealtimeMessage
        ws = WebSocketManager()
        bridge = RedisPubSubBridge(ws)
        msg = RealtimeMessage(event_type="test", tenant_id="t1", professional_id="p1")
        result = asyncio.run(bridge.publish("t1", msg))
        assert result is False

    def test_subscribe(self):
        from core.realtime_event_stream import RedisPubSubBridge, WebSocketManager
        ws = WebSocketManager()
        bridge = RedisPubSubBridge(ws)
        asyncio.run(bridge.subscribe("t1"))
        assert len(bridge._channels) == 1

    def test_close(self):
        from core.realtime_event_stream import RedisPubSubBridge, WebSocketManager
        ws = WebSocketManager()
        bridge = RedisPubSubBridge(ws)
        asyncio.run(bridge.subscribe("t1"))
        asyncio.run(bridge.close())


class TestCreateMessages:
    def test_create_alert_news2(self):
        from core.realtime_event_stream import create_alert_news2
        msg = create_alert_news2("t1", "p1", "pac-123", 8, "CRITICO")
        assert msg.event_type == "alerta.news2"
        assert msg.priority == 2
        assert msg.payload["score"] == 8

    def test_create_alert_news2_urgente(self):
        from core.realtime_event_stream import create_alert_news2
        msg = create_alert_news2("t1", "p1", "pac-123", 4, "URGENTE")
        assert msg.priority == 1

    def test_create_ruta_cambio(self):
        from core.realtime_event_stream import create_ruta_cambio
        msg = create_ruta_cambio("t1", "p1", "emergencia", "Av. Corrientes 1234")
        assert msg.event_type == "ruta.cambio"
        assert msg.payload["motivo"] == "emergencia"

    def test_create_turno_cancelado(self):
        from core.realtime_event_stream import create_turno_cancelado
        msg = create_turno_cancelado("t1", "p1", "turno-456", "Juan Perez")
        assert msg.event_type == "turno.cancelado"
        assert msg.payload["paciente"] == "Juan Perez"


class TestFastAPIWSEndpoint:
    def test_ws_endpoint_code_importable(self):
        from core.realtime_event_stream import FASTAPI_WS_ENDPOINT
        assert "WebSocketManager" in FASTAPI_WS_ENDPOINT
