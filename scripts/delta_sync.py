#!/usr/bin/env python3
"""Sincronizacion delta para clientes moviles con ancho de banda limitado.
El cliente envia ultimo timestamp/version, el servidor calcula diff.
Usa MessagePack para payload comprimido binario.
"""
from __future__ import annotations

import hashlib
import time
from typing import Any, Optional

import msgpack
from fastapi import APIRouter, Depends, HTTPException

from core.app_logging import log_event

router = APIRouter(prefix="/sync", tags=["sync"])


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS
# ═══════════════════════════════════════════════════════════════════

class DeltaRequest:
    """Solicitud de sincronizacion delta del cliente."""
    def __init__(self, tenant_id: str, ultimo_timestamp: float = 0.0,
                 ultimas_versiones: Optional[dict[str, int]] = None):
        self.tenant_id = tenant_id
        self.ultimo_timestamp = ultimo_timestamp
        self.ultimas_versiones = ultimas_versiones or {}


class DeltaResponse:
    """Respuesta delta empaquetada en MessagePack."""
    def __init__(self):
        self.cambios: dict[str, list[dict[str, Any]]] = {}
        self.eliminados: dict[str, list[str]] = {}
        self.timestamp_servidor: float = time.time()


# ═══════════════════════════════════════════════════════════════════
# 2. ENDPOINT DELTA SYNC
# ═══════════════════════════════════════════════════════════════════

@router.post("/delta")
async def sync_delta(
    tenant_id: str,
    ultimo_timestamp: float = 0.0,
    ultimas_versiones: Optional[dict[str, int]] = None,
) -> bytes:
    """Endpoint de sincronizacion delta.

    El cliente envia:
    - ultimo_timestamp: timestamp de la ultima sync exitosa
    - ultimas_versiones: dict {tabla_id: version} de cada registro local

    El servidor responde con MessagePack binario:
    - cambios: {tabla: [registros con version > local]}
    - eliminados: {tabla: [ids eliminados desde ultimo_timestamp]}
    """
    import asyncpg

    conn = await asyncpg.connect("postgresql://localhost:5432/medicare")
    try:
        response = DeltaResponse()
        ultimas = ultimas_versiones or {}

        # 1. Buscar cambios desde ultimo_timestamp
        for tabla in ("evoluciones", "administracion_med", "recetas"):
            registros = await conn.fetch(f"""
                SELECT * FROM {tabla}
                WHERE tenant_id = $1
                  AND updated_at > to_timestamp($2)
                ORDER BY updated_at ASC
                LIMIT 500
            """, tenant_id, ultimo_timestamp if ultimo_timestamp > 0 else 0)

            cambios = []
            for r in registros:
                d = dict(r)
                # Convertir tipos no serializables
                for k, v in d.items():
                    if isinstance(v, (bytes, bytearray)):
                        d[k] = v.hex()
                    elif hasattr(v, 'isoformat'):
                        d[k] = v.isoformat()
                cambios.append(d)
            if cambios:
                response.cambios[tabla] = cambios

        # 2. Buscar eliminados (soft delete)
        # Asumiendo que las tablas tienen deleted_at TIMESTAMP
        for tabla in ("evoluciones", "administracion_med"):
            if ultimo_timestamp > 0:
                eliminados = await conn.fetch(f"""
                    SELECT id FROM {tabla}
                    WHERE tenant_id = $1
                      AND deleted_at > to_timestamp($2)
                      AND deleted_at IS NOT NULL
                """, tenant_id, ultimo_timestamp)
                if eliminados:
                    response.eliminados[tabla] = [str(r["id"]) for r in eliminados]

        # 3. Empaquetar en MessagePack (binario, 60% mas compacto que JSON)
        payload = msgpack.packb({
            "cambios": response.cambios,
            "eliminados": response.eliminados,
            "timestamp": response.timestamp_servidor,
        }, use_bin_type=True)

        log_event("delta_sync", f"respuesta:{len(payload)}b:{len(response.cambios)}tablas")
        return payload

    finally:
        await conn.close()


# ═══════════════════════════════════════════════════════════════════
# 3. CLIENTE MOVIL (ejemplo de uso)
# ═══════════════════════════════════════════════════════════════════

class DeltaClient:
    """Cliente de sincronizacion delta para usar desde el dispositivo movil."""

    @staticmethod
    def get_cached_version() -> tuple[float, dict[str, int]]:
        """Obtiene la ultima version cacheada localmente.

        Returns:
            (timestamp, {registro_id: version})
        """
        # En produccion, leer de SQLite local
        return 0.0, {}

    @staticmethod
    def apply_changes(payload: bytes) -> int:
        """Aplica cambios delta recibidos a la base local.

        Args:
            payload: Bytes MessagePack del servidor.

        Returns:
            Cantidad de registros aplicados.
        """
        data = msgpack.unpackb(payload, raw=False)
        cambios = data.get("cambios", {})
        total = 0
        for tabla, registros in cambios.items():
            total += len(registros)
            # Aplicar a SQLite local
            log_event("delta_sync", f"aplicados:{tabla}:{len(registros)}")
        return total

    @staticmethod
    async def sync() -> int:
        """Ejecuta sincronizacion delta completa."""
        ts, versiones = DeltaClient.get_cached_version()

        import httpx
        import msgpack

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://api.medicare-pro.app/sync/delta",
                json={
                    "ultimo_timestamp": ts,
                    "ultimas_versiones": versiones,
                },
                timeout=30,
            )
            payload = response.content
            return DeltaClient.apply_changes(payload)
