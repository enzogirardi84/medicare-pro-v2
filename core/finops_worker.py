"""Recolector de metricas de infraestructura por tenant (FinOps).
Cruza filas en clinical_event_store, bytes transferidos por webhooks,
y almacenamiento PostGIS para calcular costo operativo estimado.
Expone metricas en formato Prometheus.
"""
from __future__ import annotations

import json
import os
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE COSTO
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TenantCostMetrics:
    """Metricas de costo operativo por tenant."""
    tenant_id: str
    event_count: int = 0
    webhook_bytes_sent: int = 0
    webhook_count: int = 0
    storage_bytes_estimate: int = 0
    read_replica_queries: int = 0
    computed_at: float = 0.0

    @property
    def estimated_cost_usd(self) -> float:
        """Costo estimado en USD usando pricing estandar.

        - Event Store: $0.10 por 1000 filas (RDS IO)
        - Webhooks: $0.05 por 1000 requests + $0.08/GB transfer
        - Storage: $0.023/GB/mes (EBS gp3)
        - Read replicas: $0.01 por 1000 queries
        """
        cost = 0.0
        cost += (self.event_count / 1000) * 0.10
        cost += (self.webhook_count / 1000) * 0.05
        cost += (self.webhook_bytes_sent / (1024 ** 3)) * 0.08
        cost += (self.storage_bytes_estimate / (1024 ** 3)) * 0.023
        cost += (self.read_replica_queries / 1000) * 0.01
        return round(cost, 4)


# ═══════════════════════════════════════════════════════════════════
# 2. RECOLECTOR DE METRICAS
# ═══════════════════════════════════════════════════════════════════

class FinOpsCollector:
    """Recolector de metricas de infraestructura por tenant.

    Uso:
        collector = FinOpsCollector()
        metrics = await collector.collect_all()
        for m in metrics:
            print(m.tenant_id, m.estimated_cost_usd)
    """

    def __init__(self):
        self._conn = None

    async def _get_conn(self):
        if self._conn is None:
            import asyncpg
            self._conn = await asyncpg.connect("postgresql://localhost:5432/medicare")
        return self._conn

    async def collect_all(self) -> list[TenantCostMetrics]:
        """Recolecta metricas de todos los tenants."""
        conn = await self._get_conn()
        metrics_map: dict[str, TenantCostMetrics] = {}

        # 1. Conteo de eventos por tenant
        rows = await conn.fetch("""
            SELECT tenant_id, COUNT(*) as cnt
            FROM clinical_event_store
            GROUP BY tenant_id
        """)
        for r in rows:
            tid = str(r["tenant_id"])
            metrics_map.setdefault(tid, TenantCostMetrics(tenant_id=tid))
            metrics_map[tid].event_count = r["cnt"]

        # 2. Webhooks: bytes enviados ultimas 24h
        webhook_rows = await conn.fetch("""
            SELECT
                (payload->>'tenant_id') as tenant_id,
                COUNT(*) as wh_count,
                COALESCE(SUM(
                    (payload->>'original_size')::BIGINT
                ), 0) as total_bytes
            FROM clinical_event_store
            WHERE aggregate_type = 'webhook_dispatch'
              AND created_at > NOW() - INTERVAL '24 hours'
            GROUP BY (payload->>'tenant_id')
        """)
        for r in webhook_rows:
            tid = r["tenant_id"]
            if tid:
                metrics_map.setdefault(tid, TenantCostMetrics(tenant_id=tid))
                metrics_map[tid].webhook_count = r["wh_count"]
                metrics_map[tid].webhook_bytes_sent = r["total_bytes"]

        # 3. Storage estimado por tenant (suma de tamanos de payload)
        storage_rows = await conn.fetch("""
            SELECT tenant_id,
                   SUM(pg_column_size(payload)) as total_payload_bytes,
                   COUNT(*) as total_events
            FROM clinical_event_store
            GROUP BY tenant_id
        """)
        for r in storage_rows:
            tid = str(r["tenant_id"])
            metrics_map.setdefault(tid, TenantCostMetrics(tenant_id=tid))
            metrics_map[tid].storage_bytes_estimate = r["total_payload_bytes"] or 0

        # Timestamp
        now = time.time()
        for m in metrics_map.values():
            m.computed_at = now

        log_event("finops", f"collected:{len(metrics_map)} tenants")
        return list(metrics_map.values())

    async def collect_tenant(self, tenant_id: str) -> Optional[TenantCostMetrics]:
        """Recolecta metricas de un tenant especifico."""
        all_metrics = await self.collect_all()
        for m in all_metrics:
            if m.tenant_id == tenant_id:
                return m
        return None

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


# ═══════════════════════════════════════════════════════════════════
# 3. EXPOSITOR PROMETHEUS
# ═══════════════════════════════════════════════════════════════════

class PrometheusExporter:
    """Exporta metricas FinOps en formato Prometheus text.

    Uso:
        exporter = PrometheusExporter()
        metrics = await collector.collect_all()
        prom_text = exporter.render(metrics)
        # Serve en /metrics para que Prometheus scrapee
    """

    METRIC_PREFIX = "medicare_finops"

    @staticmethod
    def render(metrics: list[TenantCostMetrics]) -> str:
        """Genera texto en formato Prometheus exposition format."""
        lines: list[str] = []
        ts = int(time.time())

        # HELP y TYPE
        lines.append(f"# HELP {PrometheusExporter.METRIC_PREFIX}_estimated_cost_usd Costo operativo estimado por tenant")
        lines.append(f"# TYPE {PrometheusExporter.METRIC_PREFIX}_estimated_cost_usd gauge")
        for m in metrics:
            lines.append(
                f'{PrometheusExporter.METRIC_PREFIX}_estimated_cost_usd{{tenant="{m.tenant_id}"}} {m.estimated_cost_usd} {ts}'
            )

        lines.append(f"# HELP {PrometheusExporter.METRIC_PREFIX}_event_count Eventos en event store por tenant")
        lines.append(f"# TYPE {PrometheusExporter.METRIC_PREFIX}_event_count gauge")
        for m in metrics:
            lines.append(
                f'{PrometheusExporter.METRIC_PREFIX}_event_count{{tenant="{m.tenant_id}"}} {m.event_count} {ts}'
            )

        lines.append(f"# HELP {PrometheusExporter.METRIC_PREFIX}_webhook_bytes_sent Bytes enviados por webhooks (24h)")
        lines.append(f"# TYPE {PrometheusExporter.METRIC_PREFIX}_webhook_bytes_sent gauge")
        for m in metrics:
            lines.append(
                f'{PrometheusExporter.METRIC_PREFIX}_webhook_bytes_sent{{tenant="{m.tenant_id}"}} {m.webhook_bytes_sent} {ts}'
            )

        lines.append(f"# HELP {PrometheusExporter.METRIC_PREFIX}_storage_bytes_estimate Almacenamiento estimado en event store")
        lines.append(f"# TYPE {PrometheusExporter.METRIC_PREFIX}_storage_bytes_estimate gauge")
        for m in metrics:
            lines.append(
                f'{PrometheusExporter.METRIC_PREFIX}_storage_bytes_estimate{{tenant="{m.tenant_id}"}} {m.storage_bytes_estimate} {ts}'
            )

        lines.append(f"# HELP {PrometheusExporter.METRIC_PREFIX}_webhook_count Webhooks enviados (24h)")
        lines.append(f"# TYPE {PrometheusExporter.METRIC_PREFIX}_webhook_count gauge")
        for m in metrics:
            lines.append(
                f'{PrometheusExporter.METRIC_PREFIX}_webhook_count{{tenant="{m.tenant_id}"}} {m.webhook_count} {ts}'
            )

        # Alerta: tenant comercialmente inviable (> $100/mes estimado)
        lines.append(f"# HELP {PrometheusExporter.METRIC_PREFIX}_unprofitable_tenant Alerta: tenant con costo > $100/mes")
        lines.append(f"# TYPE {PrometheusExporter.METRIC_PREFIX}_unprofitable_tenant gauge")
        for m in metrics:
            unprofitable = 1 if m.estimated_cost_usd > 100.0 else 0
            lines.append(
                f'{PrometheusExporter.METRIC_PREFIX}_unprofitable_tenant{{tenant="{m.tenant_id}"}} {unprofitable} {ts}'
            )

        return "\n".join(lines) + "\n"


# ═══════════════════════════════════════════════════════════════════
# 4. REPORTE POR TENANT (para dashboard interno)
# ═══════════════════════════════════════════════════════════════════

class FinOpsReporter:
    """Genera reportes de costo operativo por tenant."""

    def __init__(self, collector: Optional[FinOpsCollector] = None):
        self._collector = collector or FinOpsCollector()

    async def generate_report(self) -> dict:
        """Genera reporte completo de todos los tenants."""
        metrics = await self._collector.collect_all()
        metrics.sort(key=lambda m: m.estimated_cost_usd, reverse=True)

        total_cost = sum(m.estimated_cost_usd for m in metrics)
        total_events = sum(m.event_count for m in metrics)
        total_webhooks = sum(m.webhook_count for m in metrics)

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_tenants": len(metrics),
            "total_estimated_cost_usd": round(total_cost, 2),
            "total_events": total_events,
            "total_webhooks_24h": total_webhooks,
            "tenants": [
                {
                    "tenant_id": m.tenant_id,
                    "estimated_cost_usd": m.estimated_cost_usd,
                    "event_count": m.event_count,
                    "webhook_count": m.webhook_count,
                    "webhook_bytes_sent": m.webhook_bytes_sent,
                    "storage_bytes_estimate": m.storage_bytes_estimate,
                    "unprofitable": m.estimated_cost_usd > 100.0,
                }
                for m in metrics
            ],
            "alertas": self._generate_alerts(metrics),
        }

    @staticmethod
    def _generate_alerts(metrics: list[TenantCostMetrics]) -> list[dict]:
        alerts = []
        for m in metrics:
            if m.estimated_cost_usd > 100.0:
                alerts.append({
                    "tenant_id": m.tenant_id,
                    "severity": "warning",
                    "message": f"Costo mensual estimado de ${m.estimated_cost_usd:.2f} supera el umbral de $100",
                    "estimated_cost_usd": m.estimated_cost_usd,
                })
            elif m.event_count > 1_000_000:
                alerts.append({
                    "tenant_id": m.tenant_id,
                    "severity": "info",
                    "message": f"Alto volumen de eventos: {m.event_count:,}",
                })
        return alerts

    async def close(self):
        await self._collector.close()


__all__ = [
    "FinOpsCollector",
    "FinOpsReporter",
    "PrometheusExporter",
    "TenantCostMetrics",
]
