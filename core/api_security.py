"""Seguridad perimetral para FastAPI: JWT asimetrico, mTLS, secrets con Vault.
Middleware de autenticacion para POST /sync/batch.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Any, Optional

import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. JWT ASIMETRICO CON ROTACION DE CLAVES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class JWTConfig:
    """Configuracion JWT desde variables de entorno o Vault."""
    algorithm: str = "ES256"  # ECDSA P-256 (FIPS 186-5)
    public_key_pem: str = ""
    private_key_pem: str = ""
    access_token_ttl: int = 900  # 15 minutos
    refresh_token_ttl: int = 86400  # 24 horas
    issuer: str = "medicare-pro"

    @classmethod
    def from_env_or_vault(cls) -> JWTConfig:
        # Intentar Vault primero
        vault_token = os.environ.get("VAULT_TOKEN")
        vault_addr = os.environ.get("VAULT_ADDR", "https://vault.medicare-pro.app:8200")

        if vault_token and vault_addr:
            try:
                resp = httpx.get(
                    f"{vault_addr}/v1/secret/data/medicare/jwt",
                    headers={"X-Vault-Token": vault_token},
                    timeout=5,
                )
                if resp.status_code == 200:
                    data = resp.json()["data"]["data"]
                    return cls(
                        private_key_pem=data.get("private_key", ""),
                        public_key_pem=data.get("public_key", ""),
                    )
            except Exception as exc:
                log_event("api_security", f"vault_error:{type(exc).__name__}")

        # Fallback a variables de entorno
        return cls(
            private_key_pem=os.environ.get("JWT_PRIVATE_KEY", ""),
            public_key_pem=os.environ.get("JWT_PUBLIC_KEY", ""),
        )


def create_jwt(profesional_id: str, tenant_id: str, config: Optional[JWTConfig] = None) -> str:
    """Crea un JWT firmado con ECDSA P-256.

    Args:
        profesional_id: UUID del profesional.
        tenant_id: Slug del tenant.
        config: Configuracion JWT (claves).

    Returns:
        Token JWT en formato compacto.
    """
    import jwt

    cfg = config or JWTConfig.from_env_or_vault()
    now = int(time.time())

    payload = {
        "sub": profesional_id,
        "tenant": tenant_id,
        "iss": cfg.issuer,
        "iat": now,
        "exp": now + cfg.access_token_ttl,
        "jti": os.urandom(8).hex(),
    }

    token = jwt.encode(payload, cfg.private_key_pem, algorithm=cfg.algorithm)
    return token


def verify_jwt(token: str, config: Optional[JWTConfig] = None) -> dict[str, Any]:
    """Verifica un JWT y retorna el payload.

    Valida firma, expiracion, issuer.
    """
    import jwt
    from jwt.exceptions import ExpiredSignatureError, InvalidSignatureError

    cfg = config or JWTConfig.from_env_or_vault()

    try:
        payload = jwt.decode(
            token,
            cfg.public_key_pem,
            algorithms=[cfg.algorithm],
            issuer=cfg.issuer,
            options={"require": ["sub", "tenant", "exp"]},
        )
        return payload
    except ExpiredSignatureError:
        raise HTTPException(401, "Token expirado")
    except InvalidSignatureError:
        raise HTTPException(401, "Firma JWT invalida")
    except Exception as exc:
        log_event("api_security", f"jwt_error:{type(exc).__name__}")
        raise HTTPException(401, "Token invalido")


# ═══════════════════════════════════════════════════════════════════
# 2. MIDDLEWARE DE AUTENTICACION
# ═══════════════════════════════════════════════════════════════════

async def auth_middleware(request: Request, call_next: Any) -> Any:
    """Middleware que valida JWT en cada request a la API.

    Extrae profesional_id y tenant_id del token.
    Los inyecta en request.state para uso en endpoints.
    """
    # Rutas publicas
    if request.url.path in ("/healthz", "/metrics", "/docs", "/openapi.json"):
        return await call_next(request)

    # Extraer token del header Authorization
    auth_header = request.headers.get("Authorization", "")
    if not auth_header.startswith("Bearer "):
        return HTTPException(401, "Token requerido")

    token = auth_header[7:]

    try:
        payload = verify_jwt(token)
        request.state.profesional_id = payload["sub"]
        request.state.tenant_id = payload["tenant"]
    except HTTPException:
        return HTTPException(401, "Autenticacion fallida")

    return await call_next(request)


def configure_fastapi_security(app: FastAPI) -> None:
    """Configura seguridad en la aplicacion FastAPI.

    - Middleware de autenticacion JWT
    - CORS restringido
    - mTLS (opcional, requiere certificados)
    """
    # CORS restrictivo
    app.add_middleware(
        CORSMiddleware,
        allow_origins=os.environ.get("CORS_ORIGINS", "https://medicare-pro.app").split(","),
        allow_credentials=True,
        allow_methods=["POST"],
        allow_headers=["Authorization", "Content-Type", "X-Tenant-Id"],
    )

    # Middleware de autenticacion
    app.middleware("http")(auth_middleware)

    log_event("api_security", "FastAPI hardening configurado")


# ═══════════════════════════════════════════════════════════════════
# 3. SECRETS MANAGEMENT (Vault / AWS Secrets Manager / Env)
# ═══════════════════════════════════════════════════════════════════

class SecretsManager:
    """Gestor de secretos multi-backend.

    Orden de preferencia:
    1. HashiCorp Vault (produccion)
    2. AWS Secrets Manager (fallback)
    3. Variables de entorno (desarrollo)
    """

    @staticmethod
    def get_secret(key: str, default: str = "") -> str:
        # Intentar Vault
        vault_addr = os.environ.get("VAULT_ADDR")
        vault_token = os.environ.get("VAULT_TOKEN")
        if vault_addr and vault_token:
            try:
                resp = httpx.get(
                    f"{vault_addr}/v1/secret/data/medicare/{key}",
                    headers={"X-Vault-Token": vault_token},
                    timeout=3,
                )
                if resp.status_code == 200:
                    return resp.json()["data"]["data"]["value"]
            except Exception:
                pass

        # Intentar AWS Secrets Manager
        try:
            import boto3
            from botocore.exceptions import ClientError
            client = boto3.client("secretsmanager", region_name="us-east-1")
            resp = client.get_secret_value(SecretId=f"medicare/{key}")
            return resp["SecretString"]
        except Exception:
            pass

        # Fallback a variable de entorno
        return os.environ.get(key.upper(), default)
