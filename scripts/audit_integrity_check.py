#!/usr/bin/env python3
"""Audit Trail Integrity Check - ejecutar como cron diario.

Verifica la integridad del encadenamiento de hashes del audit trail.
Si detecta una alteracion, envia una alerta (stderr / log critico).

Uso:
    python scripts/audit_integrity_check.py
    python scripts/audit_integrity_check.py --alert-email soporte@medicare.com
"""

from __future__ import annotations

import argparse
import json
import smtplib
import sys
from pathlib import Path


def verificar_audit_trail(log_path: Path) -> list[dict]:
    """Verifica la integridad del archivo de audit trail."""
    from core.audit_trail_immutable import ImmutableAuditTrail, AuditEntry

    if not log_path.exists():
        return [{"tipo": "archivo_no_encontrado", "path": str(log_path)}]

    auditor = ImmutableAuditTrail(log_dir=log_path.parent)
    errores = auditor.verificar_integridad(max_entries=50000)
    return errores


def enviar_alerta_email(errores: list[dict], destinatario: str) -> None:
    """Envia alerta por email si se detectan errores de integridad."""
    if not errores:
        return
    asunto = "[CRITICO] Audit Trail - Integridad comprometida"
    cuerpo = f"Se detectaron {len(errores)} errores en la verificacion de integridad:\n\n"
    for err in errores[:20]:
        cuerpo += f"  - {err.get('tipo')}: {json.dumps(err)}\n"
    if len(errores) > 20:
        cuerpo += f"\n... y {len(errores) - 20} errores mas."

    try:
        msg = f"Subject: {asunto}\n\n{cuerpo}"
        # En produccion, configurar SMTP real aqui
        print(f"[ALERTA] {asunto}", file=sys.stderr)
        print(cuerpo, file=sys.stderr)
    except Exception as e:
        print(f"Error enviando alerta: {e}", file=sys.stderr)


def rotar_a_cold_storage(log_dir: Path, cold_dir: Path | None = None) -> None:
    """Mueve archivos rotados .gz a cold storage.

    Los archivos .gz (versiones anteriores rotadas) se mueven a un
    directorio de almacenamiento frio con permisos de solo lectura.
    """
    if cold_dir is None:
        cold_dir = log_dir / "_cold_storage"
    cold_dir.mkdir(parents=True, exist_ok=True)

    for gz_file in log_dir.glob("*.gz"):
        destino = cold_dir / gz_file.name
        if not destino.exists():
            gz_file.rename(destino)
            # Hacer el archivo de solo lectura
            destino.chmod(0o444)
            print(f"[COLD] {gz_file.name} -> {destino}")


def main():
    parser = argparse.ArgumentParser(description="Verificacion diaria del audit trail")
    parser.add_argument("--alert-email", help="Email para alertas de integridad")
    parser.add_argument("--cold-dir", help="Directorio de cold storage")
    parser.add_argument("--check-only", action="store_true", help="Solo verificar, no rotar")
    args = parser.parse_args()

    log_dir = Path(".audit_logs")
    log_file = log_dir / "audit_trail.jsonl"

    # 1. Verificar integridad
    errores = verificar_audit_trail(log_file)
    if errores:
        print(f"[ERROR] {len(errores)} problema(s) de integridad detectados!", file=sys.stderr)
        for err in errores[:5]:
            print(f"  {err}", file=sys.stderr)
        if args.alert_email:
            enviar_alerta_email(errores, args.alert_email)
        sys.exit(1)
    else:
        print("[OK] Integridad del audit trail verificada - 0 errores")

    # 2. Rotar a cold storage
    if not args.check_only:
        rotar_a_cold_storage(log_dir, Path(args.cold_dir) if args.cold_dir else None)
        print("[OK] Rotacion a cold storage completada")


if __name__ == "__main__":
    main()
