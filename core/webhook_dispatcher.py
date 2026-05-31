"""Sistema de Webhooks Outbound para integracion con prepagas.
Dispara payloads JSON firmados criptograficamente (X-Hub-Signature-256)
hacia las URL configuradas por los tenants con reintentos automaticos.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE EVENTOS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class WebhookEvent:
    """Evento para enviar a webhooks de terceros."""
    event_type: str  # "checkin.realizado" | "medicacion.administrada" | "evolucion.creada"
    tenant_id: str
    payload: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    intentos: int = 0
    max_intentos: int = 5


# ═══════════════════════════════════════════════════════════════════
# 2. DISPATCHER DE WEBHOOKS
# ═══════════════════════════════════════════════════════════════════

class WebhookDispatcher:
    """Dispatcher de webhooks con firma HMAC-SHA256 y reintentos.

    Lee las URL configuradas por tenant desde PostgreSQL o variables de entorno.
    Dispara payloads JSON firmados con secreto compartido.
    """

    TIMEOUT = 10  # segundos
    BACKOFF_BASE = 2.0

    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self.TIMEOUT,
                limits=httpx.Limits(max_keepalive_connections=50, max_connections=100),
            )
        return self._client

    async def _get_webhook_urls(self, tenant_id: str) -> list[tuple[str, str]]:
        """Obtiene URLs de webhook configuradas para un tenant.

        Returns:
            Lista de (url, secreto_compartido).
        """
        # En produccion, leer de tabla tenant_webhooks en PostgreSQL
        urls = []

        # Tambien soportar variables de entorno
        env_url = os.environ.get(f"WEBHOOK_{tenant_id.upper()}_URL")
        env_secret = os.environ.get(f"WEBHOOK_{tenant_id.upper()}_SECRET")
        if env_url and env_secret:
            urls.append((env_url, env_secret))

        return urls

    def _firmar_payload(self, payload: bytes, secreto: str) -> str:
        """Firma el payload con HMAC-SHA256.

        El webhook receptor debe verificar X-Hub-Signature-256.
        """
        return hmac.new(
            secreto.encode("utf-8"),
            payload,
            hashlib.sha256,
        ).hexdigest()

    async def disparar(self, evento: WebhookEvent) -> list[dict[str, Any]]:
        """Dispara un evento a todas las URLs del tenant.

        Returns:
            Lista de resultados de cada intento.
        """
        resultados: list[dict[str, Any]] = []
        urls = await self._get_webhook_urls(evento.tenant_id)

        if not urls:
            log_event("webhook", f"sin_urls:{evento.tenant_id}:{evento.event_type}")
            return resultados

        payload_bytes = json.dumps({
            "event_type": evento.event_type,
            "tenant_id": evento.tenant_id,
            "timestamp": evento.timestamp,
            "data": evento.payload,
        }, ensure_ascii=False, default=str).encode("utf-8")

        client = await self._get_client()

        for url, secreto in urls:
            firma = self._firmar_payload(payload_bytes, secreto)

            for intento in range(evento.max_intentos):
                try:
                    response = await client.post(
                        url,
                        content=payload_bytes,
                        headers={
                            "Content-Type": "application/json",
                            "X-Hub-Signature-256": f"sha256={firma}",
                            "X-Tenant-Id": evento.tenant_id,
                            "User-Agent": "MediCare-Webhook/2.0",
                        },
                    )

                    if response.status_code == 200:
                        resultados.append({
                            "url": url,
                            "status": 200,
                            "intento": intento + 1,
                            "ok": True,
                        })
                        log_event("webhook", f"ok:{url[:40]}:{evento.event_type}")
                        break
                    else:
                        log_event("webhook", f"http_{response.status_code}:{url[:40]}")

                except (httpx.TimeoutException, httpx.ConnectionError) as exc:
                    delay = self.BACKOFF_BASE * (2 ** intento)
                    log_event("webhook", f"retry:{intento + 1}:{url[:40]}:{type(exc).__name__}")
                    await asyncio.sleep(delay)

                if intento == evento.max_intentos - 1:
                    resultados.append({
                        "url": url,
                        "status": 0,
                        "intento": intento + 1,
                        "ok": False,
                        "error": "Maximos reintentos alcanzados",
                    })

        return resultados

    async def disparar_checkin(self, profesional_id: str, paciente_id: str,
                                lat: float, lon: float, tenant_id: str) -> None:
        """Dispara webhook cuando se realiza un check-in GPS."""
        await self.disparar(WebhookEvent(
            event_type="checkin.realizado",
            tenant_id=tenant_id,
            payload={
                "profesional_id": profesional_id,
                "paciente_id": paciente_id,
                "latitud": lat,
                "longitud": lon,
                "timestamp": time.time(),
            },
        ))

    async def disparar_medicacion(
        self, profesional_id: str, paciente_id: str,
        medicamento: str, dosis: str, tenant_id: str,
    ) -> None:
        """Dispara webhook cuando se administra una medicacion."""
        await self.disparar(WebhookEvent(
            event_type="medicacion.administrada",
            tenant_id=tenant_id,
            payload={
                "profesional_id": profesional_id,
                "paciente_id": paciente_id,
                "medicamento": medicamento,
                "dosis": dosis,
                "timestamp": time.time(),
            },
        ))

    async def cerrar(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
