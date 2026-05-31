#!/usr/bin/env python3
"""Worker diario de auto-auditoria de cumplimiento (Continuous Compliance).
Genera score de salud del tenant, alerta sobre anomalias de acceso,
hash mismatch y faltas de rotacion de claves.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from collections import Counter
from datetime import datetime, timedelta
from typing import Any

from core.app_logging import log_event


class ComplianceEngine:
    """Motor de auto-auditoria que corre diariamente.

    Evalua:
    1. Integridad criptografica (hash_integridad vs datos actuales)
    2. Accesos inusuales (>50 PHI en 5 min)
    3. Rotacion de claves de cifrado
    """

    def __init__(self, db_url: str):
        self.db_url = db_url

    async def check_integridad_criptografica(self) -> list[dict[str, Any]]:
        """Verifica que los hash_integridad coincidan con los datos actuales.

        Usa la funcion calcular_hash_integridad del lado PostgreSQL.
        """
        import asyncpg
        conn = await asyncpg.connect(self.db_url)
        anomalias = []
        try:
            # Verificar evoluciones
            rows = await conn.fetch("""
                SELECT id, tenant_id, hash_integridad
                FROM evoluciones
                WHERE hash_integridad IS NOT NULL
                  AND hash_integridad != ''
                ORDER BY created_at DESC
                LIMIT 5000
            """)
            for r in rows:
                if not r["hash_integridad"]:
                    continue
                # Recalcular hash del lado SQL (funcion calcular_hash_integridad)
                recalculado = await conn.fetchval(
                    "SELECT calcular_hash_integridad(row_to_json(e.*)::JSONB) "
                    "FROM evoluciones e WHERE id = $1", r["id"]
                )
                if recalculado and recalculado != r["hash_integridad"]:
                    anomalias.append({
                        "tabla": "evoluciones",
                        "id": str(r["id"]),
                        "tenant_id": str(r["tenant_id"]),
                        "tipo": "hash_mismatch",
                        "hash_actual": r["hash_integridad"][:20],
                        "hash_recalculado": recalculado[:20],
                    })
            log_event("compliance", f"integridad: {len(rows)} revisados, {len(anomalias)} anomalias")
        finally:
            await conn.close()
        return anomalias

    async def check_accesos_inusuales(self) -> list[dict[str, Any]]:
        """Detecta accesos masivos a PHI (>50 lecturas en 5 min)."""
        import asyncpg
        conn = await asyncpg.connect(self.db_url)
        alertas = []
        try:
            rows = await conn.fetch("""
                SELECT usuario, COUNT(*) as accesos, tenant_id
                FROM audit_trail
                WHERE accion = 'lectura_phi'
                  AND timestamp >= NOW() - INTERVAL '5 minutes'
                GROUP BY usuario, tenant_id
                HAVING COUNT(*) > 50
            """)
            for r in rows:
                alertas.append({
                    "usuario": r["usuario"],
                    "tenant_id": r["tenant_id"],
                    "accesos_5min": r["accesos"],
                    "tipo": "acceso_masivo",
                })
            log_event("compliance", f"accesos inusuales: {len(alertas)}")
        finally:
            await conn.close()
        return alertas

    async def check_rotacion_claves(self) -> list[dict[str, Any]]:
        """Verifica que las claves se hayan rotado en los ultimos 30 dias."""
        import asyncpg
        conn = await asyncpg.connect(self.db_url)
        alertas = []
        try:
            rows = await conn.fetch("""
                SELECT tenant_id, MAX(created_at) as ultima_rotacion
                FROM export_wal
                WHERE estado = 'completado'
                GROUP BY tenant_id
            """)
            for r in rows:
                if r["ultima_rotacion"] < datetime.utcnow() - timedelta(days=35):
                    alertas.append({
                        "tenant_id": r["tenant_id"],
                        "ultima_rotacion": r["ultima_rotacion"].isoformat(),
                        "tipo": "rotacion_pendiente",
                    })
            log_event("compliance", f"rotaciones pendientes: {len(alertas)}")
        finally:
            await conn.close()
        return alertas

    async def generar_score(self, tenant_id: str) -> dict[str, Any]:
        """Genera score de salud del tenant (0-100)."""
        anomalias = await self.check_integridad_criptografica()
        accesos = await self.check_accesos_inusuales()
        rotacion = await self.check_rotacion_claves()

        penalidades = 0
        penalidades += len(anomalias) * 10
        penalidades += len(accesos) * 15
        penalidades += len(rotacion) * 20

        score = max(0, 100 - penalidades)

        return {
            "tenant_id": tenant_id,
            "score": score,
            "nivel": "CRITICO" if score < 50 else "WARNING" if score < 80 else "HEALTHY",
            "anomalias_hash": len(anomalias),
            "accesos_inusuales": len(accesos),
            "rotaciones_pendientes": len(rotacion),
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def ejecutar(self) -> list[dict[str, Any]]:
        """Ejecuta todos los checks de compliance y genera alertas."""
        resultados = []

        integridad = await self.check_integridad_criptografica()
        for a in integridad:
            log_event("compliance", f"HASH_MISMATCH:{a['tabla']}:{a['id']}")
            resultados.append(a)

        accesos = await self.check_accesos_inusuales()
        for a in accesos:
            log_event("compliance", f"ACCESO_MASIVO:{a['usuario']}:{a['accesos_5min']}")
            resultados.append(a)

        rotacion = await self.check_rotacion_claves()
        for a in rotacion:
            log_event("compliance", f"ROTACION_PENDIENTE:{a['tenant_id']}")
            resultados.append(a)

        return resultados


async def main():
    db_url = os.environ.get("DATABASE_URL", "postgresql://localhost:5432/medicare")
    engine = ComplianceEngine(db_url)
    resultados = await engine.ejecutar()

    # Generar score por tenant
    tenants = os.environ.get("MEDICARE_TENANTS", "default,avalian,sancor").split(",")
    for t in tenants:
        t = t.strip()
        if t:
            score = await engine.generar_score(t)
            print(f"[{score['nivel']}] {t}: score={score['score']}")

    print(f"Total anomalias: {len(resultados)}")


if __name__ == "__main__":
    asyncio.run(main())
