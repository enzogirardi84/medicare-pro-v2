"""Tests para core.data_lineage_engine — Trazabilidad end-to-end."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch


class TestLineageNode:
    def test_node_defaults(self):
        from core.data_lineage_engine import LineageNode
        node = LineageNode(id="n1", node_type="device", label="Test Device")
        assert node.id == "n1"
        assert node.node_type == "device"
        assert node.metadata == {}

    def test_to_dict(self):
        from core.data_lineage_engine import LineageNode
        node = LineageNode(id="n1", node_type="device", label="D1", metadata={"key": "val"})
        d = node.to_dict()
        assert d["id"] == "n1"
        assert d["metadata"]["key"] == "val"


class TestLineageEdge:
    def test_edge_defaults(self):
        from core.data_lineage_engine import LineageEdge
        edge = LineageEdge(source_id="s1", target_id="t1", relation="generated_by")
        assert edge.source_id == "s1"
        assert edge.target_id == "t1"

    def test_to_dict(self):
        from core.data_lineage_engine import LineageEdge
        edge = LineageEdge(source_id="s1", target_id="t1", relation="r")
        d = edge.to_dict()
        assert d["relation"] == "r"


class TestLineageGraph:
    def test_empty_graph(self):
        from core.data_lineage_engine import LineageGraph
        g = LineageGraph()
        assert g.to_dict()["nodes"] == []
        assert g.to_dict()["edges"] == []

    def test_add_node_and_edge(self):
        from core.data_lineage_engine import LineageGraph, LineageNode, LineageEdge
        g = LineageGraph()
        g.add_node(LineageNode(id="n1", node_type="device", label="D1"))
        g.add_node(LineageNode(id="n2", node_type="event_store", label="E1"))
        g.add_edge(LineageEdge(source_id="n1", target_id="n2", relation="generated_by"))
        assert len(g.nodes) == 2
        assert len(g.edges) == 1

    def test_to_dot_contains_nodes(self):
        from core.data_lineage_engine import LineageGraph, LineageNode, LineageEdge
        g = LineageGraph()
        g.add_node(LineageNode(id="d1", node_type="device", label="Dev-1"))
        g.add_node(LineageNode(id="e1", node_type="event_store", label="Evt-1"))
        g.add_edge(LineageEdge(source_id="d1", target_id="e1", relation="generated_by"))
        dot = g.to_dot()
        assert "digraph Lineage" in dot
        assert "d1" in dot
        assert "e1" in dot
        assert "generated_by" in dot


class TestDataLineageEngine:
    def test_import(self):
        from core.data_lineage_engine import DataLineageEngine, create_webhook_lineage_event
        assert DataLineageEngine is not None

    def test_trace_alert_empty(self):
        from core.data_lineage_engine import DataLineageEngine, LineageNodeType
        engine = DataLineageEngine()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchrow = AsyncMock(return_value=None)
        engine._conn = mock_conn
        graph = asyncio.run(engine.trace_alert("alert-unknown"))
        assert len(graph.nodes) >= 1  # al menos el nodo alerta raiz
        # Verificar que el nodo es de tipo ALERT
        alert_nodes = [n for n in graph.nodes.values() if n.node_type == LineageNodeType.ALERT]
        assert len(alert_nodes) == 1

    def test_trace_alert_with_events(self):
        from core.data_lineage_engine import DataLineageEngine
        engine = DataLineageEngine()
        mock_conn = MagicMock()

        fake_event = {
            "id": "evt-1",
            "aggregate_type": "alerta",
            "aggregate_id": "alert-1",
            "event_type": "AlertaCreada",
            "event_version": 1,
            "tenant_id": "t1",
            "actor_id": "prof-1",
            "checksum": "abc123",
            "created_at": None,
            "prev_event_id": None,
            "payload": '{"alert_id": "alert-1", "device_id": "dev-1"}',
        }
        mock_conn.fetch = AsyncMock(return_value=[fake_event])
        mock_conn.fetchrow = AsyncMock(return_value=None)
        engine._conn = mock_conn

        graph = asyncio.run(engine.trace_alert("alert-1"))
        assert len(graph.nodes) >= 1
        assert len(graph.edges) >= 0

    def test_trace_evolution(self):
        from core.data_lineage_engine import DataLineageEngine
        engine = DataLineageEngine()

        with patch("core.clinical_event_store.ClinicalEventStore.replay",
                   return_value={"state": {"d": "test"}, "version": 3, "checksum": "abc"}):
            graph = asyncio.run(engine.trace_evolution("evo-1"))
            assert len(graph.nodes) >= 2
            # Verificar que hay nodo snapshot
            snapshot_nodes = [n for n in graph.nodes.values() if n.node_type == "snapshot"]
            assert len(snapshot_nodes) >= 1

    def test_trace_device(self):
        from core.data_lineage_engine import DataLineageEngine
        engine = DataLineageEngine()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[
            {"id": "e1", "aggregate_type": "alerta", "aggregate_id": "a1",
             "event_type": "AlertaCreada", "created_at": None},
        ])
        engine._conn = mock_conn
        graph = asyncio.run(engine.trace_device("dev-1"))
        assert len(graph.nodes) >= 2
        assert len(graph.edges) >= 1

    def test_trace_webhook(self):
        from core.data_lineage_engine import DataLineageEngine
        engine = DataLineageEngine()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value={
            "id": "e1", "aggregate_type": "alerta", "aggregate_id": "a1",
            "event_type": "AlertaCreada", "created_at": None,
        })
        engine._conn = mock_conn
        graph = asyncio.run(engine.trace_webhook("wh-1"))
        assert len(graph.nodes) >= 1

    def test_create_webhook_lineage_event(self):
        from core.data_lineage_engine import create_webhook_lineage_event
        ev = create_webhook_lineage_event("alert-1", "t1", "checkin.realizado", "200")
        assert ev["aggregate_type"] == "webhook_dispatch"
        assert ev["aggregate_id"] == "alert-1"
        assert "200" in ev["payload"]

    def test_close(self):
        from core.data_lineage_engine import DataLineageEngine
        engine = DataLineageEngine()
        mock_conn = MagicMock()
        mock_conn.close = AsyncMock()
        engine._conn = mock_conn
        asyncio.run(engine.close())
        mock_conn.close.assert_awaited_once()
