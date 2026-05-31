"""Tests para core.finops_worker — Costos por tenant + Prometheus."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestTenantCostMetrics:
    def test_cost_zero_for_empty(self):
        from core.finops_worker import TenantCostMetrics
        m = TenantCostMetrics(tenant_id="t1")
        assert m.estimated_cost_usd == 0.0

    def test_cost_calculation(self):
        from core.finops_worker import TenantCostMetrics
        m = TenantCostMetrics(
            tenant_id="t1",
            event_count=10_000,
            webhook_count=5_000,
            webhook_bytes_sent=500 * 1024 * 1024,  # 500 MB
            storage_bytes_estimate=2 * 1024 ** 3,   # 2 GB
            read_replica_queries=20_000,
        )
        assert m.estimated_cost_usd > 0
        # event: 10000/1000*0.10 = 1.0
        # webhook: 5000/1000*0.05 = 0.25
        # transfer: 0.5GB*0.08 = 0.04
        # storage: 2GB*0.023 = 0.046
        # read: 20000/1000*0.01 = 0.2
        # total ~ 1.536
        assert 1.5 < m.estimated_cost_usd < 1.6


class TestFinOpsCollector:
    def test_collect_all_empty(self):
        from core.finops_worker import FinOpsCollector
        collector = FinOpsCollector()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(side_effect=[
            [],  # event_count query
            [],  # webhook query
            [],  # storage query
        ])
        collector._conn = mock_conn
        metrics = asyncio.run(collector.collect_all())
        assert metrics == []

    def test_collect_all_with_data(self):
        from core.finops_worker import FinOpsCollector
        collector = FinOpsCollector()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(side_effect=[
            [{"tenant_id": "t1", "cnt": 1000}],
            [{"tenant_id": "t1", "wh_count": 50, "total_bytes": 50000}],
            [{"tenant_id": "t1", "total_payload_bytes": 200000, "total_events": 1000}],
        ])
        collector._conn = mock_conn
        metrics = asyncio.run(collector.collect_all())
        assert len(metrics) == 1
        assert metrics[0].tenant_id == "t1"
        assert metrics[0].event_count == 1000
        assert metrics[0].webhook_count == 50

    def test_collect_tenant_not_found(self):
        from core.finops_worker import FinOpsCollector
        collector = FinOpsCollector()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(side_effect=[
            [{"tenant_id": "t2", "cnt": 500}],
            [], [],  # no webhooks, no storage for t1
        ])
        collector._conn = mock_conn
        result = asyncio.run(collector.collect_tenant("t1"))
        assert result is None or result.tenant_id == "t1" and result.event_count == 0


class TestPrometheusExporter:
    def test_render_empty(self):
        from core.finops_worker import PrometheusExporter, TenantCostMetrics
        text = PrometheusExporter.render([])
        assert text.startswith("# HELP")
        assert text.endswith("\n")

    def test_render_with_metrics(self):
        from core.finops_worker import PrometheusExporter, TenantCostMetrics
        metrics = [
            TenantCostMetrics(tenant_id="t1", event_count=1000, webhook_count=50),
            TenantCostMetrics(tenant_id="t2", event_count=5000, webhook_bytes_sent=100000),
        ]
        text = PrometheusExporter.render(metrics)
        assert "t1" in text
        assert "t2" in text
        assert "medicare_finops_estimated_cost_usd" in text
        assert "medicare_finops_event_count" in text
        assert "medicare_finops_unprofitable_tenant" in text

    def test_unprofitable_flag(self):
        from core.finops_worker import PrometheusExporter, TenantCostMetrics
        cheap = TenantCostMetrics(tenant_id="t1", event_count=100)
        expensive = TenantCostMetrics(tenant_id="t2", event_count=2_000_000)
        text = PrometheusExporter.render([cheap, expensive])
        assert 'medicare_finops_unprofitable_tenant{tenant="t1"} 0' in text
        expensive_line = [l for l in text.split("\n") if 'tenant="t2"' in l and "unprofitable" in l]
        assert any(" 1 " in l for l in expensive_line) or any(l.endswith(" 1") for l in expensive_line)


class TestFinOpsReporter:
    def test_generate_report(self):
        from core.finops_worker import FinOpsReporter, FinOpsCollector, TenantCostMetrics
        collector = MagicMock()
        collector.collect_all = AsyncMock(return_value=[
            TenantCostMetrics(tenant_id="t1", event_count=100, webhook_count=5),
        ])
        reporter = FinOpsReporter(collector=collector)
        report = asyncio.run(reporter.generate_report())
        assert report["total_tenants"] == 1
        assert report["total_events"] == 100

    def test_generate_alerts(self):
        from core.finops_worker import FinOpsReporter, FinOpsCollector, TenantCostMetrics
        metrics = [
            TenantCostMetrics(tenant_id="expensive", event_count=5_000_000),
            TenantCostMetrics(tenant_id="cheap", event_count=100),
        ]
        alerts = FinOpsReporter._generate_alerts(metrics)
        assert len(alerts) >= 1

    def test_close(self):
        from core.finops_worker import FinOpsReporter, FinOpsCollector
        collector = MagicMock()
        collector.close = AsyncMock()
        reporter = FinOpsReporter(collector=collector)
        asyncio.run(reporter.close())
