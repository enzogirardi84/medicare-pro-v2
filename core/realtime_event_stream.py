"""Streaming bidireccional en tiempo real via WebSockets + Redis Pub/Sub.
Despacha notificaciones criticas (NEWS2, cambios de ruta, cancelaciones)
en menos de 50ms directamente a la app movil del profesional.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE MENSAJES EN TIEMPO REAL
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RealtimeMessage:
    """Mensaje para transmision en tiempo real."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: str = ""          # "alerta.news2" | "ruta.cambio" | "turno.cancelado"
    tenant_id: str = ""
    professional_id: str = ""
    payload: dict = field(default_factory=dict)
    priority: int = 0             # 0=normal, 1=alta, 2=critica
    timestamp: float = field(default_factory=time.time)
    ttl_seconds: int = 300        # 5 min default

    def to_json(self) -> str:
        return json.dumps({
            "id": self.id,
            "event_type": self.event_type,
            "tenant_id": self.tenant_id,
            "professional_id": self.professional_id,
            "payload": self.payload,
            "priority": self.priority,
            "timestamp": self.timestamp,
            "ttl": self.ttl_seconds,
        }, default=str)

    @classmethod
    def from_json(cls, raw: str) -> RealtimeMessage:
        d = json.loads(raw)
        return cls(**{k: v for k, v in d.items() if k != "ttl"}, ttl_seconds=d.get("ttl", 300))


# ═══════════════════════════════════════════════════════════════════
# 2. GESTOR DE CONEXIONES WEBSOCKET
# ═══════════════════════════════════════════════════════════════════

class WebSocketManager:
    """Gestor de conexiones WebSocket por tenant y profesional.

    Mantiene un mapa de conexiones activas para enrutar mensajes
    al profesional correcto en menos de 50ms.
    """

    def __init__(self):
        self._connections: dict[str, dict[str, list[asyncio.Queue]]] = {}
        # {tenant_id: {professional_id: [queue1, queue2]}}

    async def connect(self, tenant_id: str, professional_id: str) -> asyncio.Queue:
        """Registra una nueva conexion WebSocket.

        Returns:
            asyncio.Queue donde se entregaran los mensajes para este profesional.
        """
        if tenant_id not in self._connections:
            self._connections[tenant_id] = {}
        if professional_id not in self._connections[tenant_id]:
            self._connections[tenant_id][professional_id] = []

        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self._connections[tenant_id][professional_id].append(queue)
        log_event("ws_manager", f"connect:{tenant_id}:{professional_id}")
        return queue

    async def disconnect(self, tenant_id: str, professional_id: str,
                         queue: asyncio.Queue):
        """Remueve una conexion WebSocket."""
        queues = self._connections.get(tenant_id, {}).get(professional_id, [])
        if queue in queues:
            queues.remove(queue)
        if not queues:
            self._connections[tenant_id].pop(professional_id, None)
        if not self._connections.get(tenant_id):
            self._connections.pop(tenant_id, None)
        log_event("ws_manager", f"disconnect:{tenant_id}:{professional_id}")

    async def send_to_professional(self, tenant_id: str, professional_id: str,
                                   message: RealtimeMessage) -> int:
        """Envia un mensaje a todas las conexiones de un profesional.

        Args:
            tenant_id: ID del tenant.
            professional_id: ID del profesional destino.
            message: Mensaje a enviar.

        Returns:
            Cantidad de conexiones a las que se entrego el mensaje.
        """
        queues = self._connections.get(tenant_id, {}).get(professional_id, [])
        delivered = 0
        for queue in queues:
            try:
                queue.put_nowait(message)
                delivered += 1
            except asyncio.QueueFull:
                log_event("ws_manager", f"queue_full:{tenant_id}:{professional_id}")
        return delivered

    async def send_to_tenant(self, tenant_id: str, message: RealtimeMessage) -> int:
        """Broadcast a todos los profesionales conectados de un tenant."""
        total = 0
        for prof_id in list(self._connections.get(tenant_id, {})):
            total += await self.send_to_professional(tenant_id, prof_id, message)
        return total

    def get_connected_count(self) -> dict:
        """Estadisticas de conexiones activas."""
        total_professionals = 0
        total_connections = 0
        for tid, pros in self._connections.items():
            for pid, queues in pros.items():
                total_professionals += 1
                total_connections += len(queues)
        return {
            "tenants": len(self._connections),
            "professionals": total_professionals,
            "connections": total_connections,
        }


# ═══════════════════════════════════════════════════════════════════
# 3. INTEGRACION CON REDIS PUB/SUB
# ═══════════════════════════════════════════════════════════════════

class RedisPubSubBridge:
    """Puente entre Redis Pub/Sub y WebSocket Manager.

    Escucha canales de Redis y re-despacha a los WebSockets locales.
    Permite que multiples instancias de la app compartan eventos.
    """

    CHANNEL_PREFIX = "medicare:realtime:"

    def __init__(self, ws_manager: WebSocketManager):
        self._ws = ws_manager
        self._redis = None
        self._pubsub_task: Optional[asyncio.Task] = None
        self._channels: set[str] = set()

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asynced as aioredis
                self._redis = aioredis.Redis(
                    host=os.environ.get("REDIS_HOST", "localhost"),
                    port=int(os.environ.get("REDIS_PORT", "6379")),
                    db=5,
                    decode_responses=True,
                )
            except Exception:
                pass
        return self._redis

    async def publish(self, tenant_id: str, message: RealtimeMessage) -> bool:
        """Publica un mensaje en Redis Pub/Sub.

        Otras instancias de la app recibiran el mensaje
        y lo entregaran a los WebSockets locales.
        """
        r = await self._get_redis()
        if not r:
            return False
        channel = f"{self.CHANNEL_PREFIX}{tenant_id}"
        await r.publish(channel, message.to_json())
        return True

    async def subscribe(self, tenant_id: str):
        """Se suscribe a eventos de un tenant."""
        channel = f"{self.CHANNEL_PREFIX}{tenant_id}"
        self._channels.add(channel)
        if self._pubsub_task is None or self._pubsub_task.done():
            self._pubsub_task = asyncio.create_task(self._pubsub_loop())

    async def _pubsub_loop(self):
        """Loop que escucha Redis Pub/Sub y despacha a WS locales."""
        r = await self._get_redis()
        if not r:
            return

        pubsub = r.pubsub()
        for ch in self._channels:
            await pubsub.subscribe(ch)

        async for message in pubsub.listen():
            if message["type"] != "message":
                continue
            try:
                msg = RealtimeMessage.from_json(message["data"])
                delivered = await self._ws.send_to_professional(
                    msg.tenant_id, msg.professional_id, msg,
                )
                if delivered == 0:
                    log_event("ws_pubsub", f"no_ws:{msg.event_type}:{msg.professional_id}")
            except Exception as exc:
                log_event("ws_pubsub", f"error:{type(exc).__name__}")

    async def close(self):
        if self._pubsub_task:
            self._pubsub_task.cancel()
            try:
                await self._pubsub_task
            except (asyncio.CancelledError, RuntimeError):
                pass
        if self._redis:
            await self._redis.close()
            self._redis = None


# ═══════════════════════════════════════════════════════════════════
# 4. FASTAPI WEBSOCKET ENDPOINT (ejemplo de integracion)
# ═══════════════════════════════════════════════════════════════════

FASTAPI_WS_ENDPOINT = """
# Registrar en la app FastAPI:
#
# from core.realtime_event_stream import WebSocketManager, RedisPubSubBridge
# ws_manager = WebSocketManager()
# ws_bridge = RedisPubSubBridge(ws_manager)
#
# @app.websocket("/ws/{tenant_id}/{professional_id}")
# async def websocket_endpoint(websocket: WebSocket, tenant_id: str, professional_id: str):
#     await websocket.accept()
#     queue = await ws_manager.connect(tenant_id, professional_id)
#     await ws_bridge.subscribe(tenant_id)
#     try:
#         while True:
#             # Recibir mensajes del cliente (ej. heartbeat)
#             try:
#                 data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
#             except asyncio.TimeoutError:
#                 await websocket.send_json({"type": "ping"})
#                 continue
#
#             # Enviar mensajes de la cola al WebSocket
#             try:
#                 msg = await asyncio.wait_for(queue.get(), timeout=1.0)
#                 await websocket.send_text(msg.to_json())
#             except asyncio.TimeoutError:
#                 pass
#
#     except WebSocketDisconnect:
#         await ws_manager.disconnect(tenant_id, professional_id, queue)

from fastapi import WebSocket, WebSocketDisconnect
"""


# ═══════════════════════════════════════════════════════════════════
# 5. HELPERS PARA CREAR MENSAJES COMUNES
# ═══════════════════════════════════════════════════════════════════

def create_alert_news2(tenant_id: str, professional_id: str,
                        paciente_id: str, score: int, nivel: str) -> RealtimeMessage:
    """Crea un mensaje de alerta NEWS2 para tiempo real."""
    return RealtimeMessage(
        event_type="alerta.news2",
        tenant_id=tenant_id,
        professional_id=professional_id,
        payload={
            "paciente_id": paciente_id,
            "score": score,
            "nivel": nivel,
            "message": f"Alerta {nivel}: paciente {paciente_id[:8]}... score NEWS2={score}",
        },
        priority=2 if nivel == "CRITICO" else 1,
        ttl_seconds=600,
    )


def create_ruta_cambio(tenant_id: str, professional_id: str,
                        motivo: str, nueva_direccion: str) -> RealtimeMessage:
    """Crea un mensaje de cambio de ruta."""
    return RealtimeMessage(
        event_type="ruta.cambio",
        tenant_id=tenant_id,
        professional_id=professional_id,
        payload={
            "motivo": motivo,
            "nueva_direccion": nueva_direccion,
        },
        priority=1,
    )


def create_turno_cancelado(tenant_id: str, professional_id: str,
                            turno_id: str, paciente: str) -> RealtimeMessage:
    """Crea un mensaje de cancelacion de turno."""
    return RealtimeMessage(
        event_type="turno.cancelado",
        tenant_id=tenant_id,
        professional_id=professional_id,
        payload={
            "turno_id": turno_id,
            "paciente": paciente,
        },
        priority=1,
    )


__all__ = [
    "WebSocketManager",
    "RedisPubSubBridge",
    "RealtimeMessage",
    "create_alert_news2",
    "create_ruta_cambio",
    "create_turno_cancelado",
    "FASTAPI_WS_ENDPOINT",
]
