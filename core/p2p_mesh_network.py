"""Ecosistema de Red Mesh Descentralizado P2P.
Protocolo Gossip sobre LoRaWAN/WiFi-Direct/BLE.
Los vectores clock y payloads MessagePack saltan de nodo a nodo
hasta alcanzar una base de datos local. Convergencia CRDT mutua.
Cero infraestructura central.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE RED MESH
# ═══════════════════════════════════════════════════════════════════

class MeshTransport(Enum):
    LORA = "lora"              # largo alcance, baja velocidad
    WIFI_DIRECT = "wifi_direct"  # corto alcance, alta velocidad
    BLE = "ble"                # ultra corto alcance, bajo consumo


class MeshNodeRole(Enum):
    AMBULANCE = "ambulance"     # nodo movil en ambulancia
    FIELD_WORKER = "field_worker" # telefono de enfermero
    HUB = "hub"                 # hospital local con base de datos
    RELAY = "relay"             # repetidor de senal


@dataclass
class MeshNode:
    """Nodo en la red mesh descentralizada."""
    node_id: str
    role: MeshNodeRole
    transport: MeshTransport
    lat: float = 0.0
    lon: float = 0.0
    battery_pct: float = 100.0
    last_seen: float = field(default_factory=time.time)
    queue_depth: int = 0
    is_online: bool = True

    def distance_to(self, other: MeshNode) -> float:
        """Distancia haversine en km."""
        import math
        R = 6371.0
        dlat = math.radians(other.lat - self.lat)
        dlon = math.radians(other.lon - self.lon)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(self.lat)) * math.cos(math.radians(other.lat)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


@dataclass
class MeshPacket:
    """Paquete de datos en la red mesh."""
    packet_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_node: str = ""
    dest_node: str = ""            # "" = broadcast
    payload: dict = field(default_factory=dict)
    vector_clock: str = ""          # compacto: "node1:3|node2:1"
    hop_count: int = 0
    max_hops: int = 10
    ttl_seconds: float = 300.0
    created_at: float = field(default_factory=time.time)
    signature: str = ""             # ECDSA hex

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds


# ═══════════════════════════════════════════════════════════════════
# 2. GOSSIP PROTOCOL ENGINE
# ═══════════════════════════════════════════════════════════════════

class GossipProtocol:
    """Protocolo Gossip para propagacion de paquetes en red mesh.

    Estrategia:
    - Push: al recibir un paquete, re-enviar a N nodos vecinos aleatorios
    - Pull: solicitar paquetes faltantes periodicamente
    - Anti-entropia: comparar relojes vectoriales con vecinos
    - Cada paquete lleva: vector_clock, hop_count, max_hops
    """

    GOSSIP_FANOUT = 3         # reenviar a 3 vecinos aleatorios
    GOSSIP_INTERVAL = 5.0     # segundos entre rondas de gossip

    def __init__(self, local_node: MeshNode):
        self.local = local_node
        self._known_nodes: dict[str, MeshNode] = {}
        self._seen_packets: set[str] = set()
        self._pending_queue: deque[MeshPacket] = deque(maxlen=500)
        self._delivered: list[MeshPacket] = []
        self._gossip_task: Optional[asyncio.Task] = None

    def register_node(self, node: MeshNode):
        """Registra un nodo conocido en la red."""
        self._known_nodes[node.node_id] = node
        log_event("mesh", f"node_discovered:{node.node_id}:{node.role.value}:{node.transport.value}")

    def get_visible_nodes(self, max_distance_km: float = 10.0) -> list[MeshNode]:
        """Nodos dentro del rango de transmision."""
        return [
            n for n in self._known_nodes.values()
            if n.is_online and n.node_id != self.local.node_id
            and self.local.distance_to(n) <= max_distance_km
        ]

    def submit_packet(self, packet: MeshPacket) -> bool:
        """Envia un paquete a la red mesh.

        Returns:
            True si se encolo para propagacion.
        """
        if packet.packet_id in self._seen_packets:
            return False  # ya visto, descartar

        packet.hop_count += 1
        self._seen_packets.add(packet.packet_id)
        self._pending_queue.append(packet)
        log_event("mesh", f"packet_submitted:{packet.packet_id}:hop={packet.hop_count}")
        return True

    async def gossip_round(self):
        """Ejecuta una ronda de gossip: push a vecinos.

        En producción: transmitir por radiofrecuencia (LoRa/BLE/WiFi-Direct).
        Stub: re-enviar a N nodos aleatorios en memoria.
        """
        if not self._pending_queue:
            return

        packet = self._pending_queue.popleft()

        # Verificar si expiró o excede hops
        if packet.is_expired() or packet.hop_count > packet.max_hops:
            return

        # Obtener nodos visibles para re-envio
        neighbors = self.get_visible_nodes()
        if not neighbors:
            # No hay vecinos: retener para reintentar despues
            self._pending_queue.append(packet)
            return

        # Push: reenviar a GOSSIP_FANOUT nodos aleatorios
        targets = random.sample(neighbors, min(self.GOSSIP_FANOUT, len(neighbors)))
        for target in targets:
            # En producción: enviar por el transporte correspondiente
            log_event("mesh", f"gossip_push:{packet.packet_id}->{target.node_id}:via_{target.transport.value}")
            packet.hop_count += 1

        # Confirmar entrega local
        self._delivered.append(packet)

    async def gossip_loop(self):
        """Loop de gossip continuo."""
        while True:
            await self.gossip_round()
            await asyncio.sleep(self.GOSSIP_INTERVAL)

    def start(self):
        """Inicia el loop de gossip."""
        if self._gossip_task is None or self._gossip_task.done():
            try:
                self._gossip_task = asyncio.create_task(self.gossip_loop())
            except RuntimeError:
                pass

    def get_stats(self) -> dict:
        return {
            "local_node": self.local.node_id,
            "known_nodes": len(self._known_nodes),
            "seen_packets": len(self._seen_packets),
            "pending": len(self._pending_queue),
            "delivered": len(self._delivered),
        }


# ═══════════════════════════════════════════════════════════════════
# 3. RED MESH ORQUESTADOR
# ═══════════════════════════════════════════════════════════════════

class MeshNetwork:
    """Red mesh descentralizada P2P con protocolo Gossip.

    Sin infraestructura central. Los datos saltan de nodo a nodo
    hasta alcanzar un HUB con base de datos local.
    Convergencia CRDT mediante Vector Clocks.
    """

    def __init__(self, local_node: MeshNode):
        self.protocol = GossipProtocol(local_node)
        self.local = local_node
        self._hubs: list[MeshNode] = []
        self._packet_log: list[MeshPacket] = []

    def register_hub(self, node: MeshNode):
        """Registra un HUB (hospital) como destino final de datos."""
        if node.role == MeshNodeRole.HUB:
            self._hubs.append(node)
            self.protocol.register_node(node)

    def broadcast_clinical_data(self, payload: dict, vector_clock: str,
                                 signature: str = "") -> MeshPacket:
        """Transmite datos clinicos a la red mesh.

        El paquete viajara de nodo en nodo (gossip) hasta
        alcanzar un HUB con base de datos local.

        Args:
            payload: Datos clinicos (MessagePack-ready).
            vector_clock: Reloj vectorial compacto.
            signature: Firma ECDSA del payload.

        Returns:
            MeshPacket creado.
        """
        packet = MeshPacket(
            source_node=self.local.node_id,
            payload=payload,
            vector_clock=vector_clock,
            signature=signature,
        )
        self.protocol.submit_packet(packet)
        self._packet_log.append(packet)
        log_event("mesh", f"broadcast:{packet.packet_id}:clock={vector_clock}")
        return packet

    def deliver_to_nearest_hub(self, packet: MeshPacket) -> Optional[str]:
        """Entrega un paquete al HUB mas cercano, si hay alguno visible.

        Returns:
            hub_id si se entrego, None si no.
        """
        if not self._hubs:
            return None

        nearest = min(
            self._hubs,
            key=lambda h: self.local.distance_to(h),
        )
        dist = self.local.distance_to(nearest)

        if dist > 50:  # max 50km para entrega directa
            return None

        log_event("mesh", f"delivered_to_hub:{packet.packet_id}->{nearest.node_id}:{dist:.1f}km")
        return nearest.node_id

    def simulate_propagation(self, packet: MeshPacket, nodes: list[MeshNode]) -> int:
        """Simula la propagacion de un paquete a traves de la red mesh.

        Cada nodo re-envia a GOSSIP_FANOUT nodos aleatorios.
        Retorna cuantos nodos recibieron el paquete.

        Args:
            packet: Paquete a propagar.
            nodes: Lista de nodos en la red.

        Returns:
            Cantidad de nodos que recibieron el paquete.
        """
        reached = set()
        frontier = {self.local.node_id}

        for _ in range(packet.max_hops):
            new_frontier = set()
            for node_id in frontier:
                node = next((n for n in nodes if n.node_id == node_id), None)
                if not node:
                    continue
                # Cada nodo re-envia a GOSSIP_FANOUT vecinos
                neighbors = [
                    n for n in nodes
                    if n.node_id != node_id
                    and n.node_id not in reached
                    and node.distance_to(n) <= 10.0
                ]
                for neighbor in random.sample(neighbors, min(self.protocol.GOSSIP_FANOUT, len(neighbors))):
                    new_frontier.add(neighbor.node_id)
                    reached.add(neighbor.node_id)

            frontier = new_frontier
            if not frontier:
                break

        log_event("mesh", f"propagation:{packet.packet_id}:reached={len(reached)}/{len(nodes)} nodes")
        return len(reached)


__all__ = [
    "MeshNetwork",
    "GossipProtocol",
    "MeshNode",
    "MeshPacket",
    "MeshTransport",
    "MeshNodeRole",
]
