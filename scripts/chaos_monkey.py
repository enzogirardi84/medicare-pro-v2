#!/usr/bin/env python3
"""Chaos Monkey - Inyeccion de fallas controlada para validar resiliencia.
Simula caidas de S3, microcortes de red, latencia alta en DB.
"""
from __future__ import annotations

import asyncio
import logging
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. PLAN DE CAOS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ChaosAction:
    """Una accion de caos a ejecutar."""
    tipo: str  # "s3_failover" | "network_latency" | "db_timeout" | "random_500"
    probabilidad: float = 0.3  # 0-1
    duracion_ms: int = 2000
    activo: bool = True


@dataclass
class ChaosPlan:
    """Plan de caos para una prueba."""
    experimento_id: str = field(default_factory=lambda: f"chaos_{int(time.time())}")
    acciones: list[ChaosAction] = field(default_factory=lambda: [
        ChaosAction("s3_failover", 0.3, 5000),
        ChaosAction("network_latency", 0.4, 1500),
        ChaosAction("db_timeout", 0.2, 8000),
        ChaosAction("random_500", 0.1, 100),
    ])
    intervalo_seg: int = 10
    duracion_total_seg: int = 120
    dry_run: bool = True


# ═══════════════════════════════════════════════════════════════════
# 2. INYECTORES DE FALLAS
# ═══════════════════════════════════════════════════════════════════

class S3FailoverInjector:
    """Simula caida del bucket S3 primario para forzar failover a R2/local."""

    @staticmethod
    async def inject(plan: ChaosPlan) -> bool:
        if plan.dry_run:
            log_event("chaos", "[DRY_RUN] S3 failover simulado")
            return True

        log_event("chaos", "INYECTANDO: S3 failover - cortando bucket primario")
        # En produccion: modificar temporalmente la config S3 del worker
        # para que apunte a un endpoint inexistente
        old_endpoint = os.environ.get("S3_ENDPOINT", "")
        os.environ["S3_ENDPOINT"] = "https://bucket-inexistente.chaos.local"
        await asyncio.sleep(plan.acciones[0].duracion_ms / 1000)
        os.environ["S3_ENDPOINT"] = old_endpoint
        log_event("chaos", "S3 failover restaurado")
        return True


class NetworkLatencyInjector:
    """Simula latencia alta en conexiones a PostgreSQL."""

    @staticmethod
    async def inject(plan: ChaosPlan) -> bool:
        log_event("chaos", f"INYECTANDO: latencia de red {plan.acciones[1].duracion_ms}ms")
        await asyncio.sleep(plan.acciones[1].duracion_ms / 1000)
        return True


class DBTimeoutInjector:
    """Simula timeout en consultas a la base de datos."""

    @classmethod
    async def inject(cls, plan: ChaosPlan) -> bool:
        from core.tenant_repository import DBConfig
        cfg = DBConfig()

        if plan.dry_run:
            log_event("chaos", "[DRY_RUN] DB timeout simulado")
            return True

        log_event("chaos", f"INYECTANDO: DB timeout {plan.acciones[2].duracion_ms}ms")
        old_timeout = cfg.statement_timeout_ms
        try:
            # Simular alterando el timeout a 1ms (causara timeout)
            cfg.statement_timeout_ms = 1
            await asyncio.sleep(2)
            return True
        finally:
            cfg.statement_timeout_ms = old_timeout


# ═══════════════════════════════════════════════════════════════════
# 3. EJECUTOR DE CAOS
# ═══════════════════════════════════════════════════════════════════

class ChaosMonkey:
    """Ejecuta un plan de caos, inyectando fallas aleatorias.

    Uso:
        plan = ChaosPlan(dry_run=False)
        monkey = ChaosMonkey(plan)
        resultados = await monkey.ejecutar()
    """

    INYECTORES = {
        "s3_failover": S3FailoverInjector,
        "network_latency": NetworkLatencyInjector,
        "db_timeout": DBTimeoutInjector,
        "random_500": None,
    }

    def __init__(self, plan: Optional[ChaosPlan] = None):
        self.plan = plan or ChaosPlan()
        self.resultados: list[dict[str, Any]] = []
        self._detener = False

    async def ejecutar(self) -> list[dict[str, Any]]:
        """Ejecuta el plan de caos completo."""
        log_event("chaos", f"Iniciando experimento: {self.plan.experimento_id}")
        log_event("chaos", f"Duracion: {self.plan.duracion_total_seg}s, Dry-run: {self.plan.dry_run}")

        inicio = time.time()
        while time.time() - inicio < self.plan.duracion_total_seg:
            if self._detener:
                break

            for accion in self.plan.acciones:
                if not accion.activo:
                    continue
                if random.random() > accion.probabilidad:
                    continue

                inyector = self.INYECTORES.get(accion.tipo)
                if inyector is None:
                    continue

                try:
                    t0 = time.perf_counter()
                    ok = await inyector.inject(self.plan)
                    dt = (time.perf_counter() - t0) * 1000
                    self.resultados.append({
                        "accion": accion.tipo,
                        "ok": ok,
                        "duracion_ms": round(dt, 1),
                        "timestamp": time.time(),
                    })
                except Exception as exc:
                    self.resultados.append({
                        "accion": accion.tipo,
                        "ok": False,
                        "error": str(exc)[:100],
                    })

            await asyncio.sleep(self.plan.intervalo_seg)

        log_event("chaos", f"Experimento {self.plan.experimento_id} finalizado")
        return self.resultados

    def detener(self) -> None:
        self._detener = True

    def reporte(self) -> dict[str, Any]:
        total = len(self.resultados)
        ok = sum(1 for r in self.resultados if r.get("ok"))
        return {
            "experimento_id": self.plan.experimento_id,
            "total_inyecciones": total,
            "exitosas": ok,
            "fallidas": total - ok,
            "tasa_exito": f"{ok / max(total, 1) * 100:.0f}%",
            "acciones": self.resultados,
        }


async def main():
    plan = ChaosPlan(dry_run=True, duracion_total_seg=30)
    monkey = ChaosMonkey(plan)
    await monkey.ejecutar()
    report = monkey.reporte()
    print(f"Experimento: {report['experimento_id']}")
    print(f"Inyecciones: {report['exitosas']}/{report['total_inyecciones']} exitosas")
    for r in report["acciones"][:5]:
        print(f"  {r['accion']}: OK={r.get('ok')} ({r.get('duracion_ms', 'N/A')}ms)")


if __name__ == "__main__":
    asyncio.run(main())
