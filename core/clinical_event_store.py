"""Event Sourcing para inmutabilidad absoluta del historial clinico.
Cada modificacion se registra como evento atomico en clinical_event_store.
El estado actual se reconstruye via replay de eventos con ventanas nativas PG.
"""
from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. ESQUEMA SQL — clinical_event_store
# ═══════════════════════════════════════════════════════════════════

SCHEMA_SQL = """
-- =============================================================================
-- Event Store para historial clinico inmutable
-- =============================================================================

CREATE TABLE IF NOT EXISTS clinical_event_store (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    aggregate_type  TEXT NOT NULL,        -- 'paciente' | 'evolucion' | 'medicacion'
    aggregate_id    TEXT NOT NULL,         -- ID del registro afectado
    event_type      TEXT NOT NULL,         -- 'EvolucionCreada' | 'EvolucionModificada' | 'MedicationAdministrada' | 'MedicationOmitida'
    event_version   INT NOT NULL DEFAULT 1,
    tenant_id       UUID NOT NULL,
    actor_id        TEXT NOT NULL,         -- profesional_id que realizo el cambio
    payload         JSONB NOT NULL DEFAULT '{}',
    -- Metadatos de auditoria
    checksum        TEXT NOT NULL,         -- SHA256 del payload + event_version anterior
    prev_event_id   UUID,                  -- encadenamiento para integridad referencial
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    CONSTRAINT fk_prev_event FOREIGN KEY (prev_event_id) REFERENCES clinical_event_store(id)
);

-- Indices para replay rapido por paciente
CREATE INDEX IF NOT EXISTS idx_ces_aggregate
    ON clinical_event_store (aggregate_type, aggregate_id, event_version);

-- Indice para busqueda temporal de auditoria
CREATE INDEX IF NOT EXISTS idx_ces_created_at
    ON clinical_event_store (tenant_id, created_at DESC);

-- Indice para encadenamiento (merkle-like)
CREATE INDEX IF NOT EXISTS idx_ces_prev_event
    ON clinical_event_store (prev_event_id) WHERE prev_event_id IS NOT NULL;

-- =============================================================================
-- VISTA MATERIALIZADA: estado actual por agregado (replay pre-calculado)
-- =============================================================================

CREATE TABLE IF NOT EXISTS clinical_snapshot (
    aggregate_type  TEXT NOT NULL,
    aggregate_id    TEXT NOT NULL,
    tenant_id       UUID NOT NULL,
    state           JSONB NOT NULL DEFAULT '{}',
    version         INT NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    checksum        TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (aggregate_type, aggregate_id)
);

-- =============================================================================
-- FUNCION: replay — reconstruye estado actual desde eventos
-- =============================================================================

CREATE OR REPLACE FUNCTION replay_aggregate(
    p_aggregate_type TEXT,
    p_aggregate_id TEXT
) RETURNS TABLE(
    state JSONB,
    version INT,
    checksum TEXT
) AS $$
DECLARE
    v_state JSONB := '{}';
    v_version INT := 0;
    v_checksum TEXT := '';
    v_event RECORD;
BEGIN
    FOR v_event IN
        SELECT event_type, payload, event_version, checksum
        FROM clinical_event_store
        WHERE aggregate_type = p_aggregate_type
          AND aggregate_id = p_aggregate_id
        ORDER BY event_version ASC
    LOOP
        -- Aplicar evento al state actual
        v_state := apply_event_to_state(v_state, v_event.event_type, v_event.payload);
        v_version := v_event.event_version;
        v_checksum := v_event.checksum;
    END LOOP;

    RETURN QUERY SELECT v_state, v_version, v_checksum;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================================================
-- FUNCION: apply_event_to_state — reducer de eventos
-- =============================================================================

CREATE OR REPLACE FUNCTION apply_event_to_state(
    current_state JSONB,
    event_type TEXT,
    payload JSONB
) RETURNS JSONB AS $$
BEGIN
    CASE event_type
        WHEN 'EvolucionCreada' THEN
            -- Inicializar estado con payload completo
            RETURN payload;

        WHEN 'EvolucionModificada' THEN
            -- Merge profundo: payload solo contiene campos cambiados
            RETURN current_state || payload;

        WHEN 'EvolucionEliminada' THEN
            -- Marcar como eliminado
            RETURN current_state || jsonb_build_object('deleted_at', to_char(NOW(), 'YYYY-MM-DD"T"HH24:MI:SS"Z"'));

        WHEN 'MedicationAdministrada' THEN
            -- Agregar administracion al array de medicaciones
            RETURN jsonb_set(
                COALESCE(current_state, '{"medicaciones": []}'::jsonb),
                '{medicaciones}',
                (COALESCE(current_state->'medicaciones', '[]'::jsonb) || payload)
            );

        WHEN 'MedicationOmitida' THEN
            -- Marcar dosis como omitida en el array
            RETURN jsonb_set(
                COALESCE(current_state, '{"medicaciones": []}'::jsonb),
                '{medicaciones}',
                (COALESCE(current_state->'medicaciones', '[]'::jsonb) || payload)
            );

        ELSE
            -- Evento desconocido: retornar sin cambios
            RETURN current_state;
    END CASE;
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- =============================================================================
-- FUNCION: refresh_snapshot — actualiza snapshot desde replay
-- =============================================================================

CREATE OR REPLACE FUNCTION refresh_snapshot(
    p_aggregate_type TEXT,
    p_aggregate_id TEXT
) RETURNS VOID AS $$
DECLARE
    v_state JSONB;
    v_version INT;
    v_checksum TEXT;
BEGIN
    SELECT s.state, s.version, s.checksum
    INTO v_state, v_version, v_checksum
    FROM replay_aggregate(p_aggregate_type, p_aggregate_id) s;

    INSERT INTO clinical_snapshot (aggregate_type, aggregate_id, tenant_id, state, version, checksum, updated_at)
    VALUES (p_aggregate_type, p_aggregate_id, (v_state->>'tenant_id')::UUID, v_state, v_version, v_checksum, NOW())
    ON CONFLICT (aggregate_type, aggregate_id)
    DO UPDATE SET
        state = EXCLUDED.state,
        version = EXCLUDED.version,
        checksum = EXCLUDED.checksum,
        updated_at = EXCLUDED.updated_at;
END;
$$ LANGUAGE plpgsql;
"""


# ═══════════════════════════════════════════════════════════════════
# 2. MODELOS DE EVENTOS CLINICOS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ClinicalEvent:
    """Evento atomico e inmutable del historial clinico."""
    aggregate_type: str
    aggregate_id: str
    event_type: str
    tenant_id: str
    actor_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    event_version: int = 1
    prev_event_id: Optional[str] = None
    checksum: str = ""

    def __post_init__(self):
        if not self.checksum:
            self.checksum = self._compute_checksum()

    def _compute_checksum(self) -> str:
        import hashlib
        raw = json.dumps({
            "aggregate_type": self.aggregate_type,
            "aggregate_id": self.aggregate_id,
            "event_type": self.event_type,
            "event_version": self.event_version,
            "payload": self.payload,
            "prev_event_id": self.prev_event_id,
        }, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    def to_db_tuple(self) -> tuple:
        return (
            self.aggregate_type,
            self.aggregate_id,
            self.event_type,
            self.event_version,
            self.tenant_id,
            self.actor_id,
            json.dumps(self.payload, default=str),
            self.checksum,
            self.prev_event_id,
        )


# ═══════════════════════════════════════════════════════════════════
# 3. CLINICAL EVENT STORE — CLIENTE PYTHON
# ═══════════════════════════════════════════════════════════════════

class ClinicalEventStore:
    """Cliente para el event store clinico.

    Uso:
        store = ClinicalEventStore()
        await store.append_event(ClinicalEvent(...))
        estado = await store.replay("evolucion", "evol-123")
    """

    INSERT_SQL = """
        INSERT INTO clinical_event_store
            (aggregate_type, aggregate_id, event_type, event_version,
             tenant_id, actor_id, payload, checksum, prev_event_id)
        VALUES ($1, $2, $3, $4, $5, $6, $7::jsonb, $8, $9)
        RETURNING id, created_at
    """

    REPLAY_SQL = """
        SELECT event_type, payload, event_version, checksum
        FROM clinical_event_store
        WHERE aggregate_type = $1 AND aggregate_id = $2
        ORDER BY event_version ASC
    """

    SNAPSHOT_UPSERT_SQL = """
        INSERT INTO clinical_snapshot
            (aggregate_type, aggregate_id, tenant_id, state, version, checksum, updated_at)
        VALUES ($1, $2, $3, $4::jsonb, $5, $6, NOW())
        ON CONFLICT (aggregate_type, aggregate_id)
        DO UPDATE SET
            state = EXCLUDED.state,
            version = EXCLUDED.version,
            checksum = EXCLUDED.checksum,
            updated_at = EXCLUDED.updated_at
    """

    def __init__(self):
        self._conn = None

    async def _get_conn(self):
        if self._conn is None:
            import asyncpg
            self._conn = await asyncpg.connect("postgresql://localhost:5432/medicare")
        return self._conn

    async def append_event(self, event: ClinicalEvent) -> dict:
        """Persiste un evento atomico en el store.

        Args:
            event: ClinicalEvent con payload y metadatos.

        Returns:
            dict con id y created_at del evento persistido.
        """
        conn = await self._get_conn()
        row = await conn.fetchrow(self.INSERT_SQL, *event.to_db_tuple())
        log_event("event_store", f"append:{event.event_type}:{event.aggregate_id}:v{event.event_version}")
        return {"id": str(row["id"]), "created_at": row["created_at"].isoformat()}

    async def replay(self, aggregate_type: str, aggregate_id: str) -> dict:
        """Reconstruye el estado actual aplicando todos los eventos en orden.

        Args:
            aggregate_type: Tipo de agregado ('evolucion', 'medicacion', etc.)
            aggregate_id: ID del registro.

        Returns:
            dict con state, version, checksum.
        """
        conn = await self._get_conn()
        rows = await conn.fetch(self.REPLAY_SQL, aggregate_type, aggregate_id)

        state: dict[str, Any] = {}
        version = 0
        checksum = ""

        for row in rows:
            event_type = row["event_type"]
            payload = json.loads(row["payload"])
            version = row["event_version"]
            checksum = row["checksum"]
            state = self._apply(state, event_type, payload)

        return {"state": state, "version": version, "checksum": checksum}

    async def save_snapshot(self, aggregate_type: str, aggregate_id: str,
                            tenant_id: str, state: dict, version: int, checksum: str) -> None:
        """Guarda un snapshot del estado actual para replay rapido."""
        conn = await self._get_conn()
        await conn.execute(
            self.SNAPSHOT_UPSERT_SQL,
            aggregate_type, aggregate_id, tenant_id,
            json.dumps(state, default=str), version, checksum,
        )
        log_event("event_store", f"snapshot:{aggregate_type}:{aggregate_id}:v{version}")

    @staticmethod
    def _apply(state: dict, event_type: str, payload: dict) -> dict:
        """Reducer de eventos puro (sin efectos secundarios)."""
        if event_type == "EvolucionCreada":
            return dict(payload)
        elif event_type == "EvolucionModificada":
            result = dict(state)
            result.update(payload)
            return result
        elif event_type == "EvolucionEliminada":
            result = dict(state)
            result["deleted_at"] = datetime.now(timezone.utc).isoformat()
            return result
        elif event_type in ("MedicationAdministrada", "MedicationOmitida"):
            result = dict(state)
            medicaciones = list(result.get("medicaciones", []))
            medicaciones.append(payload)
            result["medicaciones"] = medicaciones
            return result
        return state

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()
            self._conn = None


# ═══════════════════════════════════════════════════════════════════
# 4. FUNCIONES DE AYUDA PARA CREAR EVENTOS COMUNES
# ═══════════════════════════════════════════════════════════════════

def crear_evento_evolucion(
    evolucion_id: str,
    tenant_id: str,
    actor_id: str,
    accion: str,  # "crear" | "modificar" | "eliminar"
    payload: dict,
    version_actual: int = 0,
) -> ClinicalEvent:
    """Crea un evento de evolucion clinica."""
    event_type_map = {
        "crear": "EvolucionCreada",
        "modificar": "EvolucionModificada",
        "eliminar": "EvolucionEliminada",
    }
    return ClinicalEvent(
        aggregate_type="evolucion",
        aggregate_id=evolucion_id,
        event_type=event_type_map.get(accion, "EvolucionModificada"),
        tenant_id=tenant_id,
        actor_id=actor_id,
        payload=payload,
        event_version=version_actual + 1,
    )


def crear_evento_medicacion(
    administracion_id: str,
    tenant_id: str,
    actor_id: str,
    omitida: bool = False,
    **kwargs,
) -> ClinicalEvent:
    """Crea un evento de administracion/omision de medicacion."""
    event_type = "MedicationOmitida" if omitida else "MedicationAdministrada"
    return ClinicalEvent(
        aggregate_type="medicacion",
        aggregate_id=administracion_id,
        event_type=event_type,
        tenant_id=tenant_id,
        actor_id=actor_id,
        payload=kwargs,
    )


__all__ = [
    "SCHEMA_SQL",
    "ClinicalEvent",
    "ClinicalEventStore",
    "crear_evento_evolucion",
    "crear_evento_medicacion",
]
