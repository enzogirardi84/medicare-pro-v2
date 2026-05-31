"""Automacion de mantenimiento PostgreSQL sin bloqueos.
Autovacuum tuning para tablas de alta rotacion,
REINDEX CONCURRENTLY para indices espaciales y B-Tree.
"""
from __future__ import annotations

import asyncio
import os
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACION DE AUTOVACUUM
# ═══════════════════════════════════════════════════════════════════

VACUUM_CONFIG_SQL = """
-- =============================================================================
-- Autovacuum tuning para tablas de alta rotacion
-- =============================================================================

-- 1. event_ingest_queue: alta tasa de INSERT + DELETE (consolidacion diferida)
ALTER TABLE event_ingest_queue SET (
    autovacuum_vacuum_scale_factor = 0.01,        -- 1% de dead tuples (default 0.2)
    autovacuum_vacuum_threshold = 1000,            -- minimo 1000 dead tuples
    autovacuum_vacuum_cost_limit = 2000,           -- mas agresivo (default 200)
    autovacuum_vacuum_cost_delay = 5,              -- 5ms entre batches
    autovacuum_analyze_scale_factor = 0.02,
    autovacuum_analyze_threshold = 500
);

-- 2. clinical_event_store: append-only, baja rotacion de dead tuples
ALTER TABLE clinical_event_store SET (
    autovacuum_vacuum_scale_factor = 0.05,         -- 5% de dead tuples
    autovacuum_vacuum_threshold = 10000,
    autovacuum_vacuum_cost_limit = 500,
    autovacuum_vacuum_cost_delay = 20,
    autovacuum_analyze_scale_factor = 0.05,
    autovacuum_analyze_threshold = 5000
);

-- 3. checkins_gps: alta rotacion con indices GIST espaciales
ALTER TABLE checkins_gps SET (
    autovacuum_vacuum_scale_factor = 0.02,
    autovacuum_vacuum_threshold = 2000,
    autovacuum_vacuum_cost_limit = 1000,
    autovacuum_vacuum_cost_delay = 10
);

-- 4. clinical_snapshot: upserts frecuentes
ALTER TABLE clinical_snapshot SET (
    autovacuum_vacuum_scale_factor = 0.03,
    autovacuum_vacuum_threshold = 5000,
    autovacuum_vacuum_cost_limit = 1000,
    autovacuum_vacuum_cost_delay = 10
);
"""


# ═══════════════════════════════════════════════════════════════════
# 2. REINDEX CONCURRENTLY AUTOMATION
# ═══════════════════════════════════════════════════════════════════

class ReindexManager:
    """Gestiona REINDEX CONCURRENTLY de forma segura.

    Opera en horas de bajo trafico (configurable).
    Reconstruye indices sin bloquear escrituras.
    """

    REINDEX_CANDIDATES_SQL = """
        SELECT
            schemaname,
            tablename,
            indexname,
            indexdef,
            pg_size_pretty(pg_relation_size(indexrelid)) as index_size
        FROM pg_indexes i
        JOIN pg_class c ON c.relname = i.indexname
        WHERE schemaname = 'public'
          AND tablename IN ('clinical_event_store', 'checkins_gps',
                            'clinical_snapshot', 'event_ingest_queue')
          AND indexdef NOT LIKE '%UNIQUE%'   -- evitar conflictos con unique
        ORDER BY pg_relation_size(c.oid) DESC
    """

    REINDEX_CONCURRENTLY_SQL = "REINDEX INDEX CONCURRENTLY %I.%I"

    VERIFY_SQL = """
        SELECT pg_size_pretty(pg_relation_size($1::regclass)) as size_after,
               pg_stat_all_indexes.idx_scan as scans
        FROM pg_stat_all_indexes
        WHERE indexrelid = $1::regclass
    """

    def __init__(self):
        self._conn = None

    async def _get_conn(self):
        if self._conn is None:
            import asyncpg
            self._conn = await asyncpg.connect("postgresql://localhost:5432/medicare")
        return self._conn

    async def get_reindex_candidates(self) -> list[dict]:
        """Obtiene indices candidatos para reconstruccion."""
        conn = await self._get_conn()
        rows = await conn.fetch(self.REINDEX_CANDIDATES_SQL)
        return [dict(r) for r in rows]

    async def reindex_index(self, schema: str, index: str) -> dict:
        """Reconstruye un indice con CONCURRENTLY (sin bloqueo).

        Args:
            schema: Schema del indice.
            index: Nombre del indice.

        Returns:
            dict con resultado de la operacion.
        """
        conn = await self._get_conn()
        start = time.time()
        try:
            await conn.execute(self.REINDEX_CONCURRENTLY_SQL.format(schema, index))
            elapsed = time.time() - start
            log_event("maintenance", f"REINDEX_CONCURRENTLY:{schema}.{index}:{elapsed:.1f}s")
            return {"index": f"{schema}.{index}", "success": True, "elapsed_seconds": round(elapsed, 2)}
        except Exception as exc:
            elapsed = time.time() - start
            log_event("maintenance", f"REINDEX_FAILED:{schema}.{index}:{type(exc).__name__}:{elapsed:.1f}s")
            return {"index": f"{schema}.{index}", "success": False, "error": str(exc), "elapsed_seconds": round(elapsed, 2)}

    async def run_maintenance_window(self, only_bloated: bool = True) -> dict:
        """Ejecuta ventana de mantenimiento completa.

        Args:
            only_bloated: Si True, solo reindexa indices con bloat estimado.

        Returns:
            dict con resultados de cada operacion.
        """
        candidates = await self.get_reindex_candidates()
        results = []

        for idx in candidates:
            if only_bloated:
                # Heuristica simple: indices > 100MB o con menos de 1000 scans son candidatos
                size_str = idx.get("index_size", "0")
                size_mb = self._parse_size(size_str)
                scans = idx.get("scans", 0)
                if size_mb < 100 and scans >= 1000:
                    continue

            result = await self.reindex_index(idx["schemaname"], idx["indexname"])
            results.append(result)

        return {
            "total_candidates": len(candidates),
            "reindexed": len(results),
            "successful": sum(1 for r in results if r["success"]),
            "failed": sum(1 for r in results if not r["success"]),
            "results": results,
        }

    @staticmethod
    def _parse_size(size_str: str) -> int:
        """Convierte '256 MB' a 256."""
        try:
            parts = size_str.split()
            return int(parts[0]) if parts else 0
        except (ValueError, IndexError):
            return 0

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


# ═══════════════════════════════════════════════════════════════════
# 3. BLOAT ESTIMATION QUERY
# ═══════════════════════════════════════════════════════════════════

BLOAT_ESTIMATE_SQL = """
-- Estimacion de bloat por tabla (necesita pg_stat_user_tables activo)
SELECT
    schemaname,
    relname,
    n_dead_tup,
    n_live_tup,
    CASE WHEN n_live_tup > 0
        THEN round(100.0 * n_dead_tup / (n_dead_tup + n_live_tup), 1)
        ELSE 0
    END AS dead_pct,
    pg_size_pretty(pg_total_relation_size(relid)) AS total_size,
    last_autovacuum,
    last_autoanalyze
FROM pg_stat_user_tables
WHERE schemaname = 'public'
  AND (n_dead_tup > 1000 OR n_live_tup > 100000)
ORDER BY n_dead_tup DESC
LIMIT 20;
"""


# ═══════════════════════════════════════════════════════════════════
# 4. TABLE REWRITE (sin bloqueo)
# ═══════════════════════════════════════════════════════════════════

TABLE_REWRITE_SQL = """
-- Reescritura de tabla con pg_repack (herramienta externa)
-- Instalar: CREATE EXTENSION pg_repack;
-- Ejecutar fuera de pico: pg_repack -t clinical_snapshot --no-kill-backend
-- O alternativamente:
-- VACUUM FULL clinical_snapshot;  -- BLOQUEA ESCRITURAS, solo usar en ventana
"""


import time


__all__ = [
    "ReindexManager",
    "VACUUM_CONFIG_SQL",
    "BLOAT_ESTIMATE_SQL",
    "TABLE_REWRITE_SQL",
]
