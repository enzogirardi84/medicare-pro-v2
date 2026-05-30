#!/usr/bin/env python3
"""Provisionamiento automatico de nuevos tenants (clientes corporativos).
Crea infraestructura aislada: S3, base de datos, configuracion, claves.

Uso:
    python scripts/tenant_provisioner.py --tenant sancor_salud --region us-east-1
    python scripts/tenant_provisioner.py --tenant avalian --region sa-east-1 --byok
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Raiz del proyecto
ROOT = Path(__file__).resolve().parent.parent


class TenantProvisioner:
    """Automatiza la creacion completa de un nuevo tenant.

    Pasos:
    1. Crear estructura de directorios locales
    2. Crear bucket S3 para estudios
    3. Ejecutar migraciones PostgreSQL
    4. Generar config.json con claves criptograficas
    5. Registrar en audit trail
    """

    def __init__(self, tenant_id: str, region: str = "us-east-1", byok: bool = False):
        self.tenant_id = tenant_id.lower().strip()
        self.region = region
        self.byok = byok
        self.tenant_dir = ROOT / "tenants" / self.tenant_id
        self.resultado: dict[str, Any] = {
            "tenant": self.tenant_id,
            "region": region,
            "timestamp": datetime.utcnow().isoformat(),
            "pasos": [],
        }

    def _log(self, paso: str, ok: bool, detalle: str = "") -> None:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {paso}: {detalle}")
        self.resultado["pasos"].append({
            "paso": paso,
            "status": status,
            "detalle": detalle[:200],
        })

    def provisionar(self) -> dict[str, Any]:
        """Ejecuta el pipeline completo de provisionamiento."""
        print(f"\n{'='*60}")
        print(f"  Provisionando tenant: {self.tenant_id}")
        print(f"  Region: {self.region}")
        print(f"{'='*60}\n")

        self._paso_1_crear_directorios()
        self._paso_2_crear_bucket_s3()
        self._paso_3_generar_config()
        self._paso_4_ejecutar_migraciones_sql()
        self._paso_5_registrar_audit_trail()
        self._paso_6_generar_claves_kms()

        self._log("PROVISIONAMIENTO COMPLETO", True, f"Tenant {self.tenant_id} listo")
        return self.resultado

    # ── Paso 1: Directorios locales ──────────────────────────

    def _paso_1_crear_directorios(self) -> None:
        try:
            for d in ["offline_queue", "audit_logs", "estudios", "backups"]:
                (self.tenant_dir / d).mkdir(parents=True, exist_ok=True)
            self._log("Directorios creados", True, str(self.tenant_dir))
        except Exception as exc:
            self._log("Directorios", False, str(exc))

    # ── Paso 2: Bucket S3 ────────────────────────────────────

    def _paso_2_crear_bucket_s3(self) -> None:
        try:
            import boto3
            s3 = boto3.client("s3", region_name=self.region)
            bucket_name = f"medicare-estudios-{self.tenant_id}"

            try:
                s3.head_bucket(Bucket=bucket_name)
                self._log("Bucket S3 ya existe", True, bucket_name)
            except Exception:
                s3.create_bucket(
                    Bucket=bucket_name,
                    CreateBucketConfiguration={"LocationConstraint": self.region},
                )
                s3.put_bucket_versioning(
                    Bucket=bucket_name,
                    VersioningConfiguration={"Status": "Enabled"},
                )
                s3.put_bucket_encryption(
                    Bucket=bucket_name,
                    ServerSideEncryptionConfiguration={
                        "Rules": [{
                            "ApplyServerSideEncryptionByDefault": {"SSEAlgorithm": "AES256"},
                        }]
                    },
                )
                self._log("Bucket S3 creado", True, bucket_name)
        except ImportError:
            self._log("Bucket S3", False, "boto3 no instalado. Saltando.")
        except Exception as exc:
            self._log("Bucket S3", False, str(exc)[:100])

    # ── Paso 3: Config.json ──────────────────────────────────

    def _paso_3_generar_config(self) -> None:
        import secrets
        config = {
            "tenant_id": self.tenant_id,
            "nombre": f"Cliente {self.tenant_id.replace('_', ' ').title()}",
            "region": self.region,
            "fecha_creacion": datetime.utcnow().isoformat(),
            "color_primario": "#1e3a5f",
            "color_secundario": "#2d5a8e",
            "sesion_timeout_min": 480,
            "max_intentos_login": 5,
            "lockout_segundos": 300,
            "claves_criptograficas": {
                "salt_pbkdf2": secrets.token_hex(32),
                "initialization_vector": secrets.token_hex(16),
                "tenant_secret": secrets.token_hex(48),
            },
            "byok_habilitado": self.byok,
        }
        config_path = self.tenant_dir / "config.json"
        config_path.write_text(json.dumps(config, indent=2), encoding="utf-8")
        self._log("Config.json generado", True, str(config_path))

    # ── Paso 4: Migraciones SQL ──────────────────────────────

    def _paso_4_ejecutar_migraciones_sql(self) -> None:
        sql_file = ROOT / "scripts" / "db_optimization.sql"
        if not sql_file.exists():
            self._log("Migraciones SQL", False, "Archivo db_optimization.sql no encontrado")
            return

        # Intentar conectar a la base de datos del tenant
        db_host = os.environ.get(f"{self.tenant_id.upper()}_DB_HOST", "localhost")
        db_name = os.environ.get(f"{self.tenant_id.upper()}_DB_NAME", f"medicare_{self.tenant_id}")
        db_user = os.environ.get(f"{self.tenant_id.upper()}_DB_USER", "medicare_admin")

        try:
            import boto3
            # Si hay secret manager, obtener credenciales
            secrets_client = boto3.client("secretsmanager", region_name=self.region)
            secret_id = f"medicare-prod-{self.tenant_id}-aurora-credentials"
            try:
                secret = secrets_client.get_secret_value(SecretId=secret_id)
                creds = json.loads(secret["SecretString"])
                db_host = creds.get("host", db_host)
                db_name = creds.get("dbname", db_name)
                db_user = creds.get("username", db_user)
                db_pass = creds.get("password", "")
            except Exception:
                db_pass = os.environ.get(f"{self.tenant_id.upper()}_DB_PASSWORD", "")

            # Ejecutar migraciones via psql
            cmd = [
                "psql",
                f"postgresql://{db_user}:{db_pass}@{db_host}:5432/{db_name}",
                "-f", str(sql_file),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0:
                self._log("Migraciones SQL ejecutadas", True, f"Exit: {result.returncode}")
            else:
                self._log("Migraciones SQL", False, result.stderr[:200])
        except FileNotFoundError:
            self._log("Migraciones SQL", False, "psql no instalado. Ejecutar manualmente.")
        except Exception as exc:
            self._log("Migraciones SQL", False, str(exc)[:100])

    # ── Paso 5: Audit trail ──────────────────────────────────

    def _paso_5_registrar_audit_trail(self) -> None:
        try:
            sys.path.insert(0, str(ROOT))
            from core.audit_trail_immutable import ImmutableAuditTrail
            auditor = ImmutableAuditTrail()
            auditor.registrar(
                usuario="__provisioner__",
                accion="TENANT_ONBOARDING",
                recurso=f"tenant:{self.tenant_id}",
                detalle=json.dumps({
                    "tenant": self.tenant_id,
                    "region": self.region,
                    "byok": self.byok,
                    "pasos": len(self.resultado["pasos"]),
                })[:500],
            )
            self._log("Audit trail registrado", True, "Accion TENANT_ONBOARDING")
        except Exception as exc:
            self._log("Audit trail", False, str(exc)[:100])

    # ── Paso 6: KMS keys ─────────────────────────────────────

    def _paso_6_generar_claves_kms(self) -> None:
        try:
            sys.path.insert(0, str(ROOT))
            from scripts.kms_key_rotation import KMSKeyManager
            km = KMSKeyManager(region=self.region)
            key_id = km.create_key(self.tenant_id)
            if key_id:
                self._log("Clave KMS creada", True, key_id[:12] + "...")
                km.enable_auto_rotation(self.tenant_id)
                self._log("Rotacion KMS activada", True, "")
            else:
                self._log("Clave KMS", False, "No se pudo crear")
        except Exception as exc:
            self._log("Clave KMS", False, str(exc)[:100])


def main():
    parser = argparse.ArgumentParser(description="Provisionamiento automatico de tenants")
    parser.add_argument("--tenant", required=True, help="ID del tenant (ej: sancor_salud)")
    parser.add_argument("--region", default="us-east-1", help="Region AWS")
    parser.add_argument("--byok", action="store_true", help="Habilitar BYOK")
    args = parser.parse_args()

    provisioner = TenantProvisioner(args.tenant, args.region, args.byok)
    resultado = provisioner.provisionar()

    # Resumen
    print(f"\n{'='*60}")
    print(f"  RESUMEN DE PROVISIONAMIENTO: {args.tenant}")
    total = len(resultado["pasos"])
    ok = sum(1 for p in resultado["pasos"] if p["status"] == "OK")
    print(f"  Pasos: {ok}/{total} exitosos")
    if ok == total:
        print(f"  ESTADO: COMPLETO")
    else:
        print(f"  ESTADO: INCOMPLETO - revisar errores")
    print(f"{'='*60}")
    return 0 if ok == total else 1


if __name__ == "__main__":
    sys.exit(main())
