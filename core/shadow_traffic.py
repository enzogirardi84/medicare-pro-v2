"""Shadow Traffic / Dark Launching para FastAPI.
Duplica payloads entrantes de forma asincrona y no bloqueante,
los anonimiza y los envia a un entorno Sandbox para pruebas.
La respuesta del sandbox se descarta para el cliente final.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional, Callable

import httpx

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. ANONIMIZADOR DE SHADOW TRAFFIC
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ShadowConfig:
    """Configuracion del entorno shadow."""
    sandbox_url: str = "https://sandbox.medicare-pro.app"
    api_key: str = ""
    timeout: float = 30.0
    sample_rate: float = 1.0       # 0.0-1.0, porcentaje de requests a espejar
    max_payload_size: int = 1_000_000  # 1MB max


class ShadowAnonymizer:
    """Anonimiza payloads en caliente para shadow traffic.

    Aplica las mismas reglas que data_masking.sql pero en Python:
    - Hash truncado de nombres (SHA256 primeros 8 chars)
    - DNI enmascarado (***NNN)
    - Rango de edad en vez de fecha exacta
    - Cuadrante geografico (0.1 grado)
    """

    @staticmethod
    def hash_name(name: str) -> str:
        if not name:
            return ""
        return hashlib.sha256(name.encode("utf-8")).hexdigest()[:8]

    @staticmethod
    def mask_dni(dni: str) -> str:
        if not dni:
            return ""
        return f"***{dni[-3:]}" if len(dni) >= 3 else "***"

    @staticmethod
    def age_range(birth_date: Optional[str]) -> str:
        if not birth_date:
            return "S/D"
        try:
            from datetime import datetime
            bd = datetime.fromisoformat(birth_date)
            age = (datetime.now() - bd).days / 365.25
            if age < 18: return "0-17"
            if age < 30: return "18-29"
            if age < 50: return "30-49"
            if age < 65: return "50-64"
            return "65+"
        except (ValueError, TypeError):
            return "S/D"

    @staticmethod
    def round_coord(lat: Optional[float], lon: Optional[float]) -> tuple:
        if lat is None or lon is None:
            return (None, None)
        return (round(lat, 1), round(lon, 1))

    def anonymize_payload(self, payload: dict) -> dict:
        """Anonimiza un payload completo con las reglas de masking."""
        result = {}
        for key, value in payload.items():
            if key in ("nombre", "nombre_completo", "patient_name"):
                result[key] = self.hash_name(str(value))
            elif key in ("dni", "documento", "document_number"):
                result[key] = self.mask_dni(str(value))
            elif key in ("fecha_nacimiento", "birth_date"):
                result[key] = self.age_range(str(value) if value else None)
            elif key in ("lat", "latitud", "latitude"):
                result[key] = round(float(value), 1) if value else None
            elif key in ("lon", "longitud", "longitude"):
                result[key] = round(float(value), 1) if value else None
            elif isinstance(value, dict):
                result[key] = self.anonymize_payload(value)
            elif isinstance(value, list):
                result[key] = [
                    self.anonymize_payload(item) if isinstance(item, dict) else item
                    for item in value
                ]
            else:
                result[key] = value
        return result


# ═══════════════════════════════════════════════════════════════════
# 2. DISPATCHER SHADOW
# ═══════════════════════════════════════════════════════════════════

class ShadowDispatcher:
    """Dispatcher de shadow traffic no bloqueante.

    Encola los payloads anonimizados y los envia al sandbox
    en background sin afectar la respuesta al cliente.
    """

    def __init__(self, config: Optional[ShadowConfig] = None):
        self._config = config or ShadowConfig()
        self._anonymizer = ShadowAnonymizer()
        self._client: Optional[httpx.AsyncClient] = None
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._worker_task: Optional[asyncio.Task] = None
        self._stats: dict[str, int] = {
            "mirrored": 0,
            "sent": 0,
            "failed": 0,
            "dropped": 0,
        }

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=self._config.timeout,
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
            )
        return self._client

    def _should_sample(self) -> bool:
        return random.random() < self._config.sample_rate

    async def mirror_request(self, method: str, path: str,
                             headers: dict, payload: dict) -> None:
        """Espeja un request al sandbox de forma no bloqueante.

        Args:
            method: HTTP method original.
            path: Ruta del endpoint (ej. /sync/batch).
            headers: Headers originales (se filtran antes de enviar).
            payload: Payload completo del request.
        """
        if not self._should_sample():
            return

        payload_bytes = json.dumps(payload, default=str).encode("utf-8")
        if len(payload_bytes) > self._config.max_payload_size:
            self._stats["dropped"] += 1
            return

        anon_payload = self._anonymizer.anonymize_payload(payload)
        shadow_entry = {
            "method": method,
            "path": path,
            "headers": {k: v for k, v in headers.items()
                        if k.lower() not in ("authorization", "cookie", "x-api-key")},
            "payload": anon_payload,
            "mirrored_at": time.time(),
            "original_size": len(payload_bytes),
        }

        try:
            self._queue.put_nowait(shadow_entry)
            self._stats["mirrored"] += 1
        except asyncio.QueueFull:
            self._stats["dropped"] += 1

        # Asegurar worker activo
        self._ensure_worker()

    def _ensure_worker(self):
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._worker_loop())

    async def _worker_loop(self):
        """Worker background que drena la cola y envia al sandbox."""
        client = await self._get_client()
        headers = {"Content-Type": "application/json"}
        if self._config.api_key:
            headers["X-Sandbox-Api-Key"] = self._config.api_key

        while True:
            try:
                entry = await asyncio.wait_for(self._queue.get(), timeout=2.0)
            except asyncio.TimeoutError:
                if self._queue.empty():
                    break
                continue

            try:
                response = await client.post(
                    f"{self._config.sandbox_url.rstrip('/')}/shadow/ingest",
                    json=entry,
                    headers=headers,
                )
                if response.status_code == 200:
                    self._stats["sent"] += 1
                else:
                    self._stats["failed"] += 1
            except Exception:
                self._stats["failed"] += 1

    def get_stats(self) -> dict:
        return dict(self._stats)

    async def close(self):
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except (asyncio.CancelledError, RuntimeError):
                pass
        if self._client:
            await self._client.aclose()
            self._client = None


# ═══════════════════════════════════════════════════════════════════
# 3. FASTAPI MIDDLEWARE (ejemplo de integracion)
# ═══════════════════════════════════════════════════════════════════

FASTAPI_MIDDLEWARE_SHADOW = """
# Registrar en la app FastAPI:
#
# from core.shadow_traffic import ShadowDispatcher, ShadowConfig
# shadow = ShadowDispatcher(ShadowConfig(sandbox_url="https://sandbox...", sample_rate=0.5))
# app.add_middleware(ShadowTrafficMiddleware, dispatcher=shadow)

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import json


class ShadowTrafficMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, dispatcher: ShadowDispatcher,
                 mirror_paths: list[str] = None):
        super().__init__(app)
        self.dispatcher = dispatcher
        self.mirror_paths = mirror_paths or ["/sync/batch", "/sync/delta",
                                              "/api/v2/evoluciones"]

    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)

        if request.method in ("POST", "PUT", "PATCH"):
            path = request.url.path
            if any(path.startswith(p) for p in self.mirror_paths):
                try:
                    body = await request.json()
                    asyncio.create_task(self.dispatcher.mirror_request(
                        method=request.method,
                        path=path,
                        headers=dict(request.headers),
                        payload=body,
                    ))
                except Exception:
                    pass  # shadow nunca debe romper el flujo principal

        return response
"""

import random


__all__ = [
    "ShadowDispatcher",
    "ShadowConfig",
    "ShadowAnonymizer",
    "FASTAPI_MIDDLEWARE_SHADOW",
]
