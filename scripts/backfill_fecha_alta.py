"""
Backfill: asigna fecha_alta a pacientes existentes sin ella.

Usa created_at como fallback. Modo dry-run por defecto.
Uso:
    python scripts/backfill_fecha_alta.py            # dry-run
    python scripts/backfill_fecha_alta.py --apply     # escribe cambios
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

if load_dotenv:
    load_dotenv()

LOCAL_DB = Path("backups/medicare_db.json")


def _local():
    if not LOCAL_DB.exists():
        return None, []
    raw = json.loads(LOCAL_DB.read_text(encoding="utf-8"))
    pacientes = raw.get("pacientes", []) if isinstance(raw, dict) else raw
    return raw, pacientes


def _supabase():
    try:
        from supabase import create_client
    except ImportError:
        return None
    url = os.environ.get("SUPABASE_URL") or os.environ.get("SUPABASE_API_URL")
    key = os.environ.get("SUPABASE_KEY") or os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
    if not url or not key:
        return None
    return create_client(url, key)


def backfill_local(dry_run: bool) -> int:
    raw, pacientes = _local()
    if raw is None:
        print("no se encontro backups/medicare_db.json")
        return 0
    count = 0
    for p in pacientes:
        if not isinstance(p, dict):
            continue
        if p.get("fecha_alta"):
            continue
        fallback = p.get("created_at") or datetime.now(timezone.utc).isoformat()
        nuevo = fallback[:10] if "T" in str(fallback) else fallback
        if dry_run:
            print(f"  [DRY] {p.get('nombre','?')}: fecha_alta -> {nuevo}")
        else:
            p["fecha_alta"] = nuevo
        count += 1
    if not dry_run and count:
        if isinstance(raw, dict):
            raw["pacientes"] = pacientes
        LOCAL_DB.write_text(
            json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    return count


def backfill_supabase(dry_run: bool) -> int:
    sb = _supabase()
    if sb is None:
        print("supabase no configurado (faltan SUPABASE_URL/KEY)")
        return 0
    resp = sb.table("pacientes").select("id,nombre,created_at,fecha_alta").is_("fecha_alta", "null").execute()
    rows = resp.data if resp and resp.data else []
    if not rows:
        print("no hay pacientes sin fecha_alta en supabase")
        return 0
    count = 0
    for r in rows:
        fallback = r.get("created_at") or datetime.now(timezone.utc).isoformat()
        nuevo = fallback[:10] if "T" in str(fallback) else fallback
        if dry_run:
            print(f"  [DRY] {r.get('nombre','?')}: fecha_alta -> {nuevo}")
        else:
            sb.table("pacientes").update({"fecha_alta": nuevo}).eq("id", r["id"]).execute()
        count += 1
    return count


def main():
    parser = argparse.ArgumentParser(description="Backfill fecha_alta para pacientes")
    parser.add_argument("--apply", action="store_true", help="aplica los cambios")
    args = parser.parse_args()
    dry = not args.apply
    print(f"{'DRY-RUN' if dry else 'APLICANDO'} - backfill fecha_alta")
    c1 = backfill_local(dry)
    c2 = backfill_supabase(dry)
    print(f"local: {c1} paciente(s) {'pendiente(s)' if dry else 'actualizado(s)'}")
    print(f"supabase: {c2} paciente(s) {'pendiente(s)' if dry else 'actualizado(s)'}")
    if dry:
        print("ejecuta con --apply para aplicar los cambios")


if __name__ == "__main__":
    main()
