"""Estrategia Zero-Lock Contention para PostgreSQL.
Append-only estricto con consolidacion diferida, SKIP LOCKED,
y colas de ingestion intermedias desacopladas.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. SQL DE ESQUEMA SIN BLOQUEOS
# ═══════════════════════════════════════════════════════════════════

ZERO_LOCK_SQL = """
-- =============================================================================
-- Zero-Lock Contention: Append-only event ingestion + deferred consolidation
-- =============================================================================

-- 1. COLA DE INGESTION INTERMEDIA (desacoplada de la tabla principal)
CREATE TABLE IF NOT EXISTS event_ingest_queue (
    id              BIGSERIAL PRIMARY KEY,
    aggregate_type  TEXT NOT NULL,
    aggregate_id    TEXT NOT NULL,
    event_type      TEXT NOT NULL,
    tenant_id       UUID NOT NULL,
    actor_id        TEXT NOT NULL,
    payload         JSONB NOT NULL DEFAULT '{}',
    checksum        TEXT NOT NULL DEFAULT '',
    vector_clock    TEXT NOT NULL DEFAULT '',
    source_region   TEXT NOT NULL DEFAULT 'local',
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | processing | done | error
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed_at    TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_eiq_status
    ON event_ingest_queue (status, created_at)
    WHERE status = 'pending';

-- 2. FUNCION: consumir lote con SKIP LOCKED
CREATE OR REPLACE FUNCTION consume_ingest_batch(
    p_batch_size INT DEFAULT 100
) RETURNS TABLE(
    id BIGINT,
    aggregate_type TEXT,
    aggregate_id TEXT,
    event_type TEXT,
    tenant_id UUID,
    actor_id TEXT,
    payload JSONB,
    checksum TEXT,
    vector_clock TEXT,
    source_region TEXT
) AS $$
BEGIN
    RETURN QUERY
    UPDATE event_ingest_queue
    SET status = 'processing', processed_at = NOW()
    WHERE id IN (
        SELECT id FROM event_ingest_queue
        WHERE status = 'pending'
        ORDER BY created_at ASC
        LIMIT p_batch_size
        FOR UPDATE SKIP LOCKED
    )
    RETURNING
        id, aggregate_type, aggregate_id, event_type,
        tenant_id, actor_id, payload, checksum,
        vector_clock, source_region;
END;
$$ LANGUAGE plpgsql;

-- 3. FUNCION: consolidar lote en clinical_event_store (sin triggers!)
CREATE OR REPLACE FUNCTION consolidate_ingest_batch(
    p_batch_ids BIGINT[]
) RETURNS INT AS $$
DECLARE
    v_inserted INT := 0;
    v_event RECORD;
BEGIN
    FOR v_event IN
        SELECT * FROM event_ingest_queue
        WHERE id = ANY(p_batch_ids) AND status = 'processing'
    LOOP
        -- Insert directo en clinical_event_store (SIN TRIGGERS IVM)
        INSERT INTO clinical_event_store (
            aggregate_type, aggregate_id, event_type, event_version,
            tenant_id, actor_id, payload, checksum, created_at
        ) VALUES (
            v_event.aggregate_type, v_event.aggregate_id, v_event.event_type,
            (SELECT COALESCE(MAX(event_version), 0) + 1
             FROM clinical_event_store
             WHERE aggregate_type = v_event.aggregate_type
               AND aggregate_id = v_event.aggregate_id),
            v_event.tenant_id, v_event.actor_id,
            v_event.payload, v_event.checksum, NOW()
        );
        v_inserted := v_inserted + 1;
    END LOOP;

    -- Marcar como procesados
    UPDATE event_ingest_queue
    SET status = 'done', processed_at = NOW()
    WHERE id = ANY(p_batch_ids);

    RETURN v_inserted;
END;
$$ LANGUAGE plpgsql;

-- 4. FUNCION: consolidacion diferida de IVM (fuera de la transaccion critica)
CREATE OR REPLACE FUNCTION deferred_ivm_update(
    p_batch_size INT DEFAULT 500
) RETURNS INT AS $$
DECLARE
    v_count INT := 0;
    v_event RECORD;
BEGIN
    FOR v_event IN
        SELECT * FROM clinical_event_store
        WHERE (aggregate_type, aggregate_id, event_version) IN (
            SELECT aggregate_type, aggregate_id, MAX(event_version)
            FROM clinical_event_store
            WHERE created_at > NOW() - INTERVAL '5 minutes'
            GROUP BY aggregate_type, aggregate_id
        )
        ORDER BY created_at ASC
        LIMIT p_batch_size
    LOOP
        -- Actualizar snapshot solo para el ultimo evento de cada aggregate
        INSERT INTO clinical_snapshot (
            aggregate_type, aggregate_id, tenant_id,
            state, version, checksum, updated_at
        ) VALUES (
            v_event.aggregate_type, v_event.aggregate_id, v_event.tenant_id,
            v_event.payload, v_event.event_version, v_event.checksum, NOW()
        )
        ON CONFLICT (aggregate_type, aggregate_id)
        DO UPDATE SET
            state = EXCLUDED.state,
            version = EXCLUDED.version,
            checksum = EXCLUDED.checksum,
            updated_at = EXCLUDED.updated_at;

        v_count := v_count + 1;
    END LOOP;

    RETURN v_count;
END;
$$ LANGUAGE plpgsql;
"""


# ═══════════════════════════════════════════════════════════════════
# 2. PYTHON WRAPPER — Cola de ingestion sin bloqueos
# ═══════════════════════════════════════════════════════════════════

class ZeroLockIngestion:
    """Cola de ingestion intermedia desacoplada.

    Los eventos se insertan en event_ingest_queue (append-only, sin locks).
    Un worker background consolida en clinical_event_store en batches.
    IVM se ejecuta diferido, fuera de la transaccion critica.
    """

    INSERT_SQL = """
        INSERT INTO event_ingest_queue
            (aggregate_type, aggregate_id, event_type, tenant_id,
             actor_id, payload, checksum, vector_clock, source_region)
        VALUES ($1, $2, $3, $4, $5, $6::jsonb, $7, $8, $9)
    """

    CONSUME_SQL = "SELECT * FROM consume_ingest_batch($1)"

    CONSOLIDATE_SQL = "SELECT consolidate_ingest_batch($1::BIGINT[])"

    IVM_SQL = "SELECT deferred_ivm_update($1)"

    def __init__(self):
        self._conn = None
        self._batch_size = 100

    async def _get_conn(self):
        if self._conn is None:
            import asyncpg
            self._conn = await asyncpg.connect("postgresql://localhost:5432/medicare")
        return self._conn

    async def enqueue_event(self, aggregate_type: str, aggregate_id: str,
                             event_type: str, tenant_id: str, actor_id: str,
                             payload: dict, checksum: str = "",
                             vector_clock: str = "",
                             source_region: str = "local") -> int:
        """Inserta un evento en la cola de ingestion (append-only, sin locks).

        Returns:
            ID de la fila insertada.
        """
        conn = await self._get_conn()
        row = await conn.fetchrow(
            self.INSERT_SQL,
            aggregate_type, aggregate_id, event_type, tenant_id,
            actor_id, json.dumps(payload, default=str), checksum,
            vector_clock, source_region,
        )
        # En postgres con BIGSERIAL, el id se auto-genera
        log_event("zero_lock", f"enqueued:{event_type}:{aggregate_id}")
        return row["id"] if row else 0

    async def consume_and_consolidate(self, batch_size: Optional[int] = None) -> int:
        """Consume un lote de la cola y lo consolida en clinical_event_store.

        Usa SKIP LOCKED para evitar contención entre workers.

        Returns:
            Cantidad de eventos consolidados.
        """
        conn = await self._get_conn()
        bs = batch_size or self._batch_size

        # 1. Consumir lote con SKIP LOCKED
        rows = await conn.fetch(self.CONSUME_SQL, bs)

        if not rows:
            return 0

        batch_ids = [r["id"] for r in rows]

        # 2. Consolidar en clinical_event_store (sin triggers)
        inserted = await conn.fetchval(self.CONSOLIDATE_SQL, batch_ids)

        log_event("zero_lock", f"consolidated:{inserted} eventos")
        return inserted or 0

    async def run_deferred_ivm(self, batch_size: Optional[int] = None) -> int:
        """Ejecuta IVM diferido sobre los ultimos eventos consolidados.

        Debe ejecutarse periodicamente (ej. cada 30s) fuera de la transaccion critica.
        """
        conn = await self._get_conn()
        bs = batch_size or 500
        count = await conn.fetchval(self.IVM_SQL, bs)
        log_event("zero_lock", f"deferred_ivm:{count} snapshots")
        return count or 0

    async def get_queue_depth(self) -> dict:
        """Profundidad actual de la cola."""
        conn = await self._get_conn()
        row = await conn.fetchrow("""
            SELECT
                COUNT(*) FILTER (WHERE status = 'pending') as pending,
                COUNT(*) FILTER (WHERE status = 'processing') as processing,
                COUNT(*) FILTER (WHERE status = 'error') as errors
            FROM event_ingest_queue
        """)
        return dict(row) if row else {"pending": 0, "processing": 0, "errors": 0}

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


__all__ = [
    "ZeroLockIngestion",
    "ZERO_LOCK_SQL",
]
