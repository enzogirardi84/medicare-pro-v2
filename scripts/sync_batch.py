from __future__ import annotations

import time

from fastapi import APIRouter

from core.crdt_resolver import CRDTMergeEngine
from core.app_logging import log_event

router = APIRouter(prefix="/sync", tags=["sync"])


@router.post("/batch")
async def sync_batch(payload: dict) -> dict:
    """Endpoint de sincronizacion batch con resolucion CRDT.

    El cliente envia:
    {
        "tenant_id": "...",
        "tablas": {
            "evoluciones": [registro1, registro2, ...],
            "administracion_med": [...],
        }
    }

    El servidor responde con registros fusionados via LWW.
    """
    import asyncpg

    engine = CRDTMergeEngine()
    tenant_id = payload.get("tenant_id", "")
    tablas_cliente = payload.get("tablas", {})

    conn = await asyncpg.connect("postgresql://localhost:5432/medicare")
    try:
        resultados = {}

        for tabla, registros_cliente in tablas_cliente.items():
            ids = [r["id"] for r in registros_cliente if r.get("id")]
            if not ids:
                continue

            registros_servidor = await conn.fetch(
                "SELECT * FROM {} WHERE tenant_id = $1 AND id = ANY($2::UUID[])".format(tabla),
                tenant_id, ids,
            )

            registros_servidor_dicts = [dict(r) for r in registros_servidor]

            resultado = await engine.merge_batch(
                registros_cliente=registros_cliente,
                registros_servidor=registros_servidor_dicts,
                tabla=tabla,
                tenant_id=tenant_id,
            )

            for r in resultado["merged"]:
                campos = r.get("campos", {})
                if r.get("deleted", {}).get("valor"):
                    await conn.execute(
                        "UPDATE {} SET deleted_at = NOW(), version = version + 1 WHERE id = $1".format(tabla),
                        r["id"],
                    )
                else:
                    set_parts = []
                    valores = []
                    for i, (campo, reg) in enumerate(campos.items()):
                        set_parts.append("{} = ${}".format(campo, i + 2))
                        valores.append(reg.get("valor"))
                    if set_parts:
                        set_parts.append("version = version + 1")
                        set_parts.append("updated_at = NOW()")
                        sql = "UPDATE {} SET {} WHERE id = $1 AND tenant_id = $2".format(
                            tabla, ", ".join(set_parts),
                        )
                        await conn.execute(sql, r["id"], tenant_id, *valores)

            resultados[tabla] = resultado

        log_event("sync_batch", "procesados:{} tablas".format(len(resultados)))
        return {
            "resultados": resultados,
            "conflictos": sum(len(r["conflictos"]) for r in resultados.values()),
            "timestamp": time.time(),
        }
    finally:
        await conn.close()
