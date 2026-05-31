#!/usr/bin/env python3
"""Refresco de vistas materializadas sin bloqueo de lecturas.
Usa CONCURRENTLY para evitar locks. Programable via cron.

Ejecutar cada 15 minutos:
    */15 * * * * python scripts/mv_refresh_cron.py
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time


async def refresh_mv_concurrently(mv_name: str, conn_string: str) -> dict:
    """Refresca una vista materializada con CONCURRENTLY.

    La opcion CONCURRENTLY permite lecturas simultaneas.
    Requiere un indice UNIQUE en la vista.
    """
    import asyncpg

    t0 = time.perf_counter()
    try:
        conn = await asyncpg.connect(conn_string)
        await conn.execute(f"REFRESH MATERIALIZED VIEW CONCURRENTLY {mv_name}")
        await conn.close()
        dt = (time.perf_counter() - t0) * 1000
        return {"vista": mv_name, "estado": "ok", "tiempo_ms": round(dt, 1)}
    except Exception as exc:
        return {"vista": mv_name, "estado": "error", "error": str(exc)[:100]}


async def crear_particiones_pendientes(conn_string: str) -> list[str]:
    """Crea particiones mensuales para los proximos 3 meses."""
    import asyncpg

    creadas = []
    conn = await asyncpg.connect(conn_string)
    for mes in range(1, 4):
        from datetime import date, timedelta
        hoy = date.today()
        primer_dia = hoy.replace(day=1) + timedelta(days=32 * mes)
        primer_dia = primer_dia.replace(day=1)
        mes_fin = (primer_dia.replace(day=28) + timedelta(days=4)).replace(day=1)
        partition_name = f"checkins_gps_{primer_dia.strftime('%Y_%m')}"

        existe = await conn.fetchval(
            "SELECT 1 FROM pg_class WHERE relname = $1", partition_name
        )
        if not existe:
            await conn.execute(f"""
                CREATE TABLE {partition_name} PARTITION OF checkins_gps
                FOR VALUES FROM ($1::DATE) TO ($2::DATE)
            """, primer_dia, mes_fin)
            creadas.append(partition_name)

    await conn.close()
    return creadas


async def main():
    parser = argparse.ArgumentParser(description="Refresco de vistas materializadas")
    parser.add_argument("--db", default="postgresql://localhost:5432/medicare")
    parser.add_argument("--vistas", nargs="+", default=["mv_densidad_atenciones"])
    parser.add_argument("--crear-particiones", action="store_true")
    args = parser.parse_args()

    resultados = []
    for vista in args.vistas:
        result = await refresh_mv_concurrently(vista, args.db)
        resultados.append(result)
        icon = "\U00002705" if result["estado"] == "ok" else "\U0000274C"
        print(f"{icon} {result['vista']}: {result.get('tiempo_ms', 'error')}ms")

    if args.crear_particiones:
        particiones = await crear_particiones_pendientes(args.db)
        for p in particiones:
            print(f"\U0001F195 Particion creada: {p}")

    fallos = sum(1 for r in resultados if r["estado"] == "error")
    return 1 if fallos > 0 else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
