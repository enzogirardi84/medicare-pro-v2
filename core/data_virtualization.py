"""Virtualizacion de Datos de Auditoria.
Genera archivos SQLite efimeros o dumps JSON encriptados
que contienen exclusivamente los eventos del aggregate consultado,
permitiendo al auditor hacer replay local sin tocar infraestructura central.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import sqlite3
import tempfile
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE EXPORTACION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class AuditExportRequest:
    """Solicitud de exportacion de auditoria."""
    aggregate_type: str
    aggregate_id: str
    tenant_id: str
    include_snapshot: bool = True
    include_lineage: bool = True
    format: str = "sqlite"      # "sqlite" | "json" | "dot"
    auditor_id: str = ""
    reason: str = ""


@dataclass
class AuditExportResult:
    """Resultado de la exportacion."""
    export_id: str = ""
    aggregate_type: str = ""
    aggregate_id: str = ""
    format: str = ""
    checksum: str = ""
    event_count: int = 0
    version: int = 0
    size_bytes: int = 0
    created_at: str = ""
    expires_at: str = ""
    data: Optional[bytes] = None


# ═══════════════════════════════════════════════════════════════════
# 2. MOTOR DE VIRTUALIZACION
# ═══════════════════════════════════════════════════════════════════

class AuditVirtualizationEngine:
    """Genera artefactos de auditoria autocontenidos.

    Uso:
        engine = AuditVirtualizationEngine()
        result = await engine.export_to_sqlite(
            aggregate_type="evolucion",
            aggregate_id="evo-123",
            tenant_id="t1",
        )
        # result.data contiene el bytes del archivo SQLite
        # El auditor puede descargarlo y abrirlo con sqlite3
    """

    SQLITE_EXPORT_TTL = 3600  # 1 hora

    def __init__(self):
        self._conn = None
        self._exports: dict[str, AuditExportResult] = {}

    async def _get_conn(self):
        if self._conn is None:
            import asyncpg
            self._conn = await asyncpg.connect("postgresql://localhost:5432/medicare")
        return self._conn

    async def _fetch_events(self, aggregate_type: str,
                            aggregate_id: str) -> list[dict]:
        """Obtiene todos los eventos de un aggregate desde el event store."""
        conn = await self._get_conn()
        rows = await conn.fetch("""
            SELECT event_type, event_version, tenant_id, actor_id,
                   payload, checksum, prev_event_id, created_at
            FROM clinical_event_store
            WHERE aggregate_type = $1 AND aggregate_id = $2
            ORDER BY event_version ASC
        """, aggregate_type, aggregate_id)
        return [dict(r) for r in rows]

    async def _fetch_snapshot(self, aggregate_type: str,
                              aggregate_id: str) -> Optional[dict]:
        """Obtiene el snapshot actual."""
        conn = await self._get_conn()
        row = await conn.fetchrow("""
            SELECT state, version, checksum, updated_at
            FROM clinical_snapshot
            WHERE aggregate_type = $1 AND aggregate_id = $2
        """, aggregate_type, aggregate_id)
        return dict(row) if row else None

    async def _fetch_lineage(self, aggregate_id: str) -> list[dict]:
        """Obtiene eventos de linaje asociados."""
        from core.data_lineage_engine import DataLineageEngine
        engine = DataLineageEngine()
        graph = await engine.trace_alert(aggregate_id)
        return graph.to_dict()["nodes"]

    @staticmethod
    def _compute_checksum(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()[:32]

    @staticmethod
    def _encrypt_aes(data: bytes, key: Optional[str] = None) -> tuple[bytes, str]:
        """Encripta datos con AES-256-GCM.

        Returns:
            (data_encriptados, key_usada)
        """
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.primitives import hashes

        if key is None:
            key = hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:32]

        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(key.encode()), modes.GCM(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(data) + encryptor.finalize()
        return (iv + encryptor.tag + ciphertext), key

    # ── Exportacion a SQLite ─────────────────────────────────

    async def export_to_sqlite(self, req: AuditExportRequest) -> AuditExportResult:
        """Genera un archivo SQLite efimero con los eventos del aggregate.

        El archivo contiene:
        - Tabla events: todos los eventos del aggregate
        - Tabla snapshot: estado actual (si se solicita)
        - Tabla lineage: nodos de linaje (si se solicita)
        - Vista replay: reconstruccion del estado via SQL
        """
        events = await self._fetch_events(req.aggregate_type, req.aggregate_id)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".audit.db")
        tmp_path = tmp.name
        tmp.close()
        conn = sqlite3.connect(tmp_path)
        cursor = conn.cursor()

        # Tabla de eventos
        cursor.execute("""
            CREATE TABLE events (
                event_version INT,
                event_type TEXT,
                actor_id TEXT,
                payload TEXT,
                checksum TEXT,
                prev_event_id TEXT,
                created_at TEXT
            )
        """)
        for ev in events:
            cursor.execute("""
                INSERT INTO events VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                ev.get("event_version"),
                ev.get("event_type"),
                ev.get("actor_id"),
                json.dumps(ev.get("payload", {}), default=str),
                ev.get("checksum"),
                str(ev.get("prev_event_id") or ""),
                ev.get("created_at").isoformat() if ev.get("created_at") else "",
            ))

        # Snapshot
        if req.include_snapshot:
            snap = await self._fetch_snapshot(req.aggregate_type, req.aggregate_id)
            cursor.execute("CREATE TABLE snapshot (state TEXT, version INT, checksum TEXT)")
            if snap:
                cursor.execute("INSERT INTO snapshot VALUES (?, ?, ?)", (
                    json.dumps(snap.get("state", {}), default=str),
                    snap.get("version"),
                    snap.get("checksum"),
                ))

        # Linaje
        if req.include_lineage:
            try:
                lineage_nodes = await self._fetch_lineage(req.aggregate_id)
                cursor.execute("CREATE TABLE lineage (node_id TEXT, node_type TEXT, label TEXT)")
                for node in lineage_nodes:
                    cursor.execute("INSERT INTO lineage VALUES (?, ?, ?)", (
                        node.get("id", ""),
                        node.get("node_type", ""),
                        node.get("label", ""),
                    ))
            except Exception:
                pass  # lineage es opcional

        # Vista replay
        cursor.execute("""
            CREATE VIEW replay AS
            SELECT event_version, event_type,
                   json(payload) as payload
            FROM events ORDER BY event_version
        """)

        conn.commit()
        conn.close()

        with open(tmp_path, "rb") as f:
            data = f.read()
        os.unlink(tmp_path)
        export_id = str(uuid.uuid4())

        result = AuditExportResult(
            export_id=export_id,
            aggregate_type=req.aggregate_type,
            aggregate_id=req.aggregate_id,
            format="sqlite",
            checksum=self._compute_checksum(data),
            event_count=len(events),
            version=events[-1]["event_version"] if events else 0,
            size_bytes=len(data),
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=datetime.fromtimestamp(
                time.time() + self.SQLITE_EXPORT_TTL, tz=timezone.utc
            ).isoformat(),
            data=data,
        )

        self._exports[export_id] = result
        log_event("audit_virt", f"sqlite_export:{req.aggregate_type}:{req.aggregate_id}:{len(events)} eventos")
        return result

    # ── Exportacion a JSON encriptado ────────────────────────

    async def export_to_encrypted_json(self, req: AuditExportRequest,
                                       encryption_key: Optional[str] = None
                                       ) -> tuple[AuditExportResult, str]:
        """Genera dump JSON encriptado con AES-256-GCM.

        Returns:
            (result, encryption_key)
        """
        events = await self._fetch_events(req.aggregate_type, req.aggregate_id)

        doc = {
            "metadata": {
                "export_id": str(uuid.uuid4()),
                "aggregate_type": req.aggregate_type,
                "aggregate_id": req.aggregate_id,
                "tenant_id": req.tenant_id,
                "event_count": len(events),
                "exported_at": datetime.now(timezone.utc).isoformat(),
                "auditor_id": req.auditor_id,
                "reason": req.reason,
            },
            "events": events,
        }

        if req.include_snapshot:
            snap = await self._fetch_snapshot(req.aggregate_type, req.aggregate_id)
            doc["snapshot"] = snap

        json_bytes = json.dumps(doc, default=str, indent=2).encode("utf-8")
        encrypted, key = self._encrypt_aes(json_bytes, encryption_key)

        export_id = str(uuid.uuid4())
        result = AuditExportResult(
            export_id=export_id,
            aggregate_type=req.aggregate_type,
            aggregate_id=req.aggregate_id,
            format="json.encrypted",
            checksum=self._compute_checksum(json_bytes),
            event_count=len(events),
            version=events[-1]["event_version"] if events else 0,
            size_bytes=len(encrypted),
            created_at=datetime.now(timezone.utc).isoformat(),
            expires_at=datetime.fromtimestamp(
                time.time() + self.SQLITE_EXPORT_TTL, tz=timezone.utc
            ).isoformat(),
            data=encrypted,
        )
        self._exports[export_id] = result
        return result, key

    # ── Verificacion de integridad ──────────────────────────

    def verify_export(self, export_id: str) -> Optional[dict]:
        """Verifica la integridad de una exportacion previa."""
        result = self._exports.get(export_id)
        if not result:
            return None
        actual_checksum = self._compute_checksum(result.data)
        return {
            "valid": actual_checksum == result.checksum,
            "export_id": export_id,
            "expected_checksum": result.checksum,
            "actual_checksum": actual_checksum,
            "size_bytes": result.size_bytes,
            "expires_at": result.expires_at,
        }

    def get_export(self, export_id: str) -> Optional[AuditExportResult]:
        return self._exports.get(export_id)

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


# ═══════════════════════════════════════════════════════════════════
# 3. REPLAY LOCAL (funcion para embedir en el SQLite)
# ═══════════════════════════════════════════════════════════════════

LOCAL_REPLAY_SQL = """
-- Reconstruir estado desde eventos (ejecutar en sqlite3)
-- Copia esta funcion en tu cliente SQLite local:

CREATE TABLE IF NOT EXISTS _replay_state (
    key TEXT PRIMARY KEY,
    value TEXT
);

-- O simplemente:
-- SELECT * FROM events ORDER BY event_version;
-- El auditor puede aplicar los eventos manualmente.
"""


__all__ = [
    "AuditVirtualizationEngine",
    "AuditExportRequest",
    "AuditExportResult",
    "LOCAL_REPLAY_SQL",
]
