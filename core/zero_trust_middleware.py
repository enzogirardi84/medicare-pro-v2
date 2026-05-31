"""Middleware de Confianza Cero (Zero-Trust) para FastAPI.
Implementa Device Attestation, Single-Use Signed URLs y
bloqueo automatico IP/Tenant via Redis por firmas ECDSA invalidas.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. DEVICE ATTESTATION — Verificacion de hardware
# ═══════════════════════════════════════════════════════════════════

@dataclass
class DeviceAttestation:
    """Metadatos de hardware firmados por el dispositivo movil.

    El dispositivo genera esta estructura, la firma con su clave ECDSA
    y la envia en el header X-Device-Attestation.
    """
    device_id: str
    hardware_hash: str            # SHA256 de serial number + board + manufacturer
    os_version: str
    app_version: str
    timestamp: float
    nonce: str = ""               # anti-replay

    def to_canonical(self) -> bytes:
        return json.dumps({
            "device_id": self.device_id,
            "hardware_hash": self.hardware_hash,
            "os_version": self.os_version,
            "app_version": self.app_version,
            "timestamp": self.timestamp,
            "nonce": self.nonce,
        }, sort_keys=True, default=str).encode("utf-8")


class DeviceAttestationVerifier:
    """Verifica la procedencia hardware de las peticiones.

    Requiere que el dispositivo haya registrado su clave publica
    y hash de hardware durante el enrolamiento inicial.
    """

    def __init__(self):
        self._trusted_devices: dict[str, dict] = {}  # device_id -> {public_key, hardware_hash}
        self._nonce_cache: set[str] = set()

    def register_device(self, device_id: str, public_key_pem: str,
                        hardware_hash: str) -> None:
        """Registra un dispositivo de confianza (durante enrolamiento)."""
        self._trusted_devices[device_id] = {
            "public_key": public_key_pem,
            "hardware_hash": hardware_hash,
            "registered_at": time.time(),
        }
        log_event("zero_trust", f"device_registered:{device_id}")

    def verify(self, attestation: DeviceAttestation, signature_hex: str,
               signature_verifier: Callable) -> bool:
        """Verifica la atestacion del dispositivo.

        Args:
            attestation: Metadatos de hardware.
            signature_hex: Firma ECDSA de los metadatos.
            signature_verifier: Funcion (pub_key, payload, sig) -> bool.

        Returns:
            True si la atestacion es valida.
        """
        # 1. Dispositivo conocido?
        if attestation.device_id not in self._trusted_devices:
            log_event("zero_trust", f"unknown_device:{attestation.device_id}")
            return False

        trusted = self._trusted_devices[attestation.device_id]

        # 2. Hardware hash coincide?
        if attestation.hardware_hash != trusted["hardware_hash"]:
            log_event("zero_trust", f"hardware_mismatch:{attestation.device_id}")
            return False

        # 3. Anti-replay: nonce no usado antes
        if attestation.nonce in self._nonce_cache:
            log_event("zero_trust", f"nonce_replay:{attestation.device_id}:{attestation.nonce[:16]}")
            return False
        self._nonce_cache.add(attestation.nonce)

        # 4. Timestamp vigente (+- 30s)
        now = time.time()
        if abs(now - attestation.timestamp) > 30:
            log_event("zero_trust", f"timestamp_stale:{attestation.device_id}:delta={now - attestation.timestamp:.0f}s")
            return False

        # 5. Verificar firma ECDSA
        canonical = attestation.to_canonical()
        if not signature_verifier(trusted["public_key"], canonical, signature_hex):
            log_event("zero_trust", f"signature_invalid:{attestation.device_id}")
            return False

        return True


# ═══════════════════════════════════════════════════════════════════
# 2. SINGLE-USE SIGNED URLS — Endpoints efimeros
# ═══════════════════════════════════════════════════════════════════

@dataclass
class SignedEndpoint:
    """Endpoint firmado de un solo uso."""
    original_path: str
    signed_path: str
    token: str
    expires_at: float
    used: bool = False
    tenant_id: str = ""


class SignedURLManager:
    """Genera y verifica URLs firmadas de un solo uso.

    El servidor expone el endpoint real bajo un hash HMAC efimero.
    El cliente recibe la URL firmada via el handshake inicial.
    """

    def __init__(self):
        self._master_secret = os.environ.get(
            "SIGNED_URL_SECRET",
            hashlib.sha256(str(uuid.uuid4()).encode()).hexdigest()[:32],
        )
        self._active_endpoints: dict[str, SignedEndpoint] = {}
        self._used_tokens: set[str] = set()

    def generate_endpoint(self, original_path: str, tenant_id: str,
                          ttl: float = 300.0) -> SignedEndpoint:
        """Genera un endpoint firmado de un solo uso.

        Args:
            original_path: Ruta real del endpoint (ej. /sync/batch).
            tenant_id: Tenant que solicita el endpoint.
            ttl: Tiempo de validez en segundos (default 5 min).

        Returns:
            SignedEndpoint con signed_path y token.
        """
        token = hashlib.sha256(
            f"{tenant_id}:{original_path}:{uuid.uuid4()}:{time.time()}".encode(),
        ).hexdigest()[:32]

        signature = hmac.new(
            self._master_secret.encode(),
            f"{original_path}:{token}:{tenant_id}".encode(),
            hashlib.sha256,
        ).hexdigest()[:16]

        signed_path = f"/_/{signature}/{token}{original_path}"

        endpoint = SignedEndpoint(
            original_path=original_path,
            signed_path=signed_path,
            token=token,
            expires_at=time.time() + ttl,
            tenant_id=tenant_id,
        )
        self._active_endpoints[signed_path] = endpoint
        log_event("zero_trust", f"signed_url_issued:{original_path}:{tenant_id}")
        return endpoint

    def verify_and_resolve(self, signed_path: str) -> Optional[str]:
        """Verifica y resuelve una URL firmada a su path original.

        Returns:
            original_path si es valido, None si no.
        """
        endpoint = self._active_endpoints.get(signed_path)
        if not endpoint:
            return None

        # Expirado?
        if time.time() > endpoint.expires_at:
            del self._active_endpoints[signed_path]
            log_event("zero_trust", f"signed_url_expired:{signed_path[:40]}")
            return None

        # Ya usado?
        if endpoint.token in self._used_tokens:
            log_event("zero_trust", f"signed_url_reused:{signed_path[:40]}")
            return None

        # Marcar como usado (single-use)
        self._used_tokens.add(endpoint.token)
        endpoint.used = True
        del self._active_endpoints[signed_path]

        return endpoint.original_path

    def revoke_tenant_endpoints(self, tenant_id: str) -> int:
        """Revoca todos los endpoints activos de un tenant."""
        count = 0
        to_delete = [
            path for path, ep in self._active_endpoints.items()
            if ep.tenant_id == tenant_id
        ]
        for path in to_delete:
            del self._active_endpoints[path]
            count += 1
        log_event("zero_trust", f"revoked_tenant_endpoints:{tenant_id}:{count}")
        return count


# ═══════════════════════════════════════════════════════════════════
# 3. BLOQUEO IP/TENANT VIA REDIS (por firmas ECDSA invalidas)
# ═══════════════════════════════════════════════════════════════════

class BlockingManager:
    """Bloqueo automatico de IPs y tenants por actividad sospechosa.

    Usa Redis para persistencia distribuida del estado de bloqueo.
    """

    BLOCK_THRESHOLD = 5       # fallos consecutivos antes de bloquear
    BLOCK_TTL_SECONDS = 900   # 15 min de bloqueo
    TENANT_BLOCK_THRESHOLD = 3  # dispositivos diferentes fallando -> bloquea tenant completo

    def __init__(self):
        self._redis = None

    async def _get_redis(self):
        if self._redis is None:
            try:
                import redis.asynced as aioredis
                self._redis = aioredis.Redis(
                    host=os.environ.get("REDIS_HOST", "localhost"),
                    port=int(os.environ.get("REDIS_PORT", "6379")),
                    db=4,
                    decode_responses=True,
                )
            except Exception:
                pass
        return self._redis

    async def record_invalid_signature(self, ip: str, tenant_id: str,
                                       device_id: str = "") -> Optional[str]:
        """Registra una firma invalida y decide si bloquear.

        Returns:
            "ip" | "tenant" | None segun que se bloqueo.
        """
        r = await self._get_redis()
        if not r:
            return None

        # Contador por IP
        ip_key = f"zt:fail:ip:{ip}"
        ip_count = await r.incr(ip_key)
        if ip_count == 1:
            await r.expire(ip_key, 300)  # ventana de 5 min

        # Contador por tenant (por dispositivo)
        tenant_key = f"zt:fail:tenant:{tenant_id}:devices"
        await r.sadd(tenant_key, device_id or ip)
        await r.expire(tenant_key, 600)
        tenant_device_count = await r.scard(tenant_key)

        # Bloquear IP si supera umbral
        if ip_count >= self.BLOCK_THRESHOLD:
            block_key = f"zt:blocked:ip:{ip}"
            await r.setex(block_key, self.BLOCK_TTL_SECONDS, "1")
            log_event("zero_trust", f"ip_blocked:{ip}:{ip_count} fallos")
            return "ip"

        # Bloquear tenant si muchos dispositivos fallan
        if tenant_device_count >= self.TENANT_BLOCK_THRESHOLD:
            block_key = f"zt:blocked:tenant:{tenant_id}"
            await r.setex(block_key, self.BLOCK_TTL_SECONDS, "1")
            log_event("zero_trust", f"tenant_blocked:{tenant_id}:{tenant_device_count} dispositivos")
            return "tenant"

        return None

    async def is_blocked(self, ip: str, tenant_id: str) -> bool:
        """Verifica si una IP o tenant estan bloqueados."""
        r = await self._get_redis()
        if not r:
            return False
        ip_blocked = await r.exists(f"zt:blocked:ip:{ip}")
        tenant_blocked = await r.exists(f"zt:blocked:tenant:{tenant_id}")
        return bool(ip_blocked) or bool(tenant_blocked)

    async def unblock_ip(self, ip: str) -> bool:
        r = await self._get_redis()
        if not r:
            return False
        result = await r.delete(f"zt:blocked:ip:{ip}")
        return result > 0

    async def unblock_tenant(self, tenant_id: str) -> bool:
        r = await self._get_redis()
        if not r:
            return False
        result = await r.delete(f"zt:blocked:tenant:{tenant_id}")
        return result > 0


# ═══════════════════════════════════════════════════════════════════
# 4. MIDDLEWARE FASTAPI COMPUESTO
# ═══════════════════════════════════════════════════════════════════

FASTAPI_MIDDLEWARE_CODE = """
# Registrar en la app FastAPI principal:
#
# from core.zero_trust_middleware import (
#     DeviceAttestationVerifier,
#     SignedURLManager,
#     BlockingManager,
#     ZeroTrustMiddleware,
# )
#
# zt_devices = DeviceAttestationVerifier()
# zt_urls = SignedURLManager()
# zt_blocking = BlockingManager()
#
# app.add_middleware(ZeroTrustMiddleware,
#     device_verifier=zt_devices,
#     url_manager=zt_urls,
#     blocking_manager=zt_blocking,
#     signature_verifier=ecdsa_verify_function,
#     protected_paths=["/sync/batch", "/sync/delta", "/api/v2/evoluciones"],
# )

import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse

from core.app_logging import log_event


class ZeroTrustMiddleware(BaseHTTPMiddleware):
    def __init__(
        self, app,
        device_verifier: DeviceAttestationVerifier,
        url_manager: SignedURLManager,
        blocking_manager: BlockingManager,
        signature_verifier: Callable,
        protected_paths: list[str] = None,
    ):
        super().__init__(app)
        self.device_verifier = device_verifier
        self.url_manager = url_manager
        self.blocking_manager = blocking_manager
        self.signature_verifier = signature_verifier
        self.protected_paths = protected_paths or []

    async def dispatch(self, request: Request, call_next) -> Response:
        client_ip = request.client.host if request.client else "0.0.0.0"
        tenant_id = request.headers.get("X-Tenant-Id", "unknown")
        path = request.url.path

        # 1. Verificar bloqueo IP/tenant
        if await self.blocking_manager.is_blocked(client_ip, tenant_id):
            log_event("zero_trust", f"request_blocked:{client_ip}:{tenant_id}")
            return JSONResponse(
                status_code=403,
                content={"error": "access_denied", "reason": "temporarily_blocked"},
            )

        # 2. Verificar device attestation en endpoints protegidos
        if any(path.startswith(p) for p in self.protected_paths):
            attest_header = request.headers.get("X-Device-Attestation", "")
            sig_header = request.headers.get("X-Device-Signature", "")
            if not attest_header or not sig_header:
                return JSONResponse(
                    status_code=401,
                    content={"error": "device_attestation_required"},
                )

            # Parsear attestation (simplificado)
            import json
            try:
                att_data = json.loads(attest_header)
                attestation = DeviceAttestation(**att_data)
            except (json.JSONDecodeError, TypeError, ValueError):
                await self.blocking_manager.record_invalid_signature(
                    client_ip, tenant_id, "unknown"
                )
                return JSONResponse(
                    status_code=401,
                    content={"error": "invalid_attestation"},
                )

            valid = self.device_verifier.verify(
                attestation, sig_header, self.signature_verifier
            )
            if not valid:
                await self.blocking_manager.record_invalid_signature(
                    client_ip, tenant_id, attestation.device_id
                )
                return JSONResponse(
                    status_code=401,
                    content={"error": "device_attestation_failed"},
                )

        # 3. Verificar Signed URL si aplica
        if path.startswith("/_/"):
            resolved = self.url_manager.verify_and_resolve(path)
            if not resolved:
                return JSONResponse(
                    status_code=404,
                    content={"error": "endpoint_not_found"},
                )
            request.scope["path"] = resolved

        response = await call_next(request)
        return response
"""

# Exportar
__all__ = [
    "DeviceAttestation",
    "DeviceAttestationVerifier",
    "SignedEndpoint",
    "SignedURLManager",
    "BlockingManager",
    "FASTAPI_MIDDLEWARE_CODE",
]
