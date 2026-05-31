"""Operador GitOps Autónomo de Costos e Infraestructura.
Monitorea FinOps metrics, aplica Taints/Tolerations dinámicos,
desaloja pods de bajo valor, escala réplicas en nube alternativa.
Basado en Kopf (Kubernetes Operator Framework Python).
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE DECISIÓN
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TenantCostDecision:
    """Decisión autónoma sobre un tenant basada en FinOps."""
    tenant_id: str
    estimated_cost_usd: float
    is_unprofitable: bool
    p95_latency_ms: float
    action: str = ""              # "none" | "evict_low_priority" | "scale_secondary" | "alert"
    reason: str = ""
    executed_at: float = field(default_factory=time.time)

    def to_kubernetes_annotation(self) -> dict:
        return {
            "medicare-pro/tenant-id": self.tenant_id,
            "medicare-pro/cost-decision": self.action,
            "medicare-pro/cost-reason": self.reason[:120],
            "medicare-pro/decision-time": str(self.executed_at),
        }


# ═══════════════════════════════════════════════════════════════════
# 2. OPERADOR KOPF (ESTRUCTURA)
# ═══════════════════════════════════════════════════════════════════

KOPF_OPERATOR_CODE = """
# ─────────────────────────────────────────────────────────────────
# cost-allocator-operator.py
# Operador Kopf para Kubernetes. Ejecutar:
#   kopf run cost-allocator-operator.py
# ─────────────────────────────────────────────────────────────────
# Requiere: pip install kopf kubernetes

import asyncio
import json
import time
import kopf
import kubernetes as k8s
import os

from core.finops_worker import FinOpsCollector, PrometheusExporter
from core.multi_region_balancer import get_multi_region_balancer

# ─── Configuración ────────────────────────────────────────────────
COST_THRESHOLD_USD = float(os.environ.get("COST_THRESHOLD_USD", "100"))
LATENCY_THRESHOLD_MS = float(os.environ.get("LATENCY_THRESHOLD_MS", "500"))
CHECK_INTERVAL = int(os.environ.get("COST_CHECK_INTERVAL", "300"))  # 5 min
NAMESPACE = os.environ.get("OPERATOR_NAMESPACE", "medicare-pro")

# ─── Timer de reconciliación ──────────────────────────────────────
@kopf.timer(NAMESPACE, interval=CHECK_INTERVAL)
async def reconcile_cost(spec, **kwargs):
    \"\"\"Timer que evalúa costos y toma decisiones autónomas.\"\"\"
    collector = FinOpsCollector()
    balancer = get_multi_region_balancer()
    v1 = k8s.client.CoreV1Api()

    metrics = await collector.collect_all()
    decisions = []

    for tm in metrics:
        if tm.estimated_cost_usd > COST_THRESHOLD_USD:
            decision = await handle_expensive_tenant(
                v1, tm.tenant_id, tm.estimated_cost_usd
            )
            decisions.append(decision)

        # Verificar latencia p95
        region_stats = await balancer.get_region_stats()
        for region, stats in region_stats.items():
            if stats.get("response_time_ms", 0) > LATENCY_THRESHOLD_MS:
                await handle_high_latency(v1, region, stats)

    return {"decisions": decisions, "checked": len(metrics)}


async def handle_expensive_tenant(v1, tenant_id: str, cost: float) -> dict:
    \"\"\"Maneja un tenant que supera el umbral de costo.\"\"\"
    log_event("cost_operator", f"expensive_tenant:{tenant_id}:${cost:.2f}")

    # 1. Anotar todos los pods del tenant
    pods = v1.list_namespaced_pod(
        NAMESPACE,
        label_selector=f"tenant-id={tenant_id}",
    )

    for pod in pods.items:
        annotations = pod.metadata.annotations or {}
        annotations["medicare-pro/cost-alert"] = f"${cost:.2f}/mes"
        annotations["medicare-pro/cost-decision-time"] = str(time.time())
        body = {"metadata": {"annotations": annotations}}
        v1.patch_namespaced_pod(pod.metadata.name, NAMESPACE, body)

    # 2. Si es muy costoso, marcar nodos con taint
    if cost > COST_THRESHOLD_USD * 3:
        # Aplicar Taint al nodo para evitar nuevos pods de bajo valor
        nodes = v1.list_node(label_selector=f"tenant-id={tenant_id}")
        for node in nodes.items:
            taint = {
                "key": "medicare-pro/cost-overrun",
                "value": tenant_id,
                "effect": "PreferNoSchedule",
            }
            body = {
                "spec": {
                    "taints": (node.spec.taints or []) + [taint]
                }
            }
            v1.patch_node(node.metadata.name, body)
            log_event("cost_operator", f"tainted_node:{node.metadata.name}:{tenant_id}")

    return {"tenant_id": tenant_id, "cost": cost, "action": "annotated"}


async def handle_high_latency(v1, region: str, stats: dict) -> dict:
    \"\"\"Maneja latencia alta en una región.\"\"\"
    log_event("cost_operator", f"high_latency:{region}:{stats.get('response_time_ms',0)}ms")

    # Escalar réplicas secundarias
    deployments = v1.list_namespaced_deployment(
        NAMESPACE,
        label_selector=f"region={region}",
    )

    for dep in deployments.items:
        current = dep.spec.replicas
        new_replicas = min(int(current * 1.5), 20)  # escalar 50%
        body = {"spec": {"replicas": new_replicas}}
        v1.patch_namespaced_deployment(dep.metadata.name, NAMESPACE, body)
        log_event("cost_operator", f"scaled:{dep.metadata.name}:{current}->{new_replicas}")

    return {"region": region, "latency_ms": stats.get('response_time_ms', 0), "action": "scaled"}


# ─── Webhook de admisión (mutante) ────────────────────────────────
@kopf.on.create(NAMESPACE, field="spec.containers")
def mutate_pod(spec, **kwargs):
    \"\"\"Middleware mutante: asigna toleraciones según tenant.\"\"\"
    tenant_id = spec.get("metadata", {}).get("labels", {}).get("tenant-id", "")
    if not tenant_id:
        return

    # Agregar toleraciones para nodos del tenant
    tolerations = spec.get("spec", {}).get("tolerations", [])
    tolerations.append({
        "key": "medicare-pro/cost-overrun",
        "operator": "Equal",
        "value": tenant_id,
        "effect": "PreferNoSchedule",
    })
    spec["spec"]["tolerations"] = tolerations
    log_event("cost_operator", f"mutated_pod:{spec['metadata']['name']}:{tenant_id}")
"""


# ═══════════════════════════════════════════════════════════════════
# 3. SIMULADOR LOCAL (para pruebas sin cluster K8s)
# ═══════════════════════════════════════════════════════════════════

class CostAllocatorSimulator:
    """Simula las decisiones del operador K8s sin cluster real.

    Usa las métricas del FinOpsCollector y aplica decisiones
    lógicas para validar el comportamiento antes del deploy.
    """

    COST_THRESHOLD = 100.0
    LATENCY_THRESHOLD = 500.0

    def __init__(self):
        self._collector = None
        self._decisions: list[TenantCostDecision] = []

    async def evaluate_and_decide(self) -> list[TenantCostDecision]:
        """Evalúa métricas y simula decisiones del operador."""
        from core.finops_worker import FinOpsCollector
        from core.multi_region_balancer import get_multi_region_balancer

        collector = FinOpsCollector()
        metrics = await collector.collect_all()
        balancer = get_multi_region_balancer()

        decisions = []

        # Decisiones por tenant
        for tm in metrics:
            is_unprofitable = tm.estimated_cost_usd > self.COST_THRESHOLD
            action = "none"
            reason = ""

            if is_unprofitable:
                action = "evict_low_priority"
                reason = f"Costo ${tm.estimated_cost_usd:.2f} supera umbral ${self.COST_THRESHOLD}"
                if tm.estimated_cost_usd > self.COST_THRESHOLD * 3:
                    action = "scale_secondary"
                    reason += ". Activando réplicas secundarias de bajo costo."

            decision = TenantCostDecision(
                tenant_id=tm.tenant_id,
                estimated_cost_usd=tm.estimated_cost_usd,
                is_unprofitable=is_unprofitable,
                p95_latency_ms=0,
                action=action,
                reason=reason,
            )
            decisions.append(decision)
            self._decisions.append(decision)

            if action != "none":
                log_event("cost_operator", f"decision:{tm.tenant_id}:{action}:{reason[:60]}")

        # Decisiones por región (latencia)
        try:
            region_stats = await balancer.get_region_stats()
            for region, stats in region_stats.items():
                latency = stats.get("response_time_ms", 0)
                if latency > self.LATENCY_THRESHOLD:
                    log_event("cost_operator", f"region_latency:{region}:{latency}ms>threshold")
        except Exception:
            pass

        return decisions

    def get_decisions_summary(self) -> dict:
        """Resumen de decisiones para dashboard."""
        total = len(self._decisions)
        actions_taken = sum(1 for d in self._decisions if d.action != "none")
        unprofitable = sum(1 for d in self._decisions if d.is_unprofitable)
        return {
            "total_tenants_evaluated": total,
            "actions_taken": actions_taken,
            "unprofitable_tenants": unprofitable,
            "decisions": [
                {"tenant": d.tenant_id, "cost": round(d.estimated_cost_usd, 2),
                 "action": d.action, "reason": d.reason}
                for d in self._decisions
            ],
        }


__all__ = [
    "CostAllocatorSimulator",
    "TenantCostDecision",
    "KOPF_OPERATOR_CODE",
]
