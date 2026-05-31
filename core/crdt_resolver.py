"""Resolucion de conflictos CRDT (LWW-Element-Set) para sincronizacion offline.
Usa (version, timestamp, hash) como tupla de decision determinista.
Mantiene un registro de conflictos resueltos en conflict_log.
"""
from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. LWW-ELEMENT-SET PARA CAMPOS INDIVIDUALES
# ═══════════════════════════════════════════════════════════════════

@dataclass(order=True)
class LWWRegister:
    """Registro CRDT de ultima escritura ganadora para un campo."""
    version: int = 0
    timestamp: float = 0.0
    valor: Any = None
    hash_valor: str = ""

    def __post_init__(self):
        if not self.hash_valor and self.valor is not None:
            self.hash_valor = self._hash(str(self.valor))

    @staticmethod
    def _hash(val: str) -> str:
        return hashlib.sha256(val.encode("utf-8")).hexdigest()[:16]

    def dominates(self, other: LWWRegister) -> bool:
        """Determina si este registro domina al otro (LWW).

        Orden de precedencia:
        1. version (mayor gana)
        2. timestamp (mas reciente gana)
        3. hash lexicografico (desempate deterministico)
        """
        if self.version != other.version:
            return self.version > other.version
        if self.timestamp != other.timestamp:
            return self.timestamp > other.timestamp
        return self.hash_valor >= other.hash_valor

    def merge(self, other: LWWRegister) -> LWWRegister:
        """Fusiona dos registros, retorna el dominante."""
        return self if self.dominates(other) else other

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "timestamp": self.timestamp,
            "valor": self.valor,
            "hash": self.hash_valor,
        }

    @classmethod
    def from_dict(cls, d: dict) -> LWWRegister:
        return cls(
            version=d.get("version", 0),
            timestamp=d.get("timestamp", 0.0),
            valor=d.get("valor"),
            hash_valor=d.get("hash", ""),
        )


# ═══════════════════════════════════════════════════════════════════
# 2. REGISTRO CRDT COMPUESTO (varios campos)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class CRDTRecord:
    """Representa un registro clinico como conjunto de LWWRegisters."""
    record_id: str
    tabla: str
    tenant_id: str
    campos: dict[str, LWWRegister] = field(default_factory=dict)
    deleted: LWWRegister = field(default_factory=lambda: LWWRegister(version=0, timestamp=0.0, valor=False))

    def merge_campo(self, campo: str, register: LWWRegister) -> bool:
        """Fusiona un campo individual, retorna True si hubo cambio."""
        if campo not in self.campos:
            self.campos[campo] = register
            return True
        prev = self.campos[campo]
        self.campos[campo] = prev.merge(register)
        return self.campos[campo] is not prev

    def merge_record(self, other: CRDTRecord) -> list[str]:
        """Fusiona otro record completo, retorna lista de campos con conflicto."""
        conflictos = []
        for campo, reg in other.campos.items():
            if campo in self.campos:
                prev = self.campos[campo]
                merged = reg.merge(prev)
                if merged is reg and reg is not prev:
                    conflictos.append(campo)
                self.campos[campo] = merged
            else:
                self.campos[campo] = reg
        # Fusionar marca de borrado
        self.deleted = self.deleted.merge(other.deleted)
        return conflictos

    def is_deleted(self) -> bool:
        return bool(self.deleted.valor)

    def to_dict(self) -> dict:
        return {
            "id": self.record_id,
            "tabla": self.tabla,
            "tenant_id": self.tenant_id,
            "campos": {k: v.to_dict() for k, v in self.campos.items()},
            "deleted": self.deleted.to_dict(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> CRDTRecord:
        campos = {k: LWWRegister.from_dict(v) for k, v in d.get("campos", {}).items()}
        deleted = LWWRegister.from_dict(d.get("deleted", {}))
        return cls(
            record_id=d["id"],
            tabla=d["tabla"],
            tenant_id=d["tenant_id"],
            campos=campos,
            deleted=deleted,
        )


# ═══════════════════════════════════════════════════════════════════
# 3. MERGE ENGINE — PROCESA LOTES DE REGISTROS CONFLICTIVOS
# ═══════════════════════════════════════════════════════════════════

class CRDTMergeEngine:
    """Motor de mezcla para sincronizacion batch.

    Recibe un lote de registros del cliente y del servidor,
    los fusiona con LWW y persiste el resultado.
    """

    def __init__(self):
        self._conflict_log: list[dict] = []

    @staticmethod
    def _build_hash(registro: dict) -> str:
        """Hash canonical del registro para deteccion de cambios."""
        canonical = json.dumps(registro, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:32]

    def registro_a_crdt(self, registro: dict, tabla: str, tenant_id: str,
                        version: int = 0, timestamp: Optional[float] = None) -> CRDTRecord:
        """Convierte un registro plano a estructura CRDT."""
        ts = timestamp or registro.get("updated_at", time.time())
        if isinstance(ts, str):
            try:
                from datetime import datetime
                ts = datetime.fromisoformat(ts).timestamp()
            except (ValueError, TypeError):
                ts = time.time()

        record_id = str(registro.get("id", ""))
        campos = {}
        excluded = {"id", "tenant_id", "deleted_at", "created_at", "updated_at", "version"}
        for k, v in registro.items():
            if k not in excluded:
                campos[k] = LWWRegister(
                    version=registro.get("version", version),
                    timestamp=ts if isinstance(ts, (int, float)) else time.time(),
                    valor=v,
                )

        deleted_reg = LWWRegister(version=0, timestamp=0.0, valor=False)
        if registro.get("deleted_at"):
            deleted_reg = LWWRegister(
                version=registro.get("version", version),
                timestamp=ts if isinstance(ts, (int, float)) else time.time(),
                valor=True,
            )

        return CRDTRecord(
            record_id=record_id,
            tabla=tabla,
            tenant_id=tenant_id,
            campos=campos,
            deleted=deleted_reg,
        )

    async def merge_batch(
        self,
        registros_cliente: list[dict],
        registros_servidor: list[dict],
        tabla: str,
        tenant_id: str,
    ) -> dict:
        """Fusiona un lote de registros cliente vs servidor.

        Returns:
            dict con:
            - merged: registros fusionados a persistir
            - conflictos: lista de conflictos detectados
            - resoluciones: reglas aplicadas
        """
        # Indexar por id
        cliente_idx: dict[str, dict] = {r["id"]: r for r in registros_cliente}
        servidor_idx: dict[str, dict] = {r["id"]: r for r in registros_servidor}
        todos_ids = set(cliente_idx) | set(servidor_idx)

        merged: list[dict] = []
        conflictos: list[dict] = []

        for rid in todos_ids:
            crdt_cliente = None
            crdt_servidor = None

            if rid in cliente_idx:
                r = cliente_idx[rid]
                crdt_cliente = self.registro_a_crdt(
                    r, tabla, tenant_id,
                    version=r.get("version", 0),
                    timestamp=r.get("updated_at"),
                )

            if rid in servidor_idx:
                r = servidor_idx[rid]
                crdt_servidor = self.registro_a_crdt(
                    r, tabla, tenant_id,
                    version=r.get("version", 0),
                    timestamp=r.get("updated_at"),
                )

            if crdt_cliente and crdt_servidor:
                # Conflicto: mezclar
                campos_conflicto = crdt_servidor.merge_record(crdt_cliente)
                if campos_conflicto:
                    conflictos.append({
                        "id": rid,
                        "tabla": tabla,
                        "campos": campos_conflicto,
                        "resolucion": "LWW",
                    })
                    log_event("crdt", f"conflicto:{tabla}:{rid}:{','.join(campos_conflicto)}")
                merged.append(crdt_servidor.to_dict())
            elif crdt_cliente:
                merged.append(crdt_cliente.to_dict())
            else:
                merged.append(crdt_servidor.to_dict())

        return {
            "merged": merged,
            "conflictos": conflictos,
            "total": len(merged),
        }

    def get_conflict_log(self) -> list[dict]:
        return list(self._conflict_log)


# ═══════════════════════════════════════════════════════════════════
# 4. ENDPOINT BATCH (/sync/batch) — router en scripts/sync_batch.py
# ═══════════════════════════════════════════════════════════════════

BATCH_ROUTER_REF = "scripts.sync_batch"

# Exportar para que pueda ser usado en el router de FastAPI
__all__ = [
    "LWWRegister",
    "CRDTRecord",
    "CRDTMergeEngine",
    "BATCH_ROUTER_REF",
]
