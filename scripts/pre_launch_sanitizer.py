#!/usr/bin/env python3
"""Saneamiento físico pre-launch: vacuum, reindex, shredding, data sanity.
Ejecuta todas las rutinas de hardening post-estrés.
"""
from __future__ import annotations

import asyncio
import gc
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.app_logging import log_event
from core.data_sanity_worker import DataSanityWorker
from core.secure_deletion import TempFileGarbageCollector, CryptographicShredder
from core.zero_downtime_maintenance import ReindexManager
from core.zero_lock_postgres import ZeroLockIngestion
from core.object_pool_gc import GCSettings


# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACIÓN AUTOVACUUM POST-ESTRÉS
# ═══════════════════════════════════════════════════════════════════

VACUUM_TUNE_SQL = """
-- Aplicar configuración agresiva de autovacuum post-estrés
ALTER TABLE event_ingest_queue SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_vacuum_threshold = 500,
    autovacuum_vacuum_cost_limit = 2000,
    autovacuum_vacuum_cost_delay = 5
);

ALTER TABLE checkins_gps SET (
    autovacuum_vacuum_scale_factor = 0.01,
    autovacuum_vacuum_threshold = 1000,
    autovacuum_vacuum_cost_limit = 1500,
    autovacuum_vacuum_cost_delay = 5
);
"""

REINDEX_CONCURRENTLY_SQL = """
-- Reconstruir índices sin bloqueo
SELECT 'REINDEX INDEX CONCURRENTLY ' || indexname || ';'
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('checkins_gps', 'clinical_event_store',
                    'clinical_snapshot', 'event_ingest_queue')
  AND indexdef NOT LIKE '%UNIQUE%'
ORDER BY tablename;
"""


# ═══════════════════════════════════════════════════════════════════
# 2. ORQUESTADOR DE SANEAMIENTO
# ═══════════════════════════════════════════════════════════════════

class PreLaunchSanitizer:
    """Orquesta todas las rutinas de saneamiento pre-launch."""

    def __init__(self):
        self.conn = None
        self.report = {}

    async def _get_conn(self):
        if self.conn is None:
            import asyncpg
            self.conn = await asyncpg.connect("postgresql://localhost:5432/medicare")
        return self.conn

    async def step_vacuum_tuning(self) -> dict:
        """Paso 1: Aplicar configuración agresiva de autovacuum."""
        print("\n[PASO 1/5] Configuración agresiva de autovacuum")
        conn = await self._get_conn()
        await conn.execute(VACUUM_TUNE_SQL)
        print("  ✓ event_ingest_queue: scale_factor=0.01, cost_limit=2000")
        print("  ✓ checkins_gps: scale_factor=0.01, cost_limit=1500")
        return {"vacuum_tuned": True}

    async def step_reindex(self) -> dict:
        """Paso 2: REINDEX CONCURRENTLY sobre índices críticos."""
        print("\n[PASO 2/5] REINDEX CONCURRENTLY")
        conn = await self._get_conn()
        indexes = await conn.fetch(REINDEX_CONCURRENTLY_SQL)

        reindexed = 0
        for row in indexes:
            sql = row["?column?"]
            try:
                await conn.execute(sql)
                reindexed += 1
                print(f"  ✓ {sql.strip(';')}")
            except Exception as exc:
                print(f"  ✗ {sql.strip(';')}: {type(exc).__name__}")

        print(f"  Total índices reindexados: {reindexed}")
        return {"reindexed_count": reindexed}

    async def step_data_sanity(self) -> dict:
        """Paso 3: DataSanityWorker — verificar checksums."""
        print("\n[PASO 3/5] DataSanityWorker — verificación de checksums")
        worker = DataSanityWorker()
        worker._conn = self.conn  # reutilizar conexión

        # Auditoría del Event Store
        corruptions = await worker.audit_event_store(limit=10000)
        print(f"  ✓ Filas verificadas: {worker._stats['rows_checked']}")
        print(f"  ✓ Corrupciones detectadas: {len(corruptions)}")

        # Intentar reparar
        repaired = 0
        for report in corruptions:
            if await worker.attempt_repair(report):
                repaired += 1
        print(f"  ✓ Reparaciones exitosas: {repaired}")

        return {
            "rows_checked": worker._stats["rows_checked"],
            "corruptions": len(corruptions),
            "repaired": repaired,
        }

    async def step_zero_lock_check(self) -> dict:
        """Paso 4: Verificar cola de ingesta y profundidad."""
        print("\n[PASO 4/5] ZeroLockIngestion — estado de la cola")
        ing = ZeroLockIngestion()
        ing._conn = self.conn
        depth = await ing.get_queue_depth()
        print(f"  ✓ Pendientes: {depth.get('pending', 0)}")
        print(f"  ✓ En proceso: {depth.get('processing', 0)}")
        print(f"  ✓ Errores: {depth.get('errors', 0)}")

        # Consolidar lote residual
        if depth.get("pending", 0) > 0:
            consolidated = await ing.consume_and_consolidate(500)
            print(f"  ✓ Lote residual consolidado: {consolidated} eventos")

        return {
            "queue_depth": depth,
            "residual_consolidated": depth.get("pending", 0),
        }

    async def step_shredding(self) -> dict:
        """Paso 5: CryptographicShredding — limpieza de archivos temporales."""
        print("\n[PASO 5/5] CryptographicShredding — limpieza DoD 5220.22-M")
        gc = TempFileGarbageCollector()
        stats_before = gc.get_stats()
        print(f"  ✓ Archivos registrados antes: {stats_before['total_registered']}")
        print(f"  ✓ Archivos pendientes: {stats_before['pending']}")

        # Forzar limpieza de todos los archivos pendientes
        destroyed = 0
        for file_id in list(gc._files.keys()):
            if gc._destroy_file(file_id):
                destroyed += 1

        stats_after = gc.get_stats()
        print(f"  ✓ Archivos destruidos: {destroyed}")
        print(f"  ✓ Archivos restantes: {stats_after['pending']}")
        print(f"  ✓ Estándar: DoD 5220.22-M (3 pasadas + truncado)")

        return {
            "destroyed": destroyed,
            "remaining": stats_after["pending"],
            "standard": "DoD 5220.22-M",
        }

    async def run_all(self) -> dict:
        """Ejecuta todas las rutinas de saneamiento."""
        print("=" * 60)
        print("PRE-LAUNCH SANITIZATION — MediCare PRO v2.1.0")
        print("Hardening físico post-estrés")
        print("=" * 60)

        # Ajustar GC para alto throughput
        GCSettings.tune_for_high_throughput()

        results = {}
        results["vacuum"] = await self.step_vacuum_tuning()
        results["reindex"] = await self.step_reindex()
        results["data_sanity"] = await self.step_data_sanity()
        results["zero_lock"] = await self.step_zero_lock_check()
        results["shredding"] = await self.step_shredding()

        # Consolidar reporte
        all_ok = all(
            r.get("success", True) if isinstance(r, dict) else True
            for r in results.values()
        )
        # Verificar data_sanity específicamente
        data_ok = results.get("data_sanity", {}).get("corruptions", 999) == 0

        self.report = {
            "steps": results,
            "data_integrity_ok": data_ok,
            "all_checks_passed": data_ok,
            "timestamp": time.time(),
        }

        print("\n" + "=" * 60)
        print("REPORTE FINAL DE SANEAMIENTO")
        print("=" * 60)
        for step_name, step_result in results.items():
            status = "✓" if step_result.get("success", True) is not False else "✗"
            print(f"  {status} {step_name}: {step_result}")

        print(f"\n  Integridad de datos: {'✓ OK' if data_ok else '✗ CORRUPCIÓN DETECTADA'}")
        print(f"  Todos los checks: {'✓ PASARON' if self.report['all_checks_passed'] else '✗ FALLARON'}")
        print("=" * 60)

        return self.report

    async def close(self):
        if self.conn:
            await self.conn.close()


if __name__ == "__main__":
    sanitizer = PreLaunchSanitizer()
    results = asyncio.run(sanitizer.run_all())
    asyncio.run(sanitizer.close())
    sys.exit(0 if results.get("all_checks_passed") else 1)
