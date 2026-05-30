#!/usr/bin/env python3
"""Rotacion automatizada de claves KMS multi-tenant con auditoria.

Cumplimiento SOC2/HIPAA: las claves maestras CMK deben rotarse
periodicamente. Este script gestiona la rotacion via AWS KMS.

Los datos historicos permanecen legibles (AWS mantiene versiones
anteriores de las claves automaticamente).

Uso:
    python scripts/kms_key_rotation.py --tenant avalian --rotate
    python scripts/kms_key_rotation.py --tenant all --status
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime
from typing import Any, Optional

import boto3
from botocore.exceptions import ClientError


class KMSKeyManager:
    """Gestiona claves KMS multi-tenant con soporte para rotacion.

    Cada tenant puede tener su propia CMK (Customer Managed Key).
    El script automatiza la rotacion y auditoria.
    """

    KEY_ALIAS_PREFIX = "alias/medicare-"

    def __init__(self, region: str = "us-east-1", profile: str = ""):
        session = boto3.Session(profile_name=profile) if profile else boto3.Session()
        self._kms = session.client("kms", region_name=region)
        self._region = region
        self._tenant: str = ""

    def _key_alias(self, tenant: str) -> str:
        return f"{self.KEY_ALIAS_PREFIX}{tenant}"

    def _find_key_id(self, tenant: str) -> Optional[str]:
        """Busca el ID de la CMK por alias del tenant."""
        alias = self._key_alias(tenant)
        try:
            response = self._kms.describe_key(KeyId=alias)
            return response["KeyMetadata"]["KeyId"]
        except ClientError as e:
            if e.response["Error"]["Code"] == "NotFoundException":
                return None
            raise

    # ── Estado de las claves ──────────────────────────────────

    def status(self, tenant: str) -> dict[str, Any]:
        """Obtiene el estado actual de la clave KMS de un tenant."""
        key_id = self._find_key_id(tenant)
        if not key_id:
            return {"tenant": tenant, "status": "no_key", "region": self._region}

        response = self._kms.describe_key(KeyId=key_id)
        meta = response["KeyMetadata"]
        rotations = self._kms.list_key_rotations(KeyId=key_id)

        return {
            "tenant": tenant,
            "key_id": key_id,
            "arn": meta["Arn"],
            "status": meta["KeyState"],
            "created": meta["CreationDate"].isoformat(),
            "auto_rotation": meta.get("RotationEnabled", False),
            "last_rotation": rotations["Rotations"][0]["RotationDate"].isoformat()
                if rotations.get("Rotations") else "never",
            "total_rotations": len(rotations.get("Rotations", [])),
            "region": self._region,
        }

    def status_all(self, tenants: list[str]) -> list[dict[str, Any]]:
        """Estado de todos los tenants."""
        return [self.status(t) for t in tenants]

    # ── Rotacion de claves ────────────────────────────────────

    def enable_auto_rotation(self, tenant: str) -> bool:
        """Activa la rotacion automatica anual (Cumplimiento SOC2)."""
        key_id = self._find_key_id(tenant)
        if not key_id:
            print(f"[ERROR] No se encontro clave para tenant: {tenant}")
            return False

        try:
            self._kms.enable_key_rotation(KeyId=key_id)
            print(f"[OK] Rotacion automatica activada para {tenant} ({key_id[:12]}...)")

            # Verificar
            response = self._kms.get_key_rotation_status(KeyId=key_id)
            return response.get("KeyRotationEnabled", False)
        except ClientError as e:
            print(f"[ERROR] No se pudo activar rotacion: {e}")
            return False

    def rotate_manual(self, tenant: str) -> dict[str, Any]:
        """Rotacion manual de clave KMS (forzada).

        AWS KMS rota automaticamente las claves anualmente.
        La rotacion manual crea un nuevo backing key.
        Los datos cifrados con la clave anterior siguen siendo
        accesibles (AWS mantiene las versiones anteriores).
        """
        key_id = self._find_key_id(tenant)
        if not key_id:
            return {"tenant": tenant, "status": "no_key", "error": "Key not found"}

        try:
            # Iniciar rotacion
            self._kms.rotate_key_on_demand(KeyId=key_id)
            result = {
                "tenant": tenant,
                "key_id": key_id[:12] + "...",
                "rotacion": "manual",
                "timestamp": datetime.utcnow().isoformat(),
                "status": "rotated",
            }

            print(f"[OK] Rotacion manual completada para {tenant}")
            return result

        except ClientError as e:
            error_msg = e.response["Error"]["Message"]
            print(f"[ERROR] Rotacion fallo para {tenant}: {error_msg}")
            return {
                "tenant": tenant,
                "status": "error",
                "error": error_msg,
            }

    # ── Creacion de nueva clave para tenant ───────────────────

    def create_key(self, tenant: str, description: str = "") -> Optional[str]:
        """Crea una nueva CMK para un tenant."""
        desc = description or f"Medicare PRO - {tenant} encryption key"
        try:
            response = self._kms.create_key(
                Description=desc,
                KeyUsage="ENCRYPT_DECRYPT",
                KeySpec="SYMMETRIC_DEFAULT",
                MultiRegion=True,
                Tags=[
                    {"TagKey": "Tenant", "TagValue": tenant},
                    {"TagKey": "Environment", "TagValue": "production"},
                    {"TagKey": "Compliance", "TagValue": "HIPAA"},
                ],
            )
            key_id = response["KeyMetadata"]["KeyId"]

            # Crear alias
            self._kms.create_alias(
                AliasName=self._key_alias(tenant),
                TargetKeyId=key_id,
            )

            # Activar rotacion automatica
            self._kms.enable_key_rotation(KeyId=key_id)

            print(f"[OK] Clave KMS creada para {tenant}: {key_id[:12]}...")
            return key_id

        except ClientError as e:
            print(f"[ERROR] Creacion de clave fallo: {e}")
            return None

    # ── Auditoria ─────────────────────────────────────────────

    def audit_rotations(self, tenants: list[str]) -> list[dict[str, Any]]:
        """Audita el estado de rotacion de todos los tenants.

        Returns:
            Lista con estado de cada tenant para registrar en audit trail.
        """
        results = self.status_all(tenants)
        for r in results:
            if r["status"] == "no_key":
                print(f"[WARN] {r['tenant']}: Sin clave KMS configurada")
            elif not r.get("auto_rotation"):
                print(f"[WARN] {r['tenant']}: Rotacion automatica DESACTIVADA")
            else:
                print(f"[OK] {r['tenant']}: Rotacion OK ({r.get('last_rotation', 'N/A')})")

        return results


# ═══════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(
        description="Rotacion de claves KMS multi-tenant para MediCare PRO"
    )
    parser.add_argument(
        "--tenant", default="all",
        help="Tenant a procesar (default: all, o especificar: avalian)"
    )
    parser.add_argument(
        "--rotate", action="store_true",
        help="Ejecutar rotacion manual de claves"
    )
    parser.add_argument(
        "--enable-auto-rotation", action="store_true",
        help="Activar rotacion automatica anual"
    )
    parser.add_argument(
        "--status", action="store_true",
        help="Mostrar estado actual de las claves"
    )
    parser.add_argument(
        "--create", metavar="DESCRIPTION", nargs="?",
        const="Medicare PRO encryption key", default=None,
        help="Crear nueva clave KMS para el tenant"
    )
    parser.add_argument(
        "--region", default="us-east-1",
        help="Region AWS (default: us-east-1)"
    )
    parser.add_argument(
        "--profile", default="",
        help="Perfil de AWS CLI (opcional)"
    )
    parser.add_argument(
        "--tenants-list", nargs="*",
        default=["default", "avalian", "sancor"],
        help="Lista de tenants (default: default avalian sancor)"
    )

    args = parser.parse_args()
    manager = KMSKeyManager(region=args.region, profile=args.profile)

    tenants = args.tenants_list
    if args.tenant and args.tenant != "all":
        tenants = [args.tenant]

    # Estado
    if args.status:
        print(f"\nEstado de claves KMS en {args.region}:")
        print("=" * 60)
        for s in manager.status_all(tenants):
            print(f"  Tenant: {s['tenant']}")
            print(f"  Key ID: {s.get('key_id', 'N/A')}")
            print(f"  Status: {s['status']}")
            print(f"  Rotacion automatica: {s.get('auto_rotation', False)}")
            print(f"  Ultima rotacion: {s.get('last_rotation', 'N/A')}")
            print(f"  Total rotaciones: {s.get('total_rotations', 0)}")
            print()

    # Crear clave
    if args.create is not None:
        desc = args.create or f"Medicare PRO - {tenants[0]} encryption key"
        for t in tenants:
            manager.create_key(t, description=desc)

    # Activar rotacion automatica
    if args.enable_auto_rotation:
        for t in tenants:
            manager.enable_auto_rotation(t)

    # Rotacion manual
    if args.rotate:
        print(f"\nRotacion manual de claves:")
        print("=" * 60)
        for t in tenants:
            result = manager.rotate_manual(t)
            if result.get("status") == "error":
                print(f"  [ERROR] {t}: {result.get('error')}")

    # Auditoria final
    if args.status or args.rotate:
        print(f"\nAuditoria final de rotacion:")
        print("=" * 60)
        auditoria = manager.audit_rotations(tenants)

        # Registrar en audit trail inmutable
        try:
            sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
            from core.audit_trail_immutable import ImmutableAuditTrail
            auditor = ImmutableAuditTrail()
            auditor.registrar(
                usuario="__kms_rotation__",
                accion="KMS_ROTATION",
                recurso=f"kms:{args.region}",
                detalle=json.dumps(auditoria, indent=2, default=str)[:500],
            )
            print("[OK] Auditoria registrada en Audit Trail inmutable")
        except Exception as e:
            print(f"[WARN] No se pudo registrar auditoria: {e}")


if __name__ == "__main__":
    from pathlib import Path
    main()
