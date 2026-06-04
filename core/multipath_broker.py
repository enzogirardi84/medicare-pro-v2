"""Broker de Conectividad Híbrida Dinámica (Multipath).
Mide latencia y packet loss en 3 interfaces (5G, Starlink, 4G).
Conmuta en <10ms si la calidad cae del umbral.
Transparente para RealtimeEventStream.
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE CONECTIVIDAD
# ═══════════════════════════════════════════════════════════════════

class LinkType(Enum):
    CELLULAR_5G = "5g"
    CELLULAR_4G = "4g"
    STARLINK = "starlink"
    ETHERNET = "ethernet"


class LinkState(Enum):
    ACTIVE = "active"          # siendo usado actualmente
    STANDBY = "standby"        # disponible pero no activo
    FAILED = "failed"          # caído, no disponible
    DEGRADED = "degraded"      # activo pero con baja calidad


@dataclass
class NetworkLink:
    """Una interfaz de red física disponible."""
    name: str
    link_type: LinkType
    state: LinkState = LinkState.STANDBY
    priority: int = 100           # menor = preferido
    latency_ms: float = 0.0       # ping p95
    packet_loss_pct: float = 0.0
    bandwidth_mbps: float = 0.0
    last_checked: float = 0.0
    consecutive_failures: int = 0
    is_active: bool = False

    @property
    def is_healthy(self) -> bool:
        return (self.latency_ms < 200 and
                self.packet_loss_pct < 5.0 and
                self.state != LinkState.FAILED)


# ═══════════════════════════════════════════════════════════════════
# 2. MULTIPATH BROKER
# ═══════════════════════════════════════════════════════════════════

class MultipathBroker:
    """Broker de conectividad multi-ruta con failover automático.

    Estrategia:
    - Activo: la mejor interfaz disponible segun prioridad + salud
    - Resto: en STANDBY
    - Health check cada 1s: ping, packet loss
    - Si activo DEGRADED o FAILED: conmutar en <10ms
    - Transparente para RealtimeEventStream y WebSocketManager
    """

    HEALTH_CHECK_INTERVAL = 1.0    # 1 segundo
    LATENCY_THRESHOLD = 200.0       # ms
    PACKET_LOSS_THRESHOLD = 5.0     # %
    HANDOFF_TIMEOUT = 0.01          # 10ms máximo de handoff

    def __init__(self):
        self._links: dict[str, NetworkLink] = {}
        self._active_link: Optional[str] = None
        self._health_task: Optional[asyncio.Task] = None
        self._handoff_callbacks: list[Callable] = []
        self._handoff_count = 0

    def configure_links(self, links: list[NetworkLink]):
        """Configura las interfaces de red disponibles.

        Args:
            links: Lista de interfaces ordenadas por prioridad.
        """
        for link in links:
            self._links[link.name] = link

        # Activar la de mayor prioridad (menor número)
        if links:
            best = min(links, key=lambda l: l.priority)
            self._activate_link(best.name)

        log_event("multipath", f"configured:{len(links)} links, active:{self._active_link}")
        self._ensure_health_checks()

    def register_handoff_callback(self, callback: Callable):
        """Registra callback ejecutado tras cada handoff.

        El callback recibe (old_link_name, new_link_name).
        """
        self._handoff_callbacks.append(callback)

    def _activate_link(self, name: str):
        """Activa una interfaz y desactiva las demás."""
        for n, link in self._links.items():
            was_active = link.is_active
            link.is_active = (n == name)
            if n == name and link.state == LinkState.STANDBY:
                link.state = LinkState.ACTIVE
            elif was_active and n != name:
                link.state = LinkState.STANDBY

        old_active = self._active_link
        self._active_link = name

        if old_active and old_active != name:
            self._handoff_count += 1
            log_event("multipath", f"HANDOFF:{old_active}->{name}")
            for cb in self._handoff_callbacks:
                try:
                    cb(old_active, name)
                except Exception as exc:
                    log_event("multipath", f"callback_error:{type(exc).__name__}")

    def get_active_link(self) -> Optional[str]:
        """Retorna el nombre de la interfaz activa."""
        return self._active_link

    async def get_active_socket(self) -> Optional[str]:
        """Retorna la IP/ruta del socket activo.

        En producción: devuelve la interfaz de red concreta
        para enlazar el socket WebSocket.
        """
        link = self._links.get(self._active_link) if self._active_link else None
        if link:
            return f"{link.name}://transport.medicare-pro.app"
        return None

    # ── Health checks ─────────────────────────────────────

    def _ensure_health_checks(self):
        try:
            if self._health_task is None or self._health_task.done():
                loop = asyncio.get_running_loop()
                self._health_task = loop.create_task(self._health_loop())
        except RuntimeError:
            pass

    async def _health_loop(self):
        """Loop de health checking cada 1 segundo."""
        while True:
            await asyncio.sleep(self.HEALTH_CHECK_INTERVAL)
            await self._check_all_links()
            await self._evaluate_failover()

    async def _check_all_links(self):
        """Simula health check de cada interfaz.

        En producción: ejecuta ping real a 8.8.8.8 o al gateway.
        Stub: simula variación de latencia/packet loss.
        """
        for name, link in self._links.items():
            # Stub: simular métricas de red
            link.latency_ms = round(random.uniform(10, 300), 1)
            link.packet_loss_pct = round(random.uniform(0, 8), 1)

            if link.latency_ms > 500 or link.packet_loss_pct > 20:
                link.consecutive_failures += 1
                if link.consecutive_failures >= 3:
                    link.state = LinkState.FAILED
            else:
                link.consecutive_failures = 0
                if link.state == LinkState.FAILED:
                    link.state = LinkState.STANDBY

            link.last_checked = time.time()

    async def _evaluate_failover(self):
        """Evalúa si es necesario conmutar a otra interfaz."""
        if not self._active_link:
            return

        active = self._links.get(self._active_link)
        if not active:
            return

        # Verificar si el enlace activo está degradado
        needs_handoff = (active.latency_ms > self.LATENCY_THRESHOLD or
                         active.packet_loss_pct > self.PACKET_LOSS_THRESHOLD or
                         active.state == LinkState.FAILED or
                         active.consecutive_failures >= 2)

        if not needs_handoff:
            return

        # Buscar mejor alternativa
        candidates = [
            (name, link) for name, link in self._links.items()
            if name != self._active_link and link.is_healthy
        ]

        if candidates:
            # Elegir la de menor latencia entre las saludables
            best = min(candidates, key=lambda c: c[1].latency_ms)
            self._activate_link(best[0])
        elif not any(l.is_healthy for l in self._links.values()):
            # Todas caídas: mantener la activa aunque esté degradada
            log_event("multipath", "all_links_down:keeping_active")

    # ── Stats ─────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Estadísticas de todas las interfaces."""
        return {
            "active_link": self._active_link,
            "handoffs": self._handoff_count,
            "links": {
                name: {
                    "type": link.link_type.value,
                    "state": link.state.value,
                    "latency_ms": link.latency_ms,
                    "packet_loss_pct": link.packet_loss_pct,
                    "is_active": link.is_active,
                    "healthy": link.is_healthy,
                }
                for name, link in self._links.items()
            },
        }

    async def close(self):
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except (asyncio.CancelledError, RuntimeError):
                pass


__all__ = [
    "MultipathBroker",
    "NetworkLink",
    "LinkType",
    "LinkState",
]
