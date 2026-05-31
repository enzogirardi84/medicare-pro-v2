"""Mantenimiento Incremental de Snapshots (IVM) para el Event Store.
Triggers PostgreSQL que actualizan clinical_snapshot y tablas
de agregados estadisticos solo con el delta del nuevo evento.
"""
from __future__ import annotations

import json
import time
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. SQL DE TRIGGERS INCREMENTALES
# ═══════════════════════════════════════════════════════════════════

IVM_SQL = """
-- =============================================================================
-- Incremental View Maintenance: actualiza snapshots solo con el delta
-- =============================================================================

-- 1. TABLA DE AGREGADOS EPIDEMIOLOGICOS MENSUALES
CREATE TABLE IF NOT EXISTS agg_epidemiologia_mensual (
    tenant_id       UUID NOT NULL,
    anio_mes        TEXT NOT NULL,      -- '2026-06'
    total_eventos   INT NOT NULL DEFAULT 0,
    total_evoluciones INT NOT NULL DEFAULT 0,
    total_medicaciones INT NOT NULL DEFAULT 0,
    diagnosticos_top JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (tenant_id, anio_mes)
);

-- 2. TABLA DE AGREGADOS POR TIPO DE EVENTO
CREATE TABLE IF NOT EXISTS agg_eventos_por_tipo (
    tenant_id       UUID NOT NULL,
    event_type      TEXT NOT NULL,
    total           INT NOT NULL DEFAULT 0,
    ultimo_evento   TIMESTAMPTZ,
    PRIMARY KEY (tenant_id, event_type)
);

-- 3. FUNCION TRIGGER: actualiza clinical_snapshot incrementalmente
CREATE OR REPLACE FUNCTION ivm_update_snapshot()
RETURNS TRIGGER AS $$
DECLARE
    v_current_state JSONB;
    v_current_version INT;
    v_current_checksum TEXT;
BEGIN
    -- Obtener snapshot actual (si existe)
    SELECT state, version, checksum
    INTO v_current_state, v_current_version, v_current_checksum
    FROM clinical_snapshot
    WHERE aggregate_type = NEW.aggregate_type
      AND aggregate_id = NEW.aggregate_id;

    -- Si no existe, inicializar con empty state
    IF v_current_state IS NULL THEN
        v_current_state := '{}'::jsonb;
        v_current_version := 0;
        v_current_checksum := '';
    END IF;

    -- Aplicar el nuevo evento al estado actual
    v_current_state := apply_event_to_state(v_current_state, NEW.event_type, NEW.payload);

    -- Actualizar checksum encadenado
    v_current_checksum := encode(
        sha256(
            (v_current_checksum || NEW.checksum)::bytea
        ),
        'hex'
    );

    -- Upsert del snapshot
    INSERT INTO clinical_snapshot
        (aggregate_type, aggregate_id, tenant_id, state, version, checksum, updated_at)
    VALUES
        (NEW.aggregate_type, NEW.aggregate_id, NEW.tenant_id,
         v_current_state, NEW.event_version, v_current_checksum, NOW())
    ON CONFLICT (aggregate_type, aggregate_id)
    DO UPDATE SET
        state = EXCLUDED.state,
        version = EXCLUDED.version,
        checksum = EXCLUDED.checksum,
        updated_at = EXCLUDED.updated_at;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 4. FUNCION TRIGGER: actualiza agregados epidemiologicos
CREATE OR REPLACE FUNCTION ivm_update_epidemiologia()
RETURNS TRIGGER AS $$
DECLARE
    v_anio_mes TEXT;
BEGIN
    v_anio_mes := to_char(NEW.created_at, 'YYYY-MM');

    -- Insert o update del agregado mensual
    INSERT INTO agg_epidemiologia_mensual
        (tenant_id, anio_mes, total_eventos, total_evoluciones,
         total_medicaciones, updated_at)
    VALUES
        (NEW.tenant_id, v_anio_mes, 1,
         CASE WHEN NEW.aggregate_type = 'evolucion' THEN 1 ELSE 0 END,
         CASE WHEN NEW.aggregate_type = 'medicacion' THEN 1 ELSE 0 END,
         NOW())
    ON CONFLICT (tenant_id, anio_mes)
    DO UPDATE SET
        total_eventos = agg_epidemiologia_mensual.total_eventos + 1,
        total_evoluciones = agg_epidemiologia_mensual.total_evoluciones +
            CASE WHEN NEW.aggregate_type = 'evolucion' THEN 1 ELSE 0 END,
        total_medicaciones = agg_epidemiologia_mensual.total_medicaciones +
            CASE WHEN NEW.aggregate_type = 'medicacion' THEN 1 ELSE 0 END,
        updated_at = NOW();

    -- Agregado por tipo de evento
    INSERT INTO agg_eventos_por_tipo (tenant_id, event_type, total, ultimo_evento)
    VALUES (NEW.tenant_id, NEW.event_type, 1, NOW())
    ON CONFLICT (tenant_id, event_type)
    DO UPDATE SET
        total = agg_eventos_por_tipo.total + 1,
        ultimo_evento = NOW();

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 5. INSTALAR TRIGGERS
DROP TRIGGER IF EXISTS trg_ivm_snapshot ON clinical_event_store;
CREATE TRIGGER trg_ivm_snapshot
    AFTER INSERT ON clinical_event_store
    FOR EACH ROW
    EXECUTE FUNCTION ivm_update_snapshot();

DROP TRIGGER IF EXISTS trg_ivm_epidemiologia ON clinical_event_store;
CREATE TRIGGER trg_ivm_epidemiologia
    AFTER INSERT ON clinical_event_store
    FOR EACH ROW
    EXECUTE FUNCTION ivm_update_epidemiologia();
"""


# ═══════════════════════════════════════════════════════════════════
# 2. PYTHON WRAPPER — Gestion de triggers
# ═══════════════════════════════════════════════════════════════════

class IncrementalSnapshotManager:
    """Administra los triggers de IVM en PostgreSQL.

    Uso:
        manager = IncrementalSnapshotManager()
        await manager.install_triggers()     # primera instalacion
        await manager.remove_triggers()      # rollback
        await manager.get_snapshot("evolucion", "evo-123")
    """

    INSTALL_SQL = """
        SELECT EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname = 'trg_ivm_snapshot'
        ) AS snapshot_installed,
        EXISTS (
            SELECT 1 FROM pg_trigger
            WHERE tgname = 'trg_ivm_epidemiologia'
        ) AS epi_installed
    """

    def __init__(self):
        self._conn = None

    async def _get_conn(self):
        if self._conn is None:
            import asyncpg
            self._conn = await asyncpg.connect("postgresql://localhost:5432/medicare")
        return self._conn

    async def install_triggers(self) -> dict:
        """Instala tablas de agregados y triggers IVM.

        Returns:
            dict con estado de instalacion.
        """
        conn = await self._get_conn()
        # Ejecutar el schema SQL
        await conn.execute(IVM_SQL)

        # Verificar instalacion
        row = await conn.fetchrow(self.INSTALL_SQL)
        result = {
            "snapshot_trigger": row["snapshot_installed"],
            "epidemiologia_trigger": row["epi_installed"],
        }
        log_event("ivm", f"triggers_installed:{result}")
        return result

    async def remove_triggers(self) -> dict:
        """Remueve los triggers IVM."""
        conn = await self._get_conn()
        await conn.execute("DROP TRIGGER IF EXISTS trg_ivm_snapshot ON clinical_event_store")
        await conn.execute("DROP TRIGGER IF EXISTS trg_ivm_epidemiologia ON clinical_event_store")
        log_event("ivm", "triggers_removed")
        return {"snapshot_removed": True, "epidemiologia_removed": True}

    async def get_snapshot(self, aggregate_type: str, aggregate_id: str) -> Optional[dict]:
        """Obtiene el snapshot actual de un agregado."""
        conn = await self._get_conn()
        row = await conn.fetchrow("""
            SELECT state, version, checksum, updated_at
            FROM clinical_snapshot
            WHERE aggregate_type = $1 AND aggregate_id = $2
        """, aggregate_type, aggregate_id)
        if not row:
            return None
        return {
            "state": json.loads(row["state"]) if isinstance(row["state"], str) else row["state"],
            "version": row["version"],
            "checksum": row["checksum"],
            "updated_at": row["updated_at"].isoformat() if row["updated_at"] else None,
        }

    async def get_monthly_epidemiologia(self, tenant_id: str,
                                        anio_mes: str) -> Optional[dict]:
        """Obtiene agregados epidemiologicos para un mes especifico."""
        conn = await self._get_conn()
        row = await conn.fetchrow("""
            SELECT * FROM agg_epidemiologia_mensual
            WHERE tenant_id = $1 AND anio_mes = $2
        """, tenant_id, anio_mes)
        if not row:
            return None
        return dict(row)

    async def get_event_type_counts(self, tenant_id: str) -> list[dict]:
        """Distribucion de tipos de evento para un tenant."""
        conn = await self._get_conn()
        rows = await conn.fetch("""
            SELECT event_type, total, ultimo_evento
            FROM agg_eventos_por_tipo
            WHERE tenant_id = $1
            ORDER BY total DESC
        """, tenant_id)
        return [dict(r) for r in rows]

    async def refresh_full_snapshot(self, aggregate_type: str, aggregate_id: str) -> dict:
        """Reconstruye snapshot completo desde cero (replay total).

        Usar solo si el trigger se desincroniza.
        """
        from core.clinical_event_store import ClinicalEventStore
        store = ClinicalEventStore()
        replay = await store.replay(aggregate_type, aggregate_id)
        # Actualizar snapshot directamente
        conn = await self._get_conn()
        await conn.execute("""
            INSERT INTO clinical_snapshot
                (aggregate_type, aggregate_id, tenant_id, state, version, checksum, updated_at)
            VALUES ($1, $2,
                COALESCE((SELECT tenant_id FROM clinical_event_store
                    WHERE aggregate_type = $1 AND aggregate_id = $2 LIMIT 1), '00000000-0000-0000-0000-000000000000'),
                $3::jsonb, $4, $5, NOW())
            ON CONFLICT (aggregate_type, aggregate_id)
            DO UPDATE SET
                state = EXCLUDED.state,
                version = EXCLUDED.version,
                checksum = EXCLUDED.checksum,
                updated_at = EXCLUDED.updated_at
        """, aggregate_type, aggregate_id,
             json.dumps(replay["state"], default=str), replay["version"], replay["checksum"])
        log_event("ivm", f"full_refresh:{aggregate_type}:{aggregate_id}:v{replay['version']}")
        return replay

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


# ═══════════════════════════════════════════════════════════════════
# 3. AGREGADOS EN PYTHON (CACHE LADO SERVIDOR)
# ═══════════════════════════════════════════════════════════════════

class AggregatedQueryCache:
    """Cache de consultas agregadas con invalidacion por evento.

    Almacena en memoria los ultimos N resultados de agregados
    para evitar recomputar en caliente.
    """

    def __init__(self, max_size: int = 100):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._max_size = max_size

    def _key(self, query_name: str, tenant_id: str, **params) -> str:
        return f"{query_name}:{tenant_id}:" + json.dumps(params, sort_keys=True)

    def get(self, query_name: str, tenant_id: str, **params) -> Optional[Any]:
        key = self._key(query_name, tenant_id, **params)
        entry = self._cache.get(key)
        if entry:
            ts, value = entry
            if time.time() - ts < 300:  # TTL 5 min
                return value
            del self._cache[key]
        return None

    def set(self, query_name: str, tenant_id: str, value: Any, **params):
        key = self._key(query_name, tenant_id, **params)
        self._cache[key] = (time.time(), value)
        if len(self._cache) > self._max_size:
            oldest = min(self._cache.keys(), key=lambda k: self._cache[k][0])
            del self._cache[oldest]

    def invalidate_tenant(self, tenant_id: str):
        to_delete = [k for k in self._cache if f":{tenant_id}:" in k]
        for k in to_delete:
            del self._cache[k]


__all__ = [
    "IVM_SQL",
    "IncrementalSnapshotManager",
    "AggregatedQueryCache",
]
