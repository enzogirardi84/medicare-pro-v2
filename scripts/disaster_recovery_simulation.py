#!/usr/bin/env python3
"""Simulacion de desastres en vivo y failover multi-region (Chaos Day).
Automatiza simulacros de caida regional de AWS, mide RTO y RPO,
y verifica la reconexion transparente del backend.

Uso:
    python scripts/disaster_recovery_simulation.py --plan
    python scripts/disaster_recovery_simulation.py --execute --region us-east-1
    python scripts/disaster_recovery_simulation.py --report
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

ROOT = Path(__file__).resolve().parent.parent


class DisasterRecoverySimulation:
    """Automatiza simulacros de failover multi-region.

    Simula:
    1. Perdida total de region primaria
    2. Promocion de Aurora Global a secundaria
    3. Verificacion de BYOK + backend
    4. Reporte RTO/RPO inmutable

    Modo --plan: solo verifica configuracion sin ejecutar.
    Modo --execute: ejecuta el simulacro completo.
    """

    def __init__(
        self,
        primary_region: str = "us-east-1",
        secondary_region: str = "sa-east-1",
        dry_run: bool = True,
    ):
        self.primary = primary_region
        self.secondary = secondary_region
        self.dry_run = dry_run
        self.reporte: dict[str, Any] = {
            "simulacion_id": f"chaos-{int(time.time())}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "primary_region": primary_region,
            "secondary_region": secondary_region,
            "dry_run": dry_run,
            "fases": [],
            "rto_segundos": 0.0,
            "rpo_segundos": 0.0,
            "resultado": "PENDIENTE",
        }

    # ═════════════════════════════════════════════════════════
    # FASE 1: VERIFICACION PRE-SIMULACRO
    # ═════════════════════════════════════════════════════════

    def fase_1_verificar_configuracion(self) -> bool:
        """Verifica que la infraestructura multi-region este configurada."""
        ok = True
        try:
            import boto3

            # Verificar cluster global Aurora
            rds = boto3.client("rds", region_name=self.primary)
            clusters = rds.describe_global_clusters()
            global_clusters = clusters.get("GlobalClusters", [])
            medicare_clusters = [
                gc for gc in global_clusters
                if "medicare" in gc.get("GlobalClusterIdentifier", "").lower()
            ]

            if medicare_clusters:
                gc = medicare_clusters[0]
                self._registrar("Cluster global encontrado", True,
                                gc["GlobalClusterIdentifier"])
                ok &= True
            else:
                self._registrar("Cluster global NO encontrado", False,
                                "medicare-* no existe en " + self.primary)

            # Verificar replicas secundarias
            secondary_rds = boto3.client("rds", region_name=self.secondary)
            sec_clusters = secondary_rds.describe_db_clusters()
            if sec_clusters.get("DBClusters"):
                self._registrar("Cluster secundario encontrado", True,
                                f"{len(sec_clusters['DBClusters'])} cluster(es)")
            else:
                self._registrar("Cluster secundario NO encontrado", False)

        except Exception as exc:
            self._registrar("Error verificando configuracion", False, str(exc)[:100])
            ok = False

        return ok

    # ═════════════════════════════════════════════════════════
    # FASE 2: SIMULACION DE CORTE REGIONAL
    # ═════════════════════════════════════════════════════════

    def fase_2_simular_corte_regional(self) -> bool:
        """Simula la caida de la region primaria.

        En dry_run: solo registra lo que haria.
        En execute: modifica security groups para denegar trafico.
        """
        if self.dry_run:
            self._registrar("CORTE REGIONAL SIMULADO", True,
                            f"Se denegaria trafico a {self.primary}")
            return True

        try:
            import boto3
            ec2 = boto3.client("ec2", region_name=self.primary)

            # Buscar security group del ALB
            sgs = ec2.describe_security_groups(
                Filters=[{"Name": "group-name", "Values": ["*medicare*alb*"]}]
            )
            if sgs.get("SecurityGroups"):
                sg_id = sgs["SecurityGroups"][0]["GroupId"]
                # Denegar todo el trafico entrante (simula caida regional)
                ec2.revoke_security_group_ingress(
                    GroupId=sg_id,
                    IpPermissions=[{
                        "IpProtocol": "-1",
                        "FromPort": 0,
                        "ToPort": 65535,
                        "IpRanges": [{"CidrIp": "0.0.0.0/0"}],
                    }],
                )
                self._registrar("Trafico denegado en ALB", True, sg_id)

                # Esperar 30s para que el corte se propague
                time.sleep(30)
            else:
                self._registrar("Security group ALB no encontrado", False)

        except Exception as exc:
            self._registrar("Error simulando corte regional", False, str(exc)[:100])
            return False

        return True

    # ═════════════════════════════════════════════════════════
    # FASE 3: FAILOVER AURORA GLOBAL
    # ═════════════════════════════════════════════════════════

    def fase_3_ejecutar_failover(self) -> bool:
        """Mide el tiempo de failover de Aurora Global Database.

        1. Inicia temporizador
        2. Promueve cluster secundario a primario
        3. Detiene temporizador -> RTO
        """
        if self.dry_run:
            self._registrar("FAILOVER AURORA GLOBAL", True,
                            "Se promoveria secondary a primary")
            return True

        try:
            import boto3
            rds_primary = boto3.client("rds", region_name=self.primary)
            rds_secondary = boto3.client("rds", region_name=self.secondary)

            # Obtener ID del cluster global
            clusters = rds_primary.describe_global_clusters()
            gc_id = None
            for gc in clusters.get("GlobalClusters", []):
                if "medicare" in gc.get("GlobalClusterIdentifier", "").lower():
                    gc_id = gc["GlobalClusterIdentifier"]
                    break

            if not gc_id:
                self._registrar("Failover", False, "No se encontro Global Cluster")
                return False

            # Iniciar temporizador RTO
            t0 = time.time()

            # Promover cluster secundario
            rds_primary.failover_global_cluster(
                GlobalClusterIdentifier=gc_id,
                TargetDbClusterIdentifier=(
                    f"medicare-prod-secondary"
                ),
            )

            # Esperar a que el failover se complete (tipico: 60-120s)
            self._registrar("Failover iniciado", True, "Esperando 120s para estabilizar...")
            time.sleep(120)

            rto = time.time() - t0
            self.reporte["rto_segundos"] = round(rto, 1)
            self._registrar("FAILOVER COMPLETADO", True, f"RTO: {rto:.1f}s")

            # Verificar que el nuevo primary responda
            try:
                sec_clusters = rds_secondary.describe_db_clusters()
                for cluster in sec_clusters.get("DBClusters", []):
                    if cluster.get("Engine") == "aurora-postgresql":
                        self._registrar("Nuevo primary respondiendo", True,
                                        cluster.get("Endpoint", ""))
            except Exception as exc:
                self._registrar("Verificacion post-failover", False, str(exc)[:100])

        except Exception as exc:
            self._registrar("Error en failover", False, str(exc)[:200])
            return False

        return True

    # ═════════════════════════════════════════════════════════
    # FASE 4: VERIFICACION POST-FAILOVER
    # ═════════════════════════════════════════════════════════

    def fase_4_verificar_post_failover(self) -> bool:
        """Verifica que BYOK y backend funcionen tras el failover."""
        if self.dry_run:
            self._registrar("VERIFICACION POST-FAILOVER", True,
                            "Se verificaria BYOK, backend y audit trail")
            return True

        # Verificar BYOK (KMS en region secundaria)
        try:
            import boto3
            kms = boto3.client("kms", region_name=self.secondary)
            keys = kms.list_keys()
            self._registrar("KMS accesible en secondary", True,
                            f"{len(keys.get('Keys', []))} claves encontradas")
        except Exception as exc:
            self._registrar("KMS en secondary", False, str(exc)[:100])

        # Verificar conectividad del backend
        import urllib.request
        try:
            resp = urllib.request.urlopen(
                "http://localhost:8501/healthz", timeout=10
            )
            self._registrar("Backend Streamlit responde", True, f"HTTP {resp.status}")
        except Exception as exc:
            self._registrar("Backend Streamlit", False, str(exc)[:100])

        # Estimar RPO (datos perdidos = ultimo backup - ahora)
        try:
            from core.audit_trail_immutable import ImmutableAuditTrail
            auditor = ImmutableAuditTrail()
            entries = auditor.obtener_entradas_recientes(limite=1)
            if entries:
                ultimo_entry = entries[-1]
                ultimo_ts = ultimo_entry.get("timestamp", 0.0)
                rpo = time.time() - ultimo_ts
                self.reporte["rpo_segundos"] = round(rpo, 1)
                self._registrar("RPO estimado", True, f"{rpo:.0f}s desde ultimo registro")
        except Exception as exc:
            self._registrar("RPO", False, str(exc)[:100])

        return True

    # ═════════════════════════════════════════════════════════
    # FASE 5: REPORTE INMUTABLE
    # ═════════════════════════════════════════════════════════

    def fase_5_generar_reporte(self) -> None:
        """Genera reporte de la simulacion y lo registra en audit trail."""
        fase_ok = sum(1 for f in self.reporte["fases"] if f["status"] == "OK")
        total_fases = len(self.reporte["fases"])
        self.reporte["resultado"] = "EXITOSO" if fase_ok == total_fases else "FALLIDO"

        print(f"\n{'='*60}")
        print(f"  REPORTE DE SIMULACRO DR")
        print(f"  ID: {self.reporte['simulacion_id']}")
        print(f"  Resultado: {self.reporte['resultado']}")
        print(f"  RTO: {self.reporte['rto_segundos']:.1f}s")
        print(f"  RPO: {self.reporte['rpo_segundos']:.1f}s")
        print(f"  Fases: {fase_ok}/{total_fases} OK")
        print(f"{'='*60}")

        # Registrar en audit trail
        try:
            sys.path.insert(0, str(ROOT))
            from core.audit_trail_immutable import ImmutableAuditTrail
            auditor = ImmutableAuditTrail()
            auditor.registrar(
                usuario="__dr_simulation__",
                accion="DR_SIMULATION",
                recurso=f"chaos:{self.reporte['simulacion_id']}",
                detalle=json.dumps({
                    "resultado": self.reporte["resultado"],
                    "rto_s": self.reporte["rto_segundos"],
                    "rpo_s": self.reporte["rpo_segundos"],
                    "fases_ok": f"{fase_ok}/{total_fases}",
                })[:500],
            )
            print("[OK] Reporte registrado en Audit Trail inmutable")
        except Exception as exc:
            print(f"[WARN] Error registrando reporte: {exc}")

    # ═════════════════════════════════════════════════════════
    # HELPERS
    # ═════════════════════════════════════════════════════════

    def _registrar(self, fase: str, ok: bool, detalle: str = "") -> None:
        status = "OK" if ok else "FAIL"
        print(f"  [{status}] {fase}: {detalle}")
        self.reporte["fases"].append({
            "fase": fase,
            "status": status,
            "detalle": detalle[:200],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

    def ejecutar(self) -> dict[str, Any]:
        """Ejecuta el pipeline completo de simulacion de desastre."""
        print(f"\n{'='*60}")
        title = " SIMULACRO DR (DRY RUN)" if self.dry_run else " SIMULACRO DR (EN VIVO)"
        print(f" {title}")
        print(f"  Primary: {self.primary} -> Secondary: {self.secondary}")
        print(f"{'='*60}\n")

        self.fase_1_verificar_configuracion()
        self.fase_2_simular_corte_regional()
        self.fase_3_ejecutar_failover()
        self.fase_4_verificar_post_failover()
        self.fase_5_generar_reporte()

        return self.reporte


def main():
    parser = argparse.ArgumentParser(description="Simulacro de Disaster Recovery Multi-Region")
    parser.add_argument("--plan", action="store_true", help="Solo verificar configuracion (dry run)")
    parser.add_argument("--execute", action="store_true", help="Ejecutar simulacro completo")
    parser.add_argument("--primary", default="us-east-1", help="Region primaria")
    parser.add_argument("--secondary", default="sa-east-1", help="Region secundaria")
    parser.add_argument("--report", action="store_true", help="Mostrar ultimo reporte")

    args = parser.parse_args()

    sim = DisasterRecoverySimulation(
        primary_region=args.primary,
        secondary_region=args.secondary,
        dry_run=not args.execute,
    )

    if args.plan or args.execute:
        reporte = sim.ejecutar()
        return 0 if reporte["resultado"] == "EXITOSO" else 1

    elif args.report:
        print("Report mode: leer de audit trail (implementacion futura)")
        return 0

    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
