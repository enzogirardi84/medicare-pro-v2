"""Almacenamiento externo S3/Cloudflare R2 para estudios medicos.
URLs firmadas (presigned) con expiracion de 15 minutos.
Reemplaza el guardado local en disco.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACION
# ═══════════════════════════════════════════════════════════════════

@dataclass
class StorageConfig:
    """Configuracion del almacenamiento externo."""
    endpoint_url: str = ""
    region: str = "us-east-1"
    bucket_name: str = ""
    access_key: str = ""
    secret_key: str = ""
    presigned_url_expiry: int = 900  # 15 minutos
    cdn_domain: str = ""  # Ej: https://cdn.medicare-pro.app

    @classmethod
    def from_env(cls, tenant_id: str = "default") -> StorageConfig:
        prefix = tenant_id.upper().replace("-", "_")

        def env(key: str, default: str = "") -> str:
            return os.environ.get(f"{prefix}_{key}", os.environ.get(key, default))

        return cls(
            endpoint_url=env("S3_ENDPOINT", "https://s3.us-east-1.amazonaws.com"),
            region=env("S3_REGION", "us-east-1"),
            bucket_name=env("S3_BUCKET", f"medicare-estudios-{tenant_id}"),
            access_key=env("S3_ACCESS_KEY", ""),
            secret_key=env("S3_SECRET_KEY", ""),
            presigned_url_expiry=int(env("S3_PRESIGNED_EXPIRY", "900")),
            cdn_domain=env("CDN_DOMAIN", ""),
        )


# ═══════════════════════════════════════════════════════════════════
# 2. CLIENTE DE ALMACENAMIENTO
# ═══════════════════════════════════════════════════════════════════

class CloudStorage:
    """Cliente de almacenamiento de objetos S3/R2 con URLs firmadas.

    Soporta AWS S3 y Cloudflare R2 (compatibles con S3 API).
    Los archivos se suben asincronicamente y se acceden via
    presigned URLs con expiracion de 15 minutos.

    Uso:
        storage = CloudStorage(tenant_id="avalian")
        url = storage.subir_archivo(buffer, "radiografia.pdf", "application/pdf")
        url_acceso = storage.generar_url_descarga("uuid_archivo.pdf")
    """

    def __init__(self, tenant_id: str = "default"):
        self._config = StorageConfig.from_env(tenant_id)
        self._client = None
        self._initialized = False

    def _init_client(self) -> Any:
        """Inicializa el cliente S3 (lazy)."""
        if self._initialized and self._client:
            return self._client

        try:
            import boto3
            from botocore.config import Config

            session = boto3.Session(
                aws_access_key_id=self._config.access_key,
                aws_secret_access_key=self._config.secret_key,
                region_name=self._config.region,
            )

            config = Config(
                retries={"max_attempts": 3, "mode": "adaptive"},
                connect_timeout=10,
                read_timeout=30,
                max_pool_connections=50,
            )

            self._client = session.client(
                "s3",
                endpoint_url=self._config.endpoint_url or None,
                config=config,
            )
            self._initialized = True
            log_event("cloud_storage", f"cliente_inicializado:{self._config.bucket_name}")
            return self._client

        except ImportError:
            log_event("cloud_storage", "boto3 no instalado. Usando fallback local.")
            return None
        except Exception as exc:
            log_event("cloud_storage", f"init_error:{type(exc).__name__}:{exc}")
            return None

    # ─── Subida de archivos ───────────────────────────────────

    def subir_archivo(
        self,
        buffer: bytes,
        nombre_original: str,
        content_type: str = "application/octet-stream",
        metadata: dict[str, str] | None = None,
    ) -> Optional[dict[str, Any]]:
        """Sube un archivo al bucket S3/R2.

        Args:
            buffer: Contenido del archivo en bytes (ya sanitizado).
            nombre_original: Nombre original del archivo.
            content_type: MIME type del archivo.
            metadata: Metadatos adicionales (tenant, paciente, etc).

        Returns:
            Dict con 'key', 'etag', 'url' si ok, None si fallo.
        """
        client = self._init_client()
        if client is None:
            return self._fallback_local(buffer, nombre_original, content_type)

        # Generar key unico con hash
        sha256 = hashlib.sha256(buffer).hexdigest()
        ext = os.path.splitext(nombre_original)[1].lower()
        key = f"estudios/{sha256[:16]}_{int(time.time())}{ext}"

        metadata = metadata or {}
        metadata["sha256"] = sha256

        try:
            client.put_object(
                Bucket=self._config.bucket_name,
                Key=key,
                Body=buffer,
                ContentType=content_type,
                Metadata=metadata,
                ServerSideEncryption="AES256",
            )
            log_event("cloud_storage", f"subida_ok:{key}:{len(buffer)}b")
            return {
                "key": key,
                "etag": sha256[:16],
                "url": self.generar_url_descarga(key),
                "sha256": sha256,
            }
        except Exception as exc:
            log_event("cloud_storage", f"subida_error:{type(exc).__name__}:{exc}")
            return None

    # ─── URLs firmadas (Presigned URLs) ───────────────────────

    def generar_url_descarga(self, key: str, expiry: int | None = None) -> str:
        """Genera una URL firmada temporal para descargar un archivo.

        La URL expira en 15 minutos (configurable).
        Si hay CDN configurado, usa el dominio CDN en lugar del bucket S3.
        """
        client = self._init_client()
        if client is None:
            return ""

        expiry = expiry or self._config.presigned_url_expiry

        try:
            url = client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": self._config.bucket_name,
                    "Key": key,
                    "ResponseContentDisposition": "inline",
                },
                ExpiresIn=expiry,
            )

            # Si hay CDN, reemplazar el endpoint por el CDN
            if self._config.cdn_domain:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                url = f"{self._config.cdn_domain.rstrip('/')}/{key}?{parsed.query}"

            return url
        except Exception as exc:
            log_event("cloud_storage", f"presigned_url_error:{type(exc).__name__}")
            return ""

    # ─── Eliminacion ──────────────────────────────────────────

    def eliminar_archivo(self, key: str) -> bool:
        """Elimina un archivo del bucket."""
        client = self._init_client()
        if client is None:
            return False
        try:
            client.delete_object(Bucket=self._config.bucket_name, Key=key)
            log_event("cloud_storage", f"eliminado:{key}")
            return True
        except Exception as exc:
            log_event("cloud_storage", f"eliminar_error:{type(exc).__name__}")
            return False

    # ─── Fallback local ───────────────────────────────────────

    def _fallback_local(
        self, buffer: bytes, nombre_original: str, content_type: str
    ) -> Optional[dict[str, Any]]:
        """Fallback a almacenamiento local si no hay S3."""
        sha256 = hashlib.sha256(buffer).hexdigest()
        ext = os.path.splitext(nombre_original)[1].lower()
        nombre = f"{sha256[:16]}_{int(time.time())}{ext}"

        local_dir = Path(f"storage/estudios/{self._config.bucket_name}")
        local_dir.mkdir(parents=True, exist_ok=True)
        ruta = local_dir / nombre
        ruta.write_bytes(buffer)

        log_event("cloud_storage", f"fallback_local:{ruta}")
        return {
            "key": nombre,
            "etag": sha256[:16],
            "ruta_local": str(ruta),
            "sha256": sha256,
        }
