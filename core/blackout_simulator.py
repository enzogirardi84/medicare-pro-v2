"""Motor de Simulacion de Apagon Planetario (Blackout Simulator).
Desconecta todo: APIs, K8s, Postgres, 5G, satelite.
Mide supervivencia de datos bajo el peor escenario posible.
"""
from __future__ import annotations

import asyncio
import random
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DEL APAGON
# ═══════════════════════════════════════════════════════════════════

class InfrastructureLayer(Enum):
    PREPAGA_API = "prepaga_api"           # APIs de Avalian, Sancor, Premedic
    KUBERNETES = "kubernetes"             # pods caidos
    POSTGRES = "postgres"                 # corrupcion fisica
    CELLULAR = "cellular"                 # 5G/4G caido
    SATELLITE = "satellite"               # Starlink caido
    MESH_NETWORK = "mesh_network"         # red P2P
    WEBHOOK_POOL = "webhook_pool"         # workers de webhook
    EVENT_STORE = "event_store"           # tablas clinicas


@dataclass
class BlackoutScenario:
    """Configuracion de un escenario de apagon."""
    name: str = "Planetary Blackout"
    prepaga_apis_down: bool = True
    kubernetes_pods_loss_pct: float = 0.95
    postgres_bitrot_pct: float = 0.01       # 1% de filas corruptas
    cellular_down: bool = True
    satellite_down: bool = True
    mesh_active: bool = True                # la red P2P siempre sobrevive
    ambulances_count: int = 1000
    duration_seconds: float = 300.0         # 5 min de apagon


@dataclass
class DataSurvivalReport:
    """Reporte de supervivencia de datos tras el apagon."""
    total_packets_sent: int = 0
    packets_delivered: int = 0
    delivery_rate: float = 0.0
    mesh_hops_avg: float = 0.0
    postgres_corruption_pct: float = 0.0
    kubernetes_survival_pct: float = 0.0
    critical_alerts_survived: int = 0
    total_critical_alerts: int = 0
    duration_seconds: float = 0.0
    overall_resilience_score: float = 0.0


# ═══════════════════════════════════════════════════════════════════
# 2. SIMULADOR DE APAGON
# ═══════════════════════════════════════════════════════════════════

class BlackoutSimulator:
    """Simulador de apagon de infraestructura planetaria.

    Escenario:
    - APIs de prepagas caidas
    - 95% de pods de K8s destruidos
    - 1% de corrupcion por bit-rot en Postgres
    - Red 5G y satelital caidas
    - 1.000 ambulancias virtuales en movimiento SIN internet
    - Solo la red Mesh P2P sobrevive
    """

    def __init__(self):
        self._scenario = BlackoutScenario()
        self._report = DataSurvivalReport()
        self._packets: list[dict] = []
        self._survived: list[dict] = []

    def configure(self, scenario: BlackoutScenario):
        """Configura el escenario de apagon."""
        self._scenario = scenario

    # ── Fase 1: Generar trafico pre-apagon ────────────────

    def _generate_pre_blackout_traffic(self) -> list[dict]:
        """Genera paquetes de datos clinicos antes del apagon."""
        packets = []
        for i in range(self._scenario.ambulances_count):
            packet = {
                "id": str(uuid.uuid4()),
                "ambulance_id": f"amb-{i:04d}",
                "tipo": random.choice(["ecg_alert", "vitals", "news2", "eeg_state"]),
                "payload": {"hr": random.randint(40, 180), "spo2": random.randint(85, 100)},
                "critical": random.random() < 0.15,  # 15% son alertas criticas
                "vector_clock": f"amb-{i:04d}:{random.randint(1,5)}",
                "created_at": time.time(),
                "source_lat": random.uniform(-35.0, -30.0),
                "source_lon": random.uniform(-65.0, -58.0),
            }
            packets.append(packet)
        return packets

    # ── Fase 2: Aplicar apagon ───────────────────────────

    def _apply_kubernetes_chaos(self, packets: list[dict]) -> list[dict]:
        """Destruye aleatoriamente el 95% de los pods."""
        survival_count = int(len(packets) * (1 - self._scenario.kubernetes_pods_loss_pct))
        survived = random.sample(packets, max(survival_count, 1))
        self._report.kubernetes_survival_pct = (1 - self._scenario.kubernetes_pods_loss_pct) * 100
        log_event("blackout", f"k8s_chaos:{len(packets)}->{len(survived)} survivors ({self._report.kubernetes_survival_pct:.0f}%)")
        return survived

    def _apply_postgres_corruption(self, packets: list[dict]) -> list[dict]:
        """Corrompe aleatoriamente el checksum de paquetes."""
        corrupted = 0
        for p in packets:
            if random.random() < self._scenario.postgres_bitrot_pct:
                p["checksum_corrupted"] = True
                corrupted += 1
        self._report.postgres_corruption_pct = self._scenario.postgres_bitrot_pct * 100
        log_event("blackout", f"bitrot:{corrupted}/{len(packets)} corruptos ({self._report.postgres_corruption_pct:.1f}%)")
        return packets

    def _apply_network_chaos(self, packets: list[dict]) -> list[dict]:
        """Aísla los paquetes: sin 5G, sin satélite. Solo mesh P2P."""
        survived = []
        for p in packets:
            # Sin conectividad: los datos solo viajan por mesh P2P
            # Simular perdida de paquetes en mesh (30% de perdida tipica)
            if random.random() < 0.7:  # 70% de entrega en mesh
                survived.append(p)
        log_event("blackout", f"network_chaos:{len(packets)}->{len(survived)} mesh survivors")
        return survived

    # ── Fase 3: Simular propagacion Mesh P2P ─────────────

    def _simulate_mesh_propagation(self, packets: list[dict]) -> list[dict]:
        """Simula propagacion de paquetes via mesh P2P.

        Cada paquete salta de nodo a nodo hasta alcanzar
        un HUB sobreviviente. 10 hops maximo.
        """
        delivered = []
        for p in packets:
            hops = random.randint(1, 10)
            # Cada hop tiene 90% de probabilidad de exito
            success = True
            for _ in range(hops):
                if random.random() < 0.1:  # 10% de perdida por hop
                    success = False
                    break
            if success:
                p["mesh_hops"] = hops
                delivered.append(p)

        self._report.mesh_hops_avg = (
            sum(p.get("mesh_hops", 0) for p in delivered) / max(len(delivered), 1)
        )
        log_event("blackout", f"mesh_propagation:{len(packets)}->{len(delivered)} delivered (avg {self._report.mesh_hops_avg:.1f} hops)")
        return delivered

    # ── Fase 4: Reporte de resiliencia ───────────────────

    def _compute_report(self, original: list[dict], delivered: list[dict]) -> DataSurvivalReport:
        """Calcula el reporte de resiliencia."""
        total = len(original)
        if total == 0:
            return DataSurvivalReport()

        delivered_ids = {p["id"] for p in delivered}
        critical_original = [p for p in original if p.get("critical")]
        critical_delivered = [p for p in delivered if p.get("critical")]

        report = DataSurvivalReport(
            total_packets_sent=total,
            packets_delivered=len(delivered),
            delivery_rate=round(len(delivered) / total * 100, 1),
            mesh_hops_avg=round(self._report.mesh_hops_avg, 1),
            postgres_corruption_pct=round(self._report.postgres_corruption_pct, 1),
            kubernetes_survival_pct=round(self._report.kubernetes_survival_pct, 1),
            critical_alerts_survived=len(critical_delivered),
            total_critical_alerts=len(critical_original),
            duration_seconds=self._scenario.duration_seconds,
            overall_resilience_score=round(
                (len(delivered) / total * 0.4 +          # entrega general
                 len(critical_delivered) / max(len(critical_original), 1) * 0.4 +  # alertas criticas
                 (1 - self._report.postgres_corruption_pct / 100) * 0.1 +  # integridad
                 self._report.kubernetes_survival_pct / 100 * 0.1) * 100,  # supervivencia k8s
                1,
            ),
        )
        return report

    async def run(self) -> DataSurvivalReport:
        """Ejecuta la simulacion de apagon completa."""
        print("=" * 60)
        print("BLACKOUT SIMULATOR — MediCare PRO v2.4.0")
        print(f"Scenario: {self._scenario.name}")
        print(f"  Ambulances: {self._scenario.ambulances_count}")
        print(f"  K8s loss: {self._scenario.kubernetes_pods_loss_pct * 100}%")
        print(f"  Bit-rot: {self._scenario.postgres_bitrot_pct * 100}%")
        print(f"  5G/Satellite: {'DOWN' if self._scenario.cellular_down else 'UP'}")
        print(f"  Mesh P2P: {'ACTIVE' if self._scenario.mesh_active else 'DOWN'}")
        print("=" * 60)

        # Fase 1: Trafico pre-apagon
        print("\n[FASE 1] Generando trafico clinico...")
        original = self._generate_pre_blackout_traffic()
        print(f"  {len(original)} paquetes generados")
        print(f"  {sum(1 for p in original if p['critical'])} alertas criticas")

        # Fase 2: Apagon
        print("\n[FASE 2] APAGON TOTAL DE INFRAESTRUCTURA")
        print(f"  Caida de APIs de prepagas... {'OK' if self._scenario.prepaga_apis_down else 'SKIP'}")
        print(f"  Destruyendo pods de Kubernetes...")

        survived_k8s = self._apply_kubernetes_chaos(original)
        print(f"  Pods supervivientes: {len(survived_k8s)}/{len(original)}")

        print(f"  Inyectando bit-rot en Postgres...")
        survived_db = self._apply_postgres_corruption(survived_k8s)

        print(f"  Cortando 5G y satelite...")
        survived_mesh = self._apply_network_chaos(survived_db)
        print(f"  Paquetes en mesh P2P: {len(survived_mesh)}")

        # Fase 3: Propagacion mesh
        print(f"\n[FASE 3] Propagando por red Mesh P2P...")
        delivered = self._simulate_mesh_propagation(survived_mesh)

        # Fase 4: Reporte
        print(f"\n[FASE 4] Reporte de resiliencia...")
        report = self._compute_report(original, delivered)
        self._report = report

        print("\n" + "=" * 60)
        print("REPORTE DE RESILIENCIA — Blackout Survival")
        print("=" * 60)
        print(f"  Paquetes enviados:      {report.total_packets_sent}")
        print(f"  Paquetes entregados:    {report.packets_delivered}")
        print(f"  Tasa de entrega:        {report.delivery_rate}%")
        print(f"  Hops promedio mesh:     {report.mesh_hops_avg}")
        print(f"  Corrupcion Postgres:    {report.postgres_corruption_pct}%")
        print(f"  Supervivencia K8s:      {report.kubernetes_survival_pct}%")
        print(f"  Alertas criticas total: {report.total_critical_alerts}")
        print(f"  Alertas criticas vivas: {report.critical_alerts_survived}")
        print(f"  Duracion apagon:        {report.duration_seconds}s")
        print(f"  PUNTAJE DE RESILIENCIA: {report.overall_resilience_score}/100")
        print("=" * 60)

        return report


__all__ = [
    "BlackoutSimulator",
    "BlackoutScenario",
    "DataSurvivalReport",
    "InfrastructureLayer",
]
