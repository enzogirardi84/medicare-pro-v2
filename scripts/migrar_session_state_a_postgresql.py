#!/usr/bin/env python3
"""Migracion automatica de session_state (JSON en memoria) a PostgreSQL.
Lee los datos historicos de session_state, los estructura en 3NF,
inyecta tenant_id por defecto, y persiste via TenantRepository.

Uso:
    streamlit run scripts/migrar_session_state_a_postgresql.py
    python scripts/migrar_session_state_a_postgresql.py --source backup.json
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent


def parse_paciente_id(pid: str) -> tuple[str, str]:
    """Separa 'Nombre - DNI' en (nombre, dni).

    Normaliza a 1NF: el identificador compuesto se divide.
    """
    if " - " in pid:
        parts = pid.rsplit(" - ", 1)
        return (parts[0].strip(), parts[1].strip())
    return (pid.strip(), "")


def migrar_pacientes(data: list[str], tenant_id: str) -> list[dict]:
    """Convierte lista de strings 'Nombre - DNI' a dicts normalizados."""
    pacientes = []
    seen = set()
    for pid in data:
        nombre, dni = parse_paciente_id(pid)
        if dni and dni not in seen:
            seen.add(dni)
            pacientes.append({
                "nombre": nombre,
                "dni": dni,
                "estado": "Activo",
                "tenant_id": tenant_id,
            })
    return pacientes


def migrar_evoluciones(data: list[dict], tenant_id: str) -> list[dict]:
    """Convierte evoluciones de session_state a formato normalizado."""
    evoluciones = []
    for evo in data:
        if not isinstance(evo, dict):
            continue
        nombre_paciente = evo.get("paciente", "")
        _, dni = parse_paciente_id(nombre_paciente)
        evoluciones.append({
            "dni_paciente": dni,
            "nombre_paciente": nombre_paciente,
            "nota": evo.get("nota", evo.get("texto", "")),
            "diagnostico": evo.get("diagnostico", ""),
            "medicacion": evo.get("medicacion", ""),
            "fecha": evo.get("fecha", ""),
            "firma": evo.get("firma", ""),
            "firma_ecdsa": evo.get("_firma_ecdsa", ""),
            "tenant_id": tenant_id,
        })
    return evoluciones


def migrar_checkins(data: list[dict], tenant_id: str) -> list[dict]:
    """Convierte check-ins GPS a formato PostGIS."""
    checkins = []
    for ci in data:
        if not isinstance(ci, dict):
            continue
        gps_str = ci.get("gps", "")
        lat, lon = 0.0, 0.0
        if gps_str and "," in gps_str:
            try:
                lat, lon = (float(x) for x in gps_str.split(",", 1))
            except (ValueError, TypeError):
                continue
        checkins.append({
            "profesional": ci.get("profesional", ci.get("tipo", "")),
            "paciente": ci.get("paciente", ""),
            "lat": lat,
            "lon": lon,
            "timestamp": ci.get("fecha_hora", ""),
            "source": "migracion",
            "tenant_id": tenant_id,
        })
    return checkins


def migrar_administracion_med(data: list[dict], tenant_id: str) -> list[dict]:
    """Convierte administracion de medicacion."""
    meds = []
    for m in data:
        if not isinstance(m, dict):
            continue
        meds.append({
            "medicamento": m.get("medicamento", m.get("med", "")),
            "dosis": m.get("dosis", ""),
            "via": m.get("via", ""),
            "fecha_real": m.get("fecha", ""),
            "estado": m.get("estado", "realizada"),
            "paciente": m.get("paciente", ""),
            "tenant_id": tenant_id,
        })
    return meds


def main():
    parser = argparse.ArgumentParser(description="Migrar session_state a PostgreSQL")
    parser.add_argument("--source", help="Archivo JSON con los datos (opcional)")
    parser.add_argument("--tenant", default="default", help="Tenant ID por defecto")
    args = parser.parse_args()

    # Cargar datos
    if args.source:
        with open(args.source, "r", encoding="utf-8") as f:
            all_data = json.load(f)
    else:
        # En modo Streamlit, leer de session_state directamente
        import streamlit as st
        all_data = {k: st.session_state[k] for k in st.session_state
                    if k.endswith("_db") and isinstance(st.session_state[k], list)}
        print("\U0001F4E1 Leyendo datos de session_state...")

    tenant_id = args.tenant

    print(f"\n{'='*60}")
    print(f"  MIGRACION A POSTGRESQL")
    print(f"  Tenant: {tenant_id}")
    print(f"{'='*60}")

    totales = {}

    # Migrar pacientes
    pacientes_raw = all_data.get("pacientes_db", [])
    if isinstance(pacientes_raw, list):
        pacientes = migrar_pacientes(pacientes_raw, tenant_id)
        totales["pacientes"] = len(pacientes)
        print(f"\n  Pacientes: {len(pacientes)}")
        for p in pacientes[:3]:
            print(f"    - {p['nombre']} (DNI: {p['dni']})")

    # Migrar evoluciones
    evos_raw = all_data.get("evoluciones_db", [])
    if isinstance(evos_raw, list):
        evoluciones = migrar_evoluciones(evos_raw, tenant_id)
        totales["evoluciones"] = len(evoluciones)
        print(f"  Evoluciones: {len(evoluciones)}")

    # Migrar check-ins GPS
    checkins_raw = all_data.get("checkin_db", [])
    if isinstance(checkins_raw, list):
        checkins = migrar_checkins(checkins_raw, tenant_id)
        totales["checkins"] = len(checkins)
        print(f"  Check-ins GPS: {len(checkins)}")

    # Migrar administracion de medicacion
    meds_raw = all_data.get("administracion_med_db", all_data.get("consumos_db", []))
    if isinstance(meds_raw, list):
        meds = migrar_administracion_med(meds_raw, tenant_id)
        totales["medicacion"] = len(meds)
        print(f"  Administracion med: {len(meds)}")

    print(f"\n{'='*60}")
    print(f"  RESUMEN: {sum(totales.values())} registros listos para migrar")
    for k, v in totales.items():
        print(f"    {k}: {v}")
    print(f"{'='*60}")

    # Persistir a PostgreSQL con transacciones por lote
    if len(sys.argv) > 1 and "--persistir" in sys.argv:
        import asyncio
        from core.tenant_repository import TenantRepository
        repo = TenantRepository()
        repo.set_tenant_context(tenant_id)

        async def persistir():
            async with repo.connect() as conn:
                async with conn.transaction():
                    BATCH = 100
                    for tabla, registros in [
                        ("pacientes", pacientes),
                        ("evoluciones", evoluciones),
                    ]:
                        for i in range(0, len(registros), BATCH):
                            batch = registros[i:i + BATCH]
                            for reg in batch:
                                await repo.insert(conn, tabla, reg)
                            print(f"  {tabla}: {i + len(batch)}/{len(registros)} registros")

        asyncio.run(persistir())
        print("Migracion completada con transacciones por lote.")
    else:
        print(f"\nPara persistir, ejecutar con --persistir")
        print(f"  python scripts/migrar_session_state_a_postgresql.py --persistir")

    return 0


if __name__ == "__main__":
    sys.exit(main())
