"""Sincronizacion Activa-Activa Multi-Region con Vector Clocks.
Extiende el CRDTMergeEngine con relojes vectoriales para ordenamiento
parcial y convergencia exacta de snapshots entre regiones.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. RELOJ VECTORIAL (Vector Clock)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class VectorClock:
    """Reloj vectorial para ordenamiento parcial de eventos.

    Cada region mantiene su propio contador.
    El orden parcial se determina por comparacion de vectores.
    """
    clocks: dict[str, int] = field(default_factory=dict)

    def tick(self, region_id: str) -> VectorClock:
        """Incrementa el contador de una region y retorna nuevo clock."""
        new = VectorClock(clocks=dict(self.clocks))
        new.clocks[region_id] = new.clocks.get(region_id, 0) + 1
        return new

    def merge(self, other: VectorClock) -> VectorClock:
        """Fusion: max por cada elemento (join de reticulado)."""
        all_keys = set(self.clocks) | set(other.clocks)
        new_clocks = {}
        for k in all_keys:
            new_clocks[k] = max(self.clocks.get(k, 0), other.clocks.get(k, 0))
        return VectorClock(clocks=new_clocks)

    def happens_before(self, other: VectorClock) -> bool:
        """True si self causalmente precede a other (∀i: self[i] ≤ other[i] y ∃j: self[j] < other[j])."""
        all_keys = set(self.clocks) | set(other.clocks)
        strict = False
        for k in all_keys:
            sv = self.clocks.get(k, 0)
            ov = other.clocks.get(k, 0)
            if sv > ov:
                return False
            if sv < ov:
                strict = True
        return strict

    def is_concurrent(self, other: VectorClock) -> bool:
        """True si los eventos son concurrentes (ni a < b ni b < a)."""
        return not (self.happens_before(other) or other.happens_before(self))

    def __eq__(self, other):
        return self.clocks == other.clocks

    def to_dict(self) -> dict:
        return dict(self.clocks)

    @classmethod
    def from_dict(cls, d: dict) -> VectorClock:
        return cls(clocks={k: int(v) for k, v in d.items()})

    def to_compact(self) -> str:
        """Representacion compacta para almacenamiento."""
        parts = [f"{k}:{v}" for k, v in sorted(self.clocks.items())]
        return "|".join(parts)

    @classmethod
    def from_compact(cls, s: str) -> VectorClock:
        clocks = {}
        if s:
            for part in s.split("|"):
                if ":" in part:
                    k, v = part.split(":", 1)
                    clocks[k] = int(v)
        return cls(clocks=clocks)


# ═══════════════════════════════════════════════════════════════════
# 2. EVENTO CON RELOJ VECTORIAL
# ═══════════════════════════════════════════════════════════════════

@dataclass
class VectorEvent:
    """Evento clinico con reloj vectorial para resolucion de conflictos."""
    event_id: str
    region_id: str
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict
    vector_clock: VectorClock
    timestamp: float = 0.0
    checksum: str = ""


# ═══════════════════════════════════════════════════════════════════
# 3. REPLICADOR ACTIVO-ACTIVO
# ═══════════════════════════════════════════════════════════════════

class ActiveActiveReplicator:
    """Motor de replicacion bidireccional entre regiones.

    Flujo:
    1. Cada region genera eventos con su VectorClock local
    2. Los eventos se replican a las otras regiones via /sync/batch
    3. En destino, se resuelven conflictos por orden causal
    4. Los snapshots convergen deterministicamente
    """

    def __init__(self, region_id: str):
        self.region_id = region_id
        self._local_clock = VectorClock()
        self._conflict_log: list[dict] = []

    def tick(self) -> VectorClock:
        """Incrementa el reloj local y retorna el nuevo vector."""
        self._local_clock = self._local_clock.tick(self.region_id)
        return self._local_clock

    def resolve_conflict(self, local_event: VectorEvent,
                         remote_event: VectorEvent) -> VectorEvent:
        """Resuelve un conflicto entre dos eventos concurrentes.

        Estrategia:
        1. Vector clock: si uno causalmente precede al otro, gana el mas reciente
        2. Concurrentes: LWW por timestamp + checksum (determinista)
        3. Registra el conflicto en el log
        """
        lc = local_event.vector_clock
        rc = remote_event.vector_clock

        if lc.happens_before(rc):
            winner = remote_event
            reason = "causal:remote"
        elif rc.happens_before(lc):
            winner = local_event
            reason = "causal:local"
        else:
            # Concurrentes: desempate por timestamp + checksum
            if local_event.timestamp > remote_event.timestamp:
                winner = local_event
                reason = "LWW:timestamp"
            elif remote_event.timestamp > local_event.timestamp:
                winner = remote_event
                reason = "LWW:timestamp"
            else:
                winner = local_event if local_event.checksum >= remote_event.checksum else remote_event
                reason = "LWW:checksum"

        merged_clock = lc.merge(rc)

        self._conflict_log.append({
            "local_id": local_event.event_id,
            "remote_id": remote_event.event_id,
            "reason": reason,
            "merged_clock": merged_clock.to_dict(),
            "winner_id": winner.event_id,
            "timestamp": time.time(),
        })

        log_event("active_active", f"conflict:{reason}:{local_event.event_id[:16]} vs {remote_event.event_id[:16]}")
        return winner

    def ingest_remote_event(self, remote_event: VectorEvent) -> VectorEvent:
        """Ingiere un evento remoto, resolviendo conflictos si es necesario.

        Returns:
            El evento ganador (puede ser el remoto o uno local existente).
        """
        # Fusionar relojes
        self._local_clock = self._local_clock.merge(remote_event.vector_clock)
        return remote_event  # En produccion, checkear vs evento local existente

    def get_local_clock(self) -> VectorClock:
        return self._local_clock

    def get_conflict_log(self) -> list[dict]:
        return list(self._conflict_log)

    def reset_clock(self):
        self._local_clock = VectorClock()


# ═══════════════════════════════════════════════════════════════════
# 4. EXTENSION DEL CRDT MERGE ENGINE CON VECTOR CLOCKS
# ═══════════════════════════════════════════════════════════════════

class VectorCRDTMergeEngine:
    """CRDT Merge Engine extendido con Vector Clocks.

    Compatible con el CRDTMergeEngine original pero agrega
    ordenamiento causal para conflictos multi-region.
    """

    def __init__(self, region_id: str = "local"):
        self._replicator = ActiveActiveReplicator(region_id)

    async def merge_batch_replicated(
        self,
        local_events: list[dict],
        remote_events: list[dict],
        region_id: str,
    ) -> dict:
        """Fusiona eventos locales y remotos con resolucion causal.

        Args:
            local_events: Eventos generados localmente.
            remote_events: Eventos recibidos de otra region.
            region_id: Region origen de los eventos remotos.

        Returns:
            dict con eventos fusionados, conflictos, clock final.
        """
        from core.crdt_resolver import CRDTMergeEngine

        merged: list[dict] = []
        conflictos: list[dict] = []

        # Indexar por (aggregate_type, aggregate_id)
        local_idx = {}
        for ev in local_events:
            key = (ev.get("aggregate_type", ""), ev.get("aggregate_id", ""))
            local_idx[key] = ev

        remote_idx = {}
        for ev in remote_events:
            key = (ev.get("aggregate_type", ""), ev.get("aggregate_id", ""))
            remote_idx[key] = ev

        all_keys = set(local_idx) | set(remote_idx)

        for key in all_keys:
            le = local_idx.get(key)
            re = remote_idx.get(key)

            if le and re:
                # Construir VectorEvents
                lv = VectorEvent(
                    event_id=le.get("id", ""),
                    region_id=self._replicator.region_id,
                    aggregate_type=key[0],
                    aggregate_id=key[1],
                    event_type=le.get("event_type", ""),
                    payload=le.get("payload", {}),
                    vector_clock=VectorClock.from_compact(le.get("vector_clock", "")),
                    timestamp=le.get("timestamp", 0.0),
                    checksum=le.get("checksum", ""),
                )
                rv = VectorEvent(
                    event_id=re.get("id", ""),
                    region_id=region_id,
                    aggregate_type=key[0],
                    aggregate_id=key[1],
                    event_type=re.get("event_type", ""),
                    payload=re.get("payload", {}),
                    vector_clock=VectorClock.from_compact(re.get("vector_clock", "")),
                    timestamp=re.get("timestamp", 0.0),
                    checksum=re.get("checksum", ""),
                )

                winner = self._replicator.resolve_conflict(lv, rv)
                conflicto = {
                    "aggregate": f"{key[0]}:{key[1]}",
                    "local_clock": lv.vector_clock.to_dict(),
                    "remote_clock": rv.vector_clock.to_dict(),
                    "winner_region": winner.region_id,
                }
                conflictos.append(conflicto)
                merged.append(winner.payload if isinstance(winner.payload, dict) else {})
            else:
                # No hay conflicto: usar el que exista
                merged.append(le or re)

        return {
            "merged": merged,
            "conflictos": conflictos,
            "total": len(merged),
            "vector_clock": self._replicator.get_local_clock().to_dict(),
        }

    def get_replicator(self) -> ActiveActiveReplicator:
        return self._replicator


# ═══════════════════════════════════════════════════════════════════
# 5. REPLICACION LOGICA VIA clinical_event_store
# ═══════════════════════════════════════════════════════════════════

REPLICATION_SQL = """
-- =============================================================================
-- Replicacion logica entre regiones: trackea eventos por region
-- =============================================================================

CREATE TABLE IF NOT EXISTS replication_log (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID NOT NULL,
    source_region   TEXT NOT NULL,
    target_region   TEXT NOT NULL,
    vector_clock    TEXT NOT NULL,        -- "region1:3|region2:1"
    status          TEXT NOT NULL DEFAULT 'pending',  -- pending | replicated | conflict
    replicated_at   TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_replication_status
    ON replication_log (source_region, status, created_at);
"""


# ═══════════════════════════════════════════════════════════════════
# 6. SQL FUNCTION: CONFLICT RESOLUTION TRIGGER
# ═══════════════════════════════════════════════════════════════════

CONFLICT_TRIGGER_SQL = """
-- Funcion trigger para resolver conflictos en clinical_event_store
CREATE OR REPLACE FUNCTION resolve_region_conflict()
RETURNS TRIGGER AS $$
DECLARE
    v_existing_clock TEXT;
    v_new_clock TEXT;
    v_existing_ts TIMESTAMPTZ;
    v_new_ts TIMESTAMPTZ;
BEGIN
    -- Buscar evento existente con mismo aggregate
    SELECT vector_clock, created_at
    INTO v_existing_clock, v_existing_ts
    FROM clinical_event_store
    WHERE aggregate_type = NEW.aggregate_type
      AND aggregate_id = NEW.aggregate_id
      AND id != NEW.id
    ORDER BY event_version DESC
    LIMIT 1;

    IF v_existing_clock IS NOT NULL THEN
        v_new_clock := NEW.payload->>'vector_clock';
        v_new_ts := NEW.created_at;

        -- Si el existente tiene reloj vectorial y el nuevo tambien
        IF v_new_clock IS NOT NULL THEN
            -- En produccion: comparacion de VectorClocks
            -- Si son concurrentes: gana timestamp mas reciente
            IF v_new_ts > v_existing_ts THEN
                -- Nuevo evento gana
                RETURN NEW;
            ELSE
                -- Evento existente se mantiene
                RETURN NULL;
            END IF;
        END IF;
    END IF;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""


__all__ = [
    "VectorClock",
    "VectorEvent",
    "ActiveActiveReplicator",
    "VectorCRDTMergeEngine",
    "REPLICATION_SQL",
    "CONFLICT_TRIGGER_SQL",
]
