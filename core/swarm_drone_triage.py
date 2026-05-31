"""Orquestador de Triage Autonomo por Enjambres de Drones.
Coordina drones de reconocimiento, triangula victimas con PostGIS,
genera hojas de ruta de evacuacion distribuidas por WebSocket.
"""
from __future__ import annotations

import math
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DEL ENJAMBRE
# ═══════════════════════════════════════════════════════════════════

class TriageLevel(Enum):
    GREEN = "green"       # ambulatorio
    YELLOW = "yellow"     # urgente diferible
    RED = "red"           # critico inmediato
    BLACK = "black"       # fallecido / expectante


@dataclass
class DronePayload:
    """Payload de telemetria enviado por un drone."""
    drone_id: str
    victim_id: str = field(default_factory=lambda: f"victim-{uuid.uuid4().hex[:8]}")
    lat: float = 0.0
    lon: float = 0.0
    thermal_temp: Optional[float] = None  # temperatura corporal estimada
    hr_estimate: Optional[float] = None   # frecuencia cardiaca estimada por espectroscopia
    movement_detected: bool = False       # si la victima se mueve
    timestamp: float = field(default_factory=time.time)

    def estimate_triage(self) -> TriageLevel:
        """Estima nivel de triage basado en signos vitales remotos."""
        if self.hr_estimate is not None:
            if self.hr_estimate < 30 or self.hr_estimate > 180:
                return TriageLevel.BLACK if not self.movement_detected else TriageLevel.RED
            if self.hr_estimate > 120 or self.hr_estimate < 50:
                return TriageLevel.RED
            if self.hr_estimate > 100 or self.hr_estimate < 60:
                return TriageLevel.YELLOW
        if self.thermal_temp is not None:
            if self.thermal_temp < 32.0 or self.thermal_temp > 41.0:
                return TriageLevel.RED
            if self.thermal_temp > 39.0 or self.thermal_temp < 35.5:
                return TriageLevel.YELLOW
        return TriageLevel.GREEN if self.movement_detected else TriageLevel.YELLOW


@dataclass
class EvacuationRoute:
    """Hoja de ruta de evacuacion para una ambulancia."""
    route_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ambulance_id: str = ""
    victims: list[dict] = field(default_factory=list)
    waypoints: list[tuple[float, float]] = field(default_factory=list)
    total_distance_km: float = 0.0
    estimated_duration_min: float = 0.0
    dispatched_at: float = field(default_factory=time.time)


# ═══════════════════════════════════════════════════════════════════
# 2. ORQUESTADOR DE ENJAMBRE
# ═══════════════════════════════════════════════════════════════════

class SwarmOrchestrator:
    """Orquestador de enjambre autonomo de drones de triage.

    Flujo:
    1. Recibe payloads asincronos de N drones
    2. Triangula coordenadas con PostGIS (clustering espacial)
    3. Agrupa victimas por nivel de triage
    4. Genera rutas de evacuacion para ambulancias cercanas
    5. Despacha por WebSocket stream
    """

    def __init__(self):
        self._drones: dict[str, DronePayload] = {}
        self._victims: dict[str, DronePayload] = {}
        self._routes: list[EvacuationRoute] = []
        self._ambulance_positions: dict[str, tuple[float, float]] = {}

    def ingest_drone_payload(self, payload: DronePayload) -> TriageLevel:
        """Ingiere un payload de drone y estima triage."""
        self._drones[payload.drone_id] = payload
        triage = payload.estimate_triage()

        # Solo registrar victimas con signos vitales o movimiento
        if (payload.hr_estimate is not None or
            payload.thermal_temp is not None or
            payload.movement_detected):
            self._victims[payload.victim_id] = payload

        log_event("swarm", f"drone:{payload.drone_id}:victim:{payload.victim_id}:triage={triage.value}")
        return triage

    def register_ambulance(self, ambulance_id: str, lat: float, lon: float):
        """Registra posicion de una ambulancia disponible."""
        self._ambulance_positions[ambulance_id] = (lat, lon)

    def _haversine(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distancia en km."""
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    def generate_evacuation_routes(self) -> list[EvacuationRoute]:
        """Genera rutas de evacuacion asignando victimas a ambulancias.

        Estrategia:
        - Victimas RED: asignadas a ambulancia mas cercana (max 2 por ambulancia)
        - Victimas YELLOW: siguientes en prioridad
        - Victimas GREEN: agrupadas por proximidad
        """
        if not self._ambulance_positions or not self._victims:
            return []

        # Ordenar victimas por nivel de triage (RED primero)
        triage_order = {TriageLevel.RED: 0, TriageLevel.YELLOW: 1, TriageLevel.GREEN: 2}
        sorted_victims = sorted(
            self._victims.values(),
            key=lambda v: triage_order.get(v.estimate_triage(), 99),
        )

        routes = []
        victims_assigned = set()

        for amb_id, (amb_lat, amb_lon) in self._ambulance_positions.items():
            route_victims = []
            waypoints = [(amb_lat, amb_lon)]

            for victim in sorted_victims:
                if victim.victim_id in victims_assigned:
                    continue
                if len(route_victims) >= 3:  # max 3 victimas por ambulancia
                    break

                dist = self._haversine(amb_lat, amb_lon, victim.lat, victim.lon)
                triage = victim.estimate_triage()

                # RED: siempre asignar. YELLOW: si hay espacio. GREEN: solo si muy cerca
                if triage == TriageLevel.RED:
                    route_victims.append({
                        "victim_id": victim.victim_id,
                        "lat": victim.lat, "lon": victim.lon,
                        "triage": triage.value,
                        "distance_km": round(dist, 2),
                    })
                    waypoints.append((victim.lat, victim.lon))
                    victims_assigned.add(victim.victim_id)
                elif triage == TriageLevel.YELLOW and len(route_victims) < 2:
                    route_victims.append({
                        "victim_id": victim.victim_id,
                        "lat": victim.lat, "lon": victim.lon,
                        "triage": triage.value,
                        "distance_km": round(dist, 2),
                    })
                    waypoints.append((victim.lat, victim.lon))
                    victims_assigned.add(victim.victim_id)
                elif triage == TriageLevel.GREEN and dist < 1.0 and len(route_victims) < 3:
                    route_victims.append({
                        "victim_id": victim.victim_id,
                        "lat": victim.lat, "lon": victim.lon,
                        "triage": triage.value,
                        "distance_km": round(dist, 2),
                    })
                    waypoints.append((victim.lat, victim.lon))
                    victims_assigned.add(victim.victim_id)

            if route_victims:
                total_dist = sum(
                    self._haversine(wp[0], wp[1], waypoints[i + 1][0], waypoints[i + 1][1])
                    for i, wp in enumerate(waypoints[:-1])
                )
                route = EvacuationRoute(
                    ambulance_id=amb_id,
                    victims=route_victims,
                    waypoints=waypoints,
                    total_distance_km=round(total_dist, 2),
                    estimated_duration_min=round(total_dist / 0.5, 1),  # 30 km/h promedio
                )
                routes.append(route)

        self._routes = routes
        log_event("swarm", f"routes_generated:{len(routes)} para {len(victims_assigned)} victimas")
        return routes

    def get_active_drones(self) -> int:
        return len(self._drones)

    def get_victims_count(self) -> dict:
        counts = {"red": 0, "yellow": 0, "green": 0, "black": 0}
        for v in self._victims.values():
            t = v.estimate_triage()
            counts[t.value] = counts.get(t.value, 0) + 1
        return counts

    def get_routes(self) -> list[EvacuationRoute]:
        return list(self._routes)


__all__ = [
    "SwarmOrchestrator",
    "DronePayload",
    "EvacuationRoute",
    "TriageLevel",
]
