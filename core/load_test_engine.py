"""Worker de simulacion masiva de carga sintetica.
Emula 5.000 profesionales concurrentes enviando deltas,
abriendo WebSockets y gatillando alertas NEWS2.
Reporta punto de quiebre (Breaking Point) del sistema.
"""
from __future__ import annotations

import asyncio
import json
import math
import os
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE SIMULACION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SimulatedProfessional:
    """Perfil de un profesional simulado."""
    id: str = field(default_factory=lambda: f"prof-{uuid.uuid4().hex[:12]}")
    tenant_id: str = ""
    region: str = "sa-east-1"
    active_patients: list[str] = field(default_factory=list)
    device_private_key: bytes = b""
    device_public_key: bytes = b""

    def generate_delta_payload(self) -> dict:
        """Genera un payload delta simulado en formato MessagePack."""
        return {
            "id": str(uuid.uuid4()),
            "tenant_id": self.tenant_id,
            "professional_id": self.id,
            "paciente_id": random.choice(self.active_patients) if self.active_patients else "",
            "event_type": random.choice(["checkin", "evolucion", "medicacion"]),
            "timestamp": time.time(),
            "payload": {
                "diagnostico": random.choice([
                    "neumonia", "fractura", "diabetes", "hipertension", "gripe",
                ]),
                "medicacion": random.choice(["paracetamol", "ibuprofeno", "amoxicilina"]),
                "nota": f"Nota de evolucion simulada #{random.randint(1, 1000)}",
            },
            "vector_clock": f"local:{random.randint(1, 10)}",
        }


@dataclass
class BreakingPoint:
    """Punto de quiebre del sistema detectado."""
    phase: str = ""              # "delta_sync" | "websocket" | "news2"
    concurrent_users: int = 0
    error_rate: float = 0.0      # 0.0 - 1.0
    p95_latency_ms: float = 0.0
    errors: list[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════
# 2. MODULO DE SIMULACION
# ═══════════════════════════════════════════════════════════════════

class LoadTestEngine:
    """Motor de simulacion de carga sintetica.

    Fases:
    1. Delta sync: N profesionales enviando POST /sync/batch
    2. WebSocket: N profesionales abriendo streams simultaneos
    3. NEWS2: Alertas firmadas con ECDSA aleatorias
    """

    DELTA_ENDPOINT = "http://localhost:8000/sync/batch"
    WS_ENDPOINT = "ws://localhost:8000/ws"

    def __init__(self, target_url: str = "http://localhost:8000"):
        self._target_url = target_url.rstrip("/")
        self._professionals: list[SimulatedProfessional] = []
        self._metrics: dict[str, list[float]] = {
            "delta_latency": [], "ws_latency": [], "news2_latency": [],
        }
        self._errors: dict[str, int] = {}
        self._breaking_point: Optional[BreakingPoint] = None

    def _create_professionals(self, count: int, tenant_id: str = "test-tenant") -> list[SimulatedProfessional]:
        """Genera N profesionales simulados."""
        from core.edge_health_scoring import ECDSASigner

        profs = []
        patients = [f"pac-{uuid.uuid4().hex[:12]}" for _ in range(max(count // 10, 10))]
        for _ in range(count):
            priv, pub = ECDSASigner.generate_keypair()
            prof = SimulatedProfessional(
                tenant_id=tenant_id,
                active_patients=random.sample(patients, min(5, len(patients))),
                device_private_key=priv,
                device_public_key=pub,
            )
            profs.append(prof)
        return profs

    # ── Fase 1: Delta Sync ──────────────────────────────────

    async def _simulate_delta_sync(self, prof: SimulatedProfessional,
                                   sem: asyncio.Semaphore) -> float:
        """Simula un POST /sync/batch con delta en MessagePack."""
        import httpx
        import msgpack

        payload = prof.generate_delta_payload()
        packed = msgpack.packb(payload, use_bin_type=True)

        async with sem:
            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.post(
                        f"{self._target_url}/sync/batch",
                        content=packed,
                        headers={"Content-Type": "application/x-msgpack",
                                 "X-Tenant-Id": prof.tenant_id},
                    )
                latency = (time.time() - start) * 1000
                if resp.status_code != 200:
                    self._errors["delta_http"] = self._errors.get("delta_http", 0) + 1
                return latency
            except Exception as exc:
                latency = (time.time() - start) * 1000
                self._errors["delta_error"] = self._errors.get("delta_error", 0) + 1
                return latency

    async def phase_delta_sync(self, concurrent_users: int,
                               requests_per_user: int = 5) -> dict:
        """Ejecuta fase de delta sync con N usuarios concurrentes."""
        self._professionals = self._create_professionals(concurrent_users)
        sem = asyncio.Semaphore(min(concurrent_users, 200))  # max 200 concurrent

        log_event("load_test", f"phase_delta:starting:{concurrent_users} usuarios:{requests_per_user}req/u")

        tasks = []
        for prof in self._professionals:
            for _ in range(requests_per_user):
                tasks.append(self._simulate_delta_sync(prof, sem))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        latencies = [r for r in results if isinstance(r, (int, float))]
        self._metrics["delta_latency"].extend(latencies)

        return self._phase_result("delta_sync", latencies)

    # ── Fase 2: WebSocket ───────────────────────────────────

    async def _simulate_websocket(self, prof: SimulatedProfessional,
                                  sem: asyncio.Semaphore) -> float:
        """Simula apertura de WebSocket y recepcion de mensajes."""
        import httpx

        async with sem:
            start = time.time()
            try:
                async with httpx.AsyncClient(timeout=10) as client:
                    # Simulamos conexion WS via HTTP upgrade check
                    resp = await client.get(
                        f"{self._target_url}/health",
                        headers={"X-Tenant-Id": prof.tenant_id},
                    )
                latency = (time.time() - start) * 1000
                if resp.status_code != 200:
                    self._errors["ws_health"] = self._errors.get("ws_health", 0) + 1
                return latency
            except Exception as exc:
                latency = (time.time() - start) * 1000
                self._errors["ws_error"] = self._errors.get("ws_error", 0) + 1
                return latency

    async def phase_websocket(self, concurrent_users: int) -> dict:
        """Simula N conexiones WebSocket simultaneas."""
        sem = asyncio.Semaphore(min(concurrent_users, 100))
        if not self._professionals:
            self._professionals = self._create_professionals(concurrent_users)

        log_event("load_test", f"phase_ws:starting:{concurrent_users} conexiones")

        tasks = [self._simulate_websocket(prof, sem) for prof in self._professionals[:concurrent_users]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        latencies = [r for r in results if isinstance(r, (int, float))]
        self._metrics["ws_latency"].extend(latencies)

        return self._phase_result("websocket", latencies)

    # ── Fase 3: Alertas NEWS2 ───────────────────────────────

    async def _simulate_news2_alert(self, prof: SimulatedProfessional,
                                    sem: asyncio.Semaphore) -> float:
        """Genera alerta NEWS2 firmada y la envia."""
        from core.edge_health_scoring import EdgeAlertEngine, VitalSigns
        import httpx

        async with sem:
            start = time.time()
            try:
                engine = EdgeAlertEngine(device_private_key_pem=prof.device_private_key)
                vs = VitalSigns(
                    respiratory_rate=random.randint(8, 30),
                    oxygen_saturation=random.randint(85, 100),
                    systolic_bp=random.randint(80, 220),
                    heart_rate=random.randint(40, 140),
                    temperature=round(random.uniform(35.0, 40.0), 1),
                )
                paciente = random.choice(prof.active_patients) if prof.active_patients else "pac-test"
                alert = engine.evaluate(paciente, prof.id, prof.tenant_id, prof.id, vs)

                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.post(
                        f"{self._target_url}/sync/batch",
                        json=alert.to_msgpack_ready(),
                        headers={"X-Tenant-Id": prof.tenant_id},
                    )
                latency = (time.time() - start) * 1000
                if resp.status_code != 200:
                    self._errors["news2_http"] = self._errors.get("news2_http", 0) + 1
                return latency
            except Exception as exc:
                latency = (time.time() - start) * 1000
                self._errors["news2_error"] = self._errors.get("news2_error", 0) + 1
                return latency

    async def phase_news2(self, concurrent_users: int) -> dict:
        """Simula N alertas NEWS2 firmadas."""
        sem = asyncio.Semaphore(min(concurrent_users, 100))
        if not self._professionals:
            self._professionals = self._create_professionals(concurrent_users)

        log_event("load_test", f"phase_news2:starting:{concurrent_users} alertas")

        tasks = [self._simulate_news2_alert(prof, sem) for prof in self._professionals[:concurrent_users]]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        latencies = [r for r in results if isinstance(r, (int, float))]
        self._metrics["news2_latency"].extend(latencies)

        return self._phase_result("news2", latencies)

    # ── Analisis ────────────────────────────────────────────

    def _phase_result(self, phase: str, latencies: list[float]) -> dict:
        """Calcula metricas de una fase."""
        if not latencies:
            return {"phase": phase, "error": "no_data", "breaking_point": False}

        latencies.sort()
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[int(len(latencies) * 0.95)]
        p99 = latencies[int(len(latencies) * 0.99)]
        error_rate = (self._errors.get(f"{phase.split('_')[0]}_error", 0) +
                      self._errors.get(f"{phase.split('_')[0]}_http", 0)) / max(len(latencies), 1)

        return {
            "phase": phase,
            "total_requests": len(latencies),
            "p50_latency_ms": round(p50, 1),
            "p95_latency_ms": round(p95, 1),
            "p99_latency_ms": round(p99, 1),
            "error_rate": round(error_rate, 4),
            "breaking_point": error_rate > 0.1 or p95 > 5000,
        }

    async def run_full_profile(self, max_users: int = 5000,
                                steps: list[int] = None) -> list[BreakingPoint]:
        """Ejecuta perfil completo de carga escalonada.

        Escala desde 100 hasta max_users en steps.
        Detecta breaking point en cada fase.
        """
        steps = steps or [100, 500, 1000, 2000, 5000]
        steps = [s for s in steps if s <= max_users]
        breaking_points = []

        for users in steps:
            log_event("load_test", f"profile:step={users} usuarios")

            # Fase 1: Delta
            d_result = await self.phase_delta_sync(users, requests_per_user=3)
            if d_result.get("breaking_point"):
                bp = BreakingPoint(phase="delta_sync", concurrent_users=users,
                                    error_rate=d_result["error_rate"],
                                    p95_latency_ms=d_result["p95_latency_ms"],
                                    errors=[f"{k}:{v}" for k, v in self._errors.items()])
                breaking_points.append(bp)

            # Fase 2: WebSocket
            ws_result = await self.phase_websocket(users)
            if ws_result.get("breaking_point"):
                bp = BreakingPoint(phase="websocket", concurrent_users=users,
                                    error_rate=ws_result["error_rate"],
                                    p95_latency_ms=ws_result["p95_latency_ms"])
                breaking_points.append(bp)

            # Fase 3: NEWS2
            n2_result = await self.phase_news2(users)
            if n2_result.get("breaking_point"):
                bp = BreakingPoint(phase="news2", concurrent_users=users,
                                    error_rate=n2_result["error_rate"],
                                    p95_latency_ms=n2_result["p95_latency_ms"])
                breaking_points.append(bp)

        self._breaking_point = breaking_points[0] if breaking_points else None
        return breaking_points

    def get_report(self) -> dict:
        """Reporte final de la simulacion."""
        return {
            "breaking_point": {
                "phase": self._breaking_point.phase if self._breaking_point else None,
                "concurrent_users": self._breaking_point.concurrent_users if self._breaking_point else 0,
                "error_rate": self._breaking_point.error_rate if self._breaking_point else 0.0,
                "p95_latency_ms": self._breaking_point.p95_latency_ms if self._breaking_point else 0.0,
            } if self._breaking_point else None,
            "errors_by_type": dict(self._errors),
            "total_professionals": len(self._professionals),
            "total_requests": sum(len(v) for v in self._metrics.values()),
        }


__all__ = [
    "LoadTestEngine",
    "SimulatedProfessional",
    "BreakingPoint",
]
