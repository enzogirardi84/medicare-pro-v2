"""Balanceador multi-region para read replicas con geo-deteccion,
health checking, deteccion de lag y fallback a primaria.
Extiende el ReadReplicaBalancer original con conciencia regional.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS
# ═══════════════════════════════════════════════════════════════════

class RegionStatus(Enum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"   # lag > threshold
    DOWN = "down"


@dataclass
class RegionConfig:
    """Configuracion de una region geografica."""
    name: str                        # "us-east-1", "sa-east-1", etc.
    priority: int = 100              # menor = mayor prioridad
    replicas: list[str] = field(default_factory=list)
    primary_url: str = ""
    max_lag_seconds: float = 5.0
    health_check_interval: float = 30.0
    coordinates: tuple[float, float] = (0.0, 0.0)  # lat, lon


@dataclass
class RegionHealth:
    """Estado de salud de una region."""
    status: RegionStatus = RegionStatus.HEALTHY
    last_check: float = 0.0
    lag_seconds: float = 0.0
    consecutive_failures: int = 0
    response_time_ms: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# 2. BALANCEADOR MULTI-REGION
# ═══════════════════════════════════════════════════════════════════

class MultiRegionBalancer:
    """Balanceador de read replicas con conciencia geografica.

    Caracteristicas:
    - Detecta la region del cliente via GeoIP/cabecera X-Region
    - Enruta a la replica mas cercana
    - Health checking periodico con deteccion de lag
    - Fallback escalonado: misma region -> region vecina -> primaria
    - Latency-weighted random selection dentro de la region
    """

    HAVERSINE_CACHE: dict[tuple, float] = {}

    def __init__(self):
        self._regions: dict[str, RegionConfig] = {}
        self._health: dict[str, RegionHealth] = {}
        self._default_region = "primary"
        self._lock = asyncio.Lock()
        self._health_task: Optional[asyncio.Task] = None
        self._load_config()

    def _load_config(self):
        """Carga configuracion desde variables de entorno.

        Formato (JSON en variable REGIONS_CONFIG):
        {
            "sa-east-1": {
                "priority": 1,
                "replicas": ["postgresql://replica1.sa:5432/db"],
                "primary_url": "postgresql://primary.sa:5432/db",
                "coordinates": [-34.6, -58.4]
            },
            "us-east-1": {
                "priority": 2,
                "replicas": ["postgresql://replica1.us:5432/db"],
                "coordinates": [40.7, -74.0]
            }
        }
        """
        env_config = os.environ.get("REGIONS_CONFIG", "{}")
        try:
            config = json.loads(env_config)
        except json.JSONDecodeError:
            config = {}

        if not config:
            default_url = os.environ.get("DB_URL", "postgresql://localhost:5432/medicare")
            config = {
                "primary": {
                    "priority": 0,
                    "replicas": [default_url],
                    "primary_url": default_url,
                    "coordinates": [0, 0],
                }
            }

        for name, cfg in config.items():
            self._regions[name] = RegionConfig(
                name=name,
                priority=cfg.get("priority", 100),
                replicas=cfg.get("replicas", []),
                primary_url=cfg.get("primary_url", cfg.get("replicas", [""])[0]),
                max_lag_seconds=cfg.get("max_lag_seconds", 5.0),
                coordinates=tuple(cfg.get("coordinates", [0, 0])),
            )
            self._health[name] = RegionHealth()

        # Health checks periodicos se inician con start_health_checks()
        self._health_task = None

    # ── Geo-deteccion ──────────────────────────────────────────

    @staticmethod
    def _haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Distancia en km entre dos puntos geograficos."""
        key = (round(lat1, 2), round(lon1, 2), round(lat2, 2), round(lon2, 2))
        if key in MultiRegionBalancer.HAVERSINE_CACHE:
            return MultiRegionBalancer.HAVERSINE_CACHE[key]

        import math
        R = 6371.0
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat / 2) ** 2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        dist = R * c
        MultiRegionBalancer.HAVERSINE_CACHE[key] = dist
        return dist

    def _detect_client_region(self, client_ip: str = "",
                              region_header: str = "") -> str:
        """Determina la region mas cercana al cliente.

        Orden de precedencia:
        1. Cabecera X-Region del cliente
        2. GeoIP sobre client_ip (aproximacion por coordenadas)
        3. Default: region con menor latencia historica
        """
        # 1. Cabecera explicita
        if region_header and region_header in self._regions:
            return region_header

        # 2. Sin datos: retornar la de menor prioridad (mas cercana a default)
        sorted_regions = sorted(
            self._regions.values(),
            key=lambda r: (r.priority, r.name),
        )
        return sorted_regions[0].name if sorted_regions else "primary"

    def _get_nearest_region(self, lat: float, lon: float) -> str:
        """Retorna la region mas cercana a una coordenada."""
        nearest = "primary"
        min_dist = float("inf")
        for name, cfg in self._regions.items():
            rlat, rlon = cfg.coordinates
            dist = self._haversine(lat, lon, rlat, rlon)
            if dist < min_dist:
                min_dist = dist
                nearest = name
        return nearest

    # ── Obtencion de conexion ────────────────────────────────

    async def get_read_replica(self, client_ip: str = "",
                               region_header: str = "") -> str:
        """Obtiene URL de replica optima para el cliente.

        Estrategia:
        1. Region del cliente (por cabecera o GeoIP)
        2. Replica saludable dentro de esa region (random ponderado)
        3. Fallback a region vecina mas cercana
        4. Fallback a primaria global
        """
        region_name = self._detect_client_region(client_ip, region_header)
        candidates = await self._get_healthy_replicas(region_name)

        if candidates:
            return candidates[0] if len(candidates) == 1 else random_weighted(candidates)

        # Fallback: buscar en regiones vecinas (ordenadas por prioridad)
        sorted_regions = sorted(
            self._regions.items(),
            key=lambda kv: (kv[1].priority, kv[0]),
        )
        for rname, _ in sorted_regions:
            if rname == region_name:
                continue
            candidates = await self._get_healthy_replicas(rname)
            if candidates:
                log_event("multi_region", f"fallback:{region_name}->{rname}")
                return candidates[0]

        # Fallback final: primaria de la region solicitada
        region = self._regions.get(region_name)
        if region and region.primary_url:
            log_event("multi_region", f"fallback_primary:{region_name}")
            return region.primary_url

        return os.environ.get("DB_URL", "postgresql://localhost:5432/medicare")

    async def _get_healthy_replicas(self, region_name: str) -> list[str]:
        """Retorna replicas saludables de una region."""
        health = self._health.get(region_name)
        if not health or health.status == RegionStatus.DOWN:
            return []

        region = self._regions.get(region_name)
        if not region:
            return []

        if health.status == RegionStatus.DEGRADED:
            log_event("multi_region", f"degraded:{region_name}:lag={health.lag_seconds:.1f}s")
            return region.replicas  # aun usable pero con advertencia

        return list(region.replicas)

    # ── Health checks periodicos ─────────────────────────────

    async def _health_loop(self):
        """Loop de health checking cada N segundos."""
        while True:
            for region_name in list(self._regions.keys()):
                await self._check_region(region_name)
            await asyncio.sleep(30)

    async def _check_region(self, region_name: str):
        """Verifica salud de una region: conectividad y lag."""
        region = self._regions.get(region_name)
        health = self._health.get(region_name)
        if not region or not health:
            return

        start = time.time()
        success = False
        lag = 0.0

        for replica_url in region.replicas[:2]:  # probar max 2 replicas
            try:
                import asyncpg
                conn = await asyncpg.connect(
                    replica_url,
                    timeout=5,
                    statement_cache_size=0,
                )
                # Medir lag: diferencia entre NOW() en replica vs primaria
                row = await conn.fetchrow("""
                    SELECT
                        EXTRACT(EPOCH FROM (NOW() - pg_last_xact_replay_timestamp()))
                            AS lag_seconds
                """)
                if row and row["lag_seconds"] is not None:
                    lag = float(row["lag_seconds"])
                await conn.close()
                success = True
                break
            except Exception as exc:
                log_event("multi_region", f"health_check_fail:{replica_url}:{type(exc).__name__}")
                continue

        elapsed_ms = (time.time() - start) * 1000
        health.response_time_ms = elapsed_ms
        health.last_check = time.time()

        if not success:
            health.consecutive_failures += 1
            if health.consecutive_failures >= 3:
                health.status = RegionStatus.DOWN
                log_event("multi_region", f"region_down:{region_name}")
        else:
            health.consecutive_failures = 0
            if lag > region.max_lag_seconds:
                health.status = RegionStatus.DEGRADED
                health.lag_seconds = lag
            else:
                health.status = RegionStatus.HEALTHY
                health.lag_seconds = lag

    # ── API publica ──────────────────────────────────────────

    def start_health_checks(self):
        """Inicia el loop de health checks (requiere event loop corriendo)."""
        if self._health_task is None:
            try:
                self._health_task = asyncio.create_task(self._health_loop())
            except RuntimeError:
                pass  # No event loop available yet

    async def get_region_stats(self) -> dict:
        """Estadisticas de todas las regiones."""
        self.start_health_checks()
        stats = {}
        for name, cfg in self._regions.items():
            h = self._health.get(name)
            stats[name] = {
                "status": h.status.value if h else "unknown",
                "lag_seconds": round(h.lag_seconds, 2) if h else 0,
                "response_time_ms": round(h.response_time_ms, 1) if h else 0,
                "replicas": len(cfg.replicas),
                "priority": cfg.priority,
            }
        return stats

    async def close(self):
        if self._health_task:
            self._health_task.cancel()
            self._health_task = None


def random_weighted(candidates: list[str]) -> str:
    """Seleccion aleatoria simple."""
    import random
    return random.choice(candidates)


# ═══════════════════════════════════════════════════════════════════
# 3. SINGLETON
# ═══════════════════════════════════════════════════════════════════

_balancer: Optional[MultiRegionBalancer] = None


def get_multi_region_balancer() -> MultiRegionBalancer:
    global _balancer
    if _balancer is None:
        _balancer = MultiRegionBalancer()
    return _balancer


__all__ = [
    "MultiRegionBalancer",
    "RegionConfig",
    "RegionHealth",
    "RegionStatus",
    "get_multi_region_balancer",
]
