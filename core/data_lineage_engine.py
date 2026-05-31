"""Motor de linaje de datos clinicos end-to-end.
Reconstruye el arbol de procedencia de una alerta o evolucion
desde el dispositivo Edge hasta el webhook de la prepaga.
"""
from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE LINALE
# ═══════════════════════════════════════════════════════════════════

class LineageNodeType:
    DEVICE = "device"
    SYNC_BATCH = "sync_batch"
    CRDT_MERGE = "crdt_merge"
    EVENT_STORE = "event_store"
    SNAPSHOT = "snapshot"
    WEBHOOK_DISPATCH = "webhook_dispatch"
    ALERT = "alert"
    FHIR_EXPORT = "fhir_export"


@dataclass
class LineageNode:
    """Nodo del arbol de procedencia."""
    id: str
    node_type: str
    label: str
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LineageEdge:
    """Arista del arbol de procedencia."""
    source_id: str
    target_id: str
    relation: str        # "generated_by" | "transformed_by" | "validated_by" | "dispatched_by"
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class LineageGraph:
    """Grafo dirigido aciclico (DAG) de procedencia."""
    nodes: dict[str, LineageNode] = field(default_factory=dict)
    edges: list[LineageEdge] = field(default_factory=list)

    def add_node(self, node: LineageNode):
        self.nodes[node.id] = node

    def add_edge(self, edge: LineageEdge):
        self.edges.append(edge)

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
        }

    def to_dot(self) -> str:
        """Exporta a formato Graphviz DOT para visualizacion."""
        lines = ['digraph Lineage {', '    rankdir=LR;', '    node [shape=box, style=rounded];']
        for n in self.nodes.values():
            color = {
                LineageNodeType.DEVICE: "#4CAF50",
                LineageNodeType.SYNC_BATCH: "#2196F3",
                LineageNodeType.CRDT_MERGE: "#FF9800",
                LineageNodeType.EVENT_STORE: "#9C27B0",
                LineageNodeType.SNAPSHOT: "#00BCD4",
                LineageNodeType.WEBHOOK_DISPATCH: "#F44336",
                LineageNodeType.ALERT: "#FF5722",
                LineageNodeType.FHIR_EXPORT: "#607D8B",
            }.get(n.node_type, "#999999")
            label = n.label.replace('"', '\\"')
            lines.append(f'    "{n.id}" [label="{label}", fillcolor="{color}", style="filled,rounded"];')
        for e in self.edges:
            lines.append(f'    "{e.source_id}" -> "{e.target_id}" [label="{e.relation}"];')
        lines.append('}')
        return '\n'.join(lines)


# ═══════════════════════════════════════════════════════════════════
# 2. DATA LINEAGE ENGINE
# ═══════════════════════════════════════════════════════════════════

class DataLineageEngine:
    """Motor de trazabilidad que reconstruye el arbol de procedencia.

    Uso:
        engine = DataLineageEngine()
        graph = await engine.trace_alert("alert-abc-123")
        print(graph.to_dot())
    """

    def __init__(self):
        self._conn = None
        self._store = None

    async def _get_conn(self):
        if self._conn is None:
            import asyncpg
            self._conn = await asyncpg.connect("postgresql://localhost:5432/medicare")
        return self._conn

    async def _get_event_store(self):
        if self._store is None:
            from core.clinical_event_store import ClinicalEventStore
            self._store = ClinicalEventStore()
        return self._store

    async def trace_alert(self, alert_id: str) -> LineageGraph:
        """Reconstruye el arbol completo de una alerta clinica.

        Traza: alert -> evento_event_store -> sync_batch -> crdt_merge -> device
        Opcionalmente: -> webhook_dispatch -> fhir_export
        """
        graph = LineageGraph()
        conn = await self._get_conn()

        # Buscar alerta en event store
        event_rows = await conn.fetch("""
            SELECT * FROM clinical_event_store
            WHERE aggregate_type = 'alerta'
              AND aggregate_id = $1
            ORDER BY event_version ASC
        """, alert_id)

        if not event_rows:
            # Alerta no encontrada en event store, buscar en tabla de alertas
            alert_row = await conn.fetchrow("""
                SELECT id, payload, created_at, tenant_id
                FROM clinical_event_store
                WHERE payload->>'alert_id' = $1
                LIMIT 1
            """, alert_id)
            if alert_row:
                event_rows = [alert_row]

        if not event_rows:
            # Intentar con alerta directamente como SignedClinicalAlert
            alert_node = LineageNode(
                id=f"alert:{alert_id}",
                node_type=LineageNodeType.ALERT,
                label=f"Alerta Clinica {alert_id[:12]}...",
                metadata={"alert_id": alert_id, "source": "direct_lookup"},
            )
            graph.add_node(alert_node)
            return graph

        alert_node_id = f"alert:{alert_id}"
        for ev in event_rows:
            # 1. Nodo: Event Store
            event_node_id = f"event:{ev['id']}"
            graph.add_node(LineageNode(
                id=event_node_id,
                node_type=LineageNodeType.EVENT_STORE,
                label=f"Event: {ev['event_type']} v{ev['event_version']}",
                metadata={
                    "event_type": ev["event_type"],
                    "event_version": ev["event_version"],
                    "tenant_id": str(ev["tenant_id"]),
                    "checksum": ev["checksum"],
                    "actor_id": ev["actor_id"],
                },
                timestamp=ev["created_at"].isoformat() if ev["created_at"] else "",
            ))

            if ev["prev_event_id"]:
                graph.add_edge(LineageEdge(
                    source_id=f"event:{ev['prev_event_id']}",
                    target_id=event_node_id,
                    relation="preceded_by",
                ))

            graph.add_edge(LineageEdge(
                source_id=alert_node_id if graph.nodes.get(alert_node_id) else event_node_id,
                target_id=event_node_id,
                relation="recorded_as",
            ))

            # 2. Nodo: Snapshot (si existe)
            snap = await conn.fetchrow("""
                SELECT version, updated_at FROM clinical_snapshot
                WHERE aggregate_type = $1 AND aggregate_id = $2
            """, ev["aggregate_type"], ev["aggregate_id"])
            if snap:
                snap_node_id = f"snapshot:{ev['aggregate_type']}:{ev['aggregate_id']}"
                graph.add_node(LineageNode(
                    id=snap_node_id,
                    node_type=LineageNodeType.SNAPSHOT,
                    label=f"Snapshot v{snap['version']}",
                    metadata={"version": snap["version"]},
                    timestamp=snap["updated_at"].isoformat() if snap["updated_at"] else "",
                ))
                graph.add_edge(LineageEdge(
                    source_id=event_node_id,
                    target_id=snap_node_id,
                    relation="materialized_as",
                ))

            # 3. Nodo: Webhook dispatch (si se registro)
            webhook_rows = await conn.fetch("""
                SELECT id, event_type, created_at FROM clinical_event_store
                WHERE aggregate_type = 'webhook_dispatch'
                  AND aggregate_id = $1
                LIMIT 5
            """, alert_id)
            for wh in webhook_rows:
                wh_node_id = f"webhook:{wh['id']}"
                graph.add_node(LineageNode(
                    id=wh_node_id,
                    node_type=LineageNodeType.WEBHOOK_DISPATCH,
                    label=f"Webhook: {wh['event_type']}",
                    metadata={"event_type": wh["event_type"]},
                    timestamp=wh["created_at"].isoformat() if wh["created_at"] else "",
                ))
                graph.add_edge(LineageEdge(
                    source_id=event_node_id,
                    target_id=wh_node_id,
                    relation="dispatched_as",
                ))

        # 4. Nodo: Dispositivo (desde payload si incluye device_id)
        if event_rows:
            payload = event_rows[0].get("payload", {})
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except (json.JSONDecodeError, TypeError):
                    payload = {}
            device_id = payload.get("device_id") or payload.get("dispositivo_id", "")
            if device_id:
                device_node_id = f"device:{device_id}"
                graph.add_node(LineageNode(
                    id=device_node_id,
                    node_type=LineageNodeType.DEVICE,
                    label=f"Dispositivo: {device_id[:16]}...",
                    metadata={"device_id": device_id},
                ))
                first_event_id = f"event:{event_rows[0]['id']}"
                graph.add_edge(LineageEdge(
                    source_id=device_node_id,
                    target_id=first_event_id,
                    relation="generated_by",
                ))

        # Nodo raiz de alerta si no existe
        if alert_node_id not in graph.nodes:
            graph.add_node(LineageNode(
                id=alert_node_id,
                node_type=LineageNodeType.ALERT,
                label=f"Alerta {alert_id[:16]}...",
                metadata={"alert_id": alert_id},
            ))

        log_event("lineage", f"trace_alert:{alert_id}:{len(graph.nodes)} nodos:{len(graph.edges)} aristas")
        return graph

    async def trace_evolution(self, evolution_id: str) -> LineageGraph:
        """Reconstruye el linaje de una evolucion clinica."""
        graph = LineageGraph()
        store = await self._get_event_store()
        replay = await store.replay("evolucion", evolution_id)

        event_root = LineageNode(
            id=f"evo:{evolution_id}",
            node_type=LineageNodeType.EVENT_STORE,
            label=f"Evolucion {evolution_id[:16]}...",
            metadata={"replay_version": replay["version"]},
        )
        graph.add_node(event_root)

        # Agregar eventos individuales como sub-nodos
        fake_event_id = f"event:evo:{evolution_id}:0"
        for i in range(replay["version"]):
            event_id = f"event:evo:{evolution_id}:{i + 1}"
            graph.add_node(LineageNode(
                id=event_id,
                node_type=LineageNodeType.EVENT_STORE,
                label=f"Event v{i + 1}",
                metadata={"version": i + 1},
            ))
            if i == 0:
                graph.add_edge(LineageEdge(source_id=event_root.id, target_id=event_id, relation="composed_of"))
            else:
                graph.add_edge(LineageEdge(source_id=fake_event_id, target_id=event_id, relation="preceded_by"))
            fake_event_id = event_id

        # Snapshot
        snap_id = f"snapshot:evo:{evolution_id}"
        graph.add_node(LineageNode(
            id=snap_id,
            node_type=LineageNodeType.SNAPSHOT,
            label=f"Snapshot v{replay['version']}",
            metadata={"version": replay["version"]},
        ))
        graph.add_edge(LineageEdge(
            source_id=event_root.id,
            target_id=snap_id,
            relation="materialized_as",
        ))

        return graph

    async def trace_device(self, device_id: str) -> LineageGraph:
        """Traza todas las alertas generadas por un dispositivo."""
        graph = LineageGraph()
        conn = await self._get_conn()

        device_node = LineageNode(
            id=f"device:{device_id}",
            node_type=LineageNodeType.DEVICE,
            label=f"Dispositivo: {device_id[:20]}...",
            metadata={"device_id": device_id},
        )
        graph.add_node(device_node)

        # Buscar eventos generados por este dispositivo
        rows = await conn.fetch("""
            SELECT id, aggregate_type, aggregate_id, event_type, created_at
            FROM clinical_event_store
            WHERE payload->>'device_id' = $1
               OR payload->>'dispositivo_id' = $1
            ORDER BY created_at DESC
            LIMIT 50
        """, device_id)

        for r in rows:
            event_id = f"event:{r['id']}"
            graph.add_node(LineageNode(
                id=event_id,
                node_type=LineageNodeType.EVENT_STORE,
                label=f"{r['event_type']}:{str(r['aggregate_id'])[:12]}...",
                timestamp=r["created_at"].isoformat() if r["created_at"] else "",
            ))
            graph.add_edge(LineageEdge(
                source_id=device_node.id,
                target_id=event_id,
                relation="generated_by",
            ))

        return graph

    async def trace_webhook(self, webhook_event_id: str) -> LineageGraph:
        """Traza desde un webhook dispatch hacia atras."""
        graph = LineageGraph()
        conn = await self._get_conn()

        wh_node = LineageNode(
            id=f"webhook:{webhook_event_id}",
            node_type=LineageNodeType.WEBHOOK_DISPATCH,
            label=f"Webhook Dispatch {webhook_event_id[:16]}...",
        )
        graph.add_node(wh_node)

        # Buscar evento de origen
        row = await conn.fetchrow("""
            SELECT id, aggregate_type, aggregate_id, event_type, created_at
            FROM clinical_event_store
            WHERE id = $1::UUID
        """, webhook_event_id)
        if row:
            event_id = f"event:{row['id']}"
            graph.add_node(LineageNode(
                id=event_id,
                node_type=LineageNodeType.EVENT_STORE,
                label=f"Source: {row['event_type']}",
            ))
            graph.add_edge(LineageEdge(
                source_id=event_id,
                target_id=wh_node.id,
                relation="dispatched_as",
            ))

        return graph

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


# ═══════════════════════════════════════════════════════════════════
# 3. INTEGRACION CON WEBHOOK POOL (registro de dispatch)
# ═══════════════════════════════════════════════════════════════════

def create_webhook_lineage_event(alert_id: str, tenant_id: str,
                                   event_type: str, status: str) -> dict:
    """Crea un evento de linaje para registrar un dispatch de webhook.

    Returns:
        dict listo para insertar en clinical_event_store.
    """
    return {
        "aggregate_type": "webhook_dispatch",
        "aggregate_id": alert_id,
        "event_type": f"Webhook{event_type.capitalize()}",
        "tenant_id": tenant_id,
        "actor_id": "system",
        "payload": json.dumps({
            "alert_id": alert_id,
            "webhook_status": status,
            "event_type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }),
    }


__all__ = [
    "DataLineageEngine",
    "LineageGraph",
    "LineageNode",
    "LineageEdge",
    "LineageNodeType",
    "create_webhook_lineage_event",
]
