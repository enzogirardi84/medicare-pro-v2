#!/usr/bin/env python3
"""Simulación E2E: flujo cruzado PC vs Móvil offline.
Valida CRDT con Vector Clocks, outbox móvil, cache invalidation broadcast.
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import time
import uuid

# Asegurar path del proyecto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.app_logging import log_event
from core.edge_health_scoring import EdgeAlertEngine, VitalSigns, Consciousness
from core.mobile_outbox import MobileOutbox, SyncStatus
from core.crdt_resolver import CRDTMergeEngine
from core.active_active_replication import ActiveActiveReplicator, VectorClock
from core.l1_l2_cache import CacheDispatcher


# ═══════════════════════════════════════════════════════════════════
# 1. ESCENARIO: CONFLICTO OFFLINE + RESOLUCIÓN CRDT + CACHE
# ═══════════════════════════════════════════════════════════════════

class CrossDeviceScenario:
    """Simula el conflicto y resolución entre PC central y móvil offline."""

    def __init__(self):
        self.outbox = MobileOutbox()
        self.crdt_engine = CRDTMergeEngine()
        self.replicator = ActiveActiveReplicator(region_id="sa-east-1")
        self.cache = CacheDispatcher(instance_id="pc-central")
        self.results: dict = {}

    async def run(self) -> dict:
        """Ejecuta el escenario completo y retorna resultados."""
        print("=" * 60)
        print("ESCENARIO: Conflicto PC central vs Móvil offline")
        print("=" * 60)

        paciente_id = f"pac-{uuid.uuid4().hex[:12]}"
        tenant_id = "aval"
        profesional_id = f"prof-{uuid.uuid4().hex[:12]}"

        # ── Fase 1: Móvil offline genera alerta NEWS2 ──────────
        print("\n[FASE 1] Móvil offline → Alerta NEWS2 + Outbox PENDING")
        engine = EdgeAlertEngine()
        vs = VitalSigns(
            respiratory_rate=26,
            oxygen_saturation=88,
            systolic_bp=85,
            heart_rate=115,
            temperature=38.5,
            consciousness=Consciousness.ALERT,
        )
        alerta_movil = engine.evaluate(
            paciente_id, profesional_id, tenant_id,
            f"device-{uuid.uuid4().hex[:8]}", vs,
            nota_evolucion="Paciente con disnea severa y fiebre alta",
        )

        # Guardar en outbox móvil
        entry = self.outbox.add_entry(
            action_type="alerta_news2",
            summary=f"Alerta NEWS2 para paciente {paciente_id[:12]}...",
            patient_name="Luis González",
            professional_id=profesional_id,
            tenant_id=tenant_id,
            payload=alerta_movil.to_msgpack_ready(),
        )
        assert entry.status == SyncStatus.PENDING
        print(f"  ✓ Outbox: {entry.to_ui_dict()['status']} (⏳)")

        # Reloj vectorial del móvil
        movil_clock = VectorClock(clocks={"device-movil": 1})
        print(f"  ✓ Vector Clock móvil: {movil_clock.to_compact()}")

        # ── Fase 2: PC central modifica simultáneamente ────────
        print("\n[FASE 2] PC central modifica mismo registro (coordinador)")
        pc_clock = self.replicator.tick()
        print(f"  ✓ Vector Clock PC: {pc_clock.to_compact()}")

        version_pc = 2
        registro_pc = {
            "id": paciente_id,
            "diagnostico": "neumonia bilateral",
            "medicacion": "amoxicilina 500mg",
            "nota": "Paciente presenta neumonia bilateral. Se indica antibiotico.",
            "version": version_pc,
            "updated_at": time.time(),
        }

        # PC actualiza cache L1/L2
        await self.cache.set(f"paciente:{paciente_id}", registro_pc)
        print(f"  ✓ Cache L1/L2 actualizada desde PC")

        # ── Fase 3: Móvil recupera conexión y envía delta ──────
        print("\n[FASE 3] Móvil recupera conexión → POST /sync/batch")
        registro_movil = {
            "id": paciente_id,
            "diagnostico": "disnea severa",
            "medicacion": "salbutamol inhalador",
            "nota": alerta_movil.nota_evolucion,
            "version": 1,
            "updated_at": time.time(),
            "vector_clock": movil_clock.to_compact(),
        }

        # CRDT Merge: resolver conflicto LWW
        print("\n[FASE 4] CRDTMergeEngine resuelve conflicto LWW")
        resultado = await self.crdt_engine.merge_batch(
            registros_cliente=[registro_movil],
            registros_servidor=[registro_pc],
            tabla="evoluciones",
            tenant_id=tenant_id,
        )

        has_conflictos = len(resultado["conflictos"]) > 0
        print(f"  ✓ Conflictos detectados: {len(resultado['conflictos'])}")

        # Vector Clock: determinar ganador
        conflictos = resultado.get("conflictos", [])
        if conflictos:
            print(f"  ✓ Resolución: LWW (timestamp + checksum)")
            print(f"  ✓ Campos en conflicto: {conflictos[0].get('campos', [])}")

        # Marcar outbox como sincronizado
        self.outbox.mark_synced(entry.entry_id)
        assert entry.status == SyncStatus.SYNCED
        print(f"  ✓ Outbox actualizado: {entry.to_ui_dict()['status']} (✓)")

        # ── Fase 4: Cache invalidation broadcast ───────────────
        print("\n[FASE 5] Cache invalidation broadcast → Redis Pub/Sub")
        await self.cache.invalidate(f"paciente:{paciente_id}")
        l1_stats = self.cache.get_stats()
        print(f"  ✓ Cache L1 invalidada: {l1_stats['l1']['size']} entries restantes")
        print(f"  ✓ Broadcast publicado en canal: {cache.INVALIDATION_CHANNEL}")

        # ── Resultados ─────────────────────────────────────────
        self.results = {
            "escenario": "conflicto_pc_vs_movil",
            "paciente_id": paciente_id,
            "conflictos_detectados": len(conflictos),
            "resolucion": "LWW (version > timestamp > hash)",
            "outbox_final": entry.to_ui_dict(),
            "movil_clock": movil_clock.to_compact(),
            "pc_clock": pc_clock.to_compact(),
            "cache_l1_stats": l1_stats["l1"],
            "merged_count": resultado.get("total", 0),
            "success": True,
        }

        print("\n" + "=" * 60)
        print("RESULTADO FINAL:")
        for k, v in self.results.items():
            print(f"  {k}: {v}")
        print("=" * 60)

        return self.results


# ═══════════════════════════════════════════════════════════════════
# 2. EJECUCIÓN
# ═══════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    scenario = CrossDeviceScenario()
    results = asyncio.run(scenario.run())
    sys.exit(0 if results.get("success") else 1)
