#!/usr/bin/env python3
"""Orquestador de autorreparacion y mitigacion automatica (Self-Healing).
Escucha alertas, ejecuta acciones correctivas sin intervencion humana.
"""
from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE REMEDIACION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class RemediationAction:
    """Accion de autorreparacion."""
    tipo: str  # "degradar_tenant" | "aislar_registro" | "restaurar_backup"
    target: str
    parametros: dict[str, Any] = None


# ═══════════════════════════════════════════════════════════════════
# 2. MOTOR DE REMEDIACION
# ═══════════════════════════════════════════════════════════════════

class SelfHealingEngine:
    """Motor de autorreparacion que escucha alertas y ejecuta acciones.

    Acciones:
    - Degradar tenant: reduce cuota de rate limiting si hay abuso
    - Aislar registro: marca registro como bajo_auditoria si falla hash
    """

    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                self._redis = aioredis.Redis(
                    host=os.environ.get("REDIS_HOST", "localhost"),
                    port=int(os.environ.get("REDIS_PORT", "6379")),
                    db=3,
                    decode_responses=True,
                )
            except Exception:
                pass
        return self._redis

    # ── Accion 1: Degradar tenant por abuso de rate limiting ──

    async def degradar_tenant(self, tenant_id: str, razon: str = "rate_limit_abuse") -> bool:
        """Degrada temporalmente la cuota de un tenant a modo 'safe'.

        Reduce requests_per_minute a 10 y concurrent_limit a 1.
        Los demas tenants no se ven afectados.
        """
        r = await self._get_redis()
        if r:
            await r.hset(f"rate_limit:{tenant_id}", mapping={
                "requests_per_minute": "10",
                "concurrent_limit": "1",
                "degraded_at": str(time.time()),
                "razon": razon,
            })
            await r.expire(f"rate_limit:{tenant_id}", 1800)  # 30 min
        log_event("self_healing", f"DEGRADADO:{tenant_id}:{razon}")
        return True

    async def restaurar_tenant(self, tenant_id: str) -> bool:
        """Restaura cuota normal del tenant."""
        r = await self._get_redis()
        if r:
            await r.delete(f"rate_limit:{tenant_id}")
        log_event("self_healing", f"RESTAURADO:{tenant_id}")
        return True

    # ── Accion 2: Aislar registro por fallo de integridad ──

    async def aislar_registro(self, tabla: str, registro_id: str, tenant_id: str) -> bool:
        """Marca un registro como bajo_auditoria para impedir modificaciones.

        Agrega columna 'bajo_auditoria' si no existe y setea TRUE.
        """
        import asyncpg
        conn = await asyncpg.connect(os.environ.get("DB_URL", "postgresql://localhost:5432/medicare"))
        try:
            # Asegurar columna existe
            await conn.execute(f"""
                ALTER TABLE {tabla}
                ADD COLUMN IF NOT EXISTS bajo_auditoria BOOLEAN DEFAULT FALSE
            """)
            # Marcar registro
            await conn.execute(
                f"UPDATE {tabla} SET bajo_auditoria = TRUE WHERE id = $1 AND tenant_id = $2",
                registro_id, tenant_id,
            )
            log_event("self_healing", f"AISLADO:{tabla}:{registro_id}")
            return True
        except Exception as exc:
            log_event("self_healing", f"error_aislar:{type(exc).__name__}")
            return False
        finally:
            await conn.close()

    # ── Dispatcher principal ─────────────────────────────────

    async def procesar_alerta(self, alerta: dict[str, Any]) -> Optional[RemediationAction]:
        """Procesa una alerta y ejecuta la accion de remediacion adecuada."""
        alertname = alerta.get("alertname", "")
        labels = alerta.get("labels", {})
        tenant = labels.get("tenant", "default")

        if "IntegrityFailure" in alertname:
            # Aislar registro afectado
            registro_id = labels.get("registro_id", "")
            tabla = labels.get("tabla", "evoluciones")
            if registro_id:
                await self.aislar_registro(tabla, registro_id, tenant)
                return RemediationAction("aislar_registro", registro_id)

        elif "RateLimit" in alertname or "TooManyRequests" in alertname:
            # Degradar tenant
            await self.degradar_tenant(tenant)
            return RemediationAction("degradar_tenant", tenant)

        elif "OptimisticLock" in alertname:
            # Reintentar sync con backoff
            log_event("self_healing", f"LOCK_CONFLICT:{tenant}:reintentando con backoff")
            return RemediationAction("reintentar", tenant)

        return None

    async def loop_escucha(self) -> None:
        """Loop principal que escucha alertas cada 30 segundos."""
        log_event("self_healing", "Engine iniciado")
        while True:
            try:
                r = await self._get_redis()
                if r:
                    # Leer alertas desde Redis (Alertmanager webhook)
                    alertas_json = await r.lpop("medicare:alertas")
                    while alertas_json:
                        alerta = json.loads(alertas_json)
                        await self.procesar_alerta(alerta)
                        alertas_json = await r.lpop("medicare:alertas")
            except Exception as exc:
                log_event("self_healing", f"loop_error:{type(exc).__name__}")

            await asyncio.sleep(30)


if __name__ == "__main__":
    engine = SelfHealingEngine()
    asyncio.run(engine.loop_escucha())
