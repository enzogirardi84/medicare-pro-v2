"""Cifrado a nivel de columna con AES-256-GCM por tenant.
Los campos PHI se cifran antes de INSERT/UPDATE y se descifran
transparentemente en SELECT. Claves aisladas por tenant_id.
"""
from __future__ import annotations

import base64
import os
from dataclasses import dataclass
from typing import Any, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. GESTOR DE CLAVES POR TENANT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TenantCryptoKey:
    """Clave de cifrado para un tenant especifico."""
    tenant_id: str
    master_key: bytes  # 32 bytes AES-256
    salt: bytes = b"MediCare-ColumnEnc-v1"

    @classmethod
    def derivar(cls, tenant_id: str, master_secret: Optional[str] = None) -> TenantCryptoKey:
        """Deriva una clave AES-256 unica por tenant usando PBKDF2.

        Args:
            tenant_id: Slug del tenant (ej. "avalian").
            master_secret: Secreto maestro (default: variable de entorno).

        Returns:
            TenantCryptoKey con clave de 32 bytes.
        """
        secret = master_secret or os.environ.get("COLUMN_ENCRYPTION_KEY", "")
        if not secret:
            raise ValueError("COLUMN_ENCRYPTION_KEY no configurada")

        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=tenant_id.encode("utf-8"),
            iterations=600000,
        )
        key = kdf.derive(secret.encode("utf-8"))
        return cls(tenant_id=tenant_id, master_key=key)


# ═══════════════════════════════════════════════════════════════════
# 2. CIFRADO DE COLUMNAS
# ═══════════════════════════════════════════════════════════════════

class ColumnEncryptor:
    """Cifra/descifra campos PHI con AES-256-GCM.

    Los datos cifrados se almacenan como JSON base64 con nonce incluido.
    Cada tenant usa su propia clave derivada.
    """

    @staticmethod
    def encrypt(tenant_id: str, plaintext: str) -> str:
        """Cifra un campo PHI.

        Args:
            tenant_id: Slug del tenant.
            plaintext: Texto a cifrar.

        Returns:
            String base64 con nonce + ciphertext.
        """
        if not plaintext:
            return ""

        key = TenantCryptoKey.derivar(tenant_id)
        aesgcm = AESGCM(key.master_key)
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("ascii")

    @staticmethod
    def decrypt(tenant_id: str, ciphertext_b64: str) -> str:
        """Descifra un campo PHI.

        Args:
            tenant_id: Slug del tenant.
            ciphertext_b64: String base64 con nonce + ciphertext.

        Returns:
            Texto plano original.
        """
        if not ciphertext_b64:
            return ""

        try:
            key = TenantCryptoKey.derivar(tenant_id)
            data = base64.b64decode(ciphertext_b64)
            nonce, ciphertext = data[:12], data[12:]
            aesgcm = AESGCM(key.master_key)
            return aesgcm.decrypt(nonce, ciphertext, None).decode("utf-8")
        except Exception as exc:
            log_event("column_encrypt", f"decrypt_error:{type(exc).__name__}")
            return "[cifrado]"


# ═══════════════════════════════════════════════════════════════════
# 3. CAMPOS PHI POR TABLA
# ═══════════════════════════════════════════════════════════════════

PHI_FIELDS_CONFIG = {
    "pacientes": ["nombre", "dni", "email", "telefono", "direccion", "obra_social"],
    "evoluciones": ["nota", "diagnostico", "medicacion"],
    "usuarios": ["nombre", "email", "telefono"],
    "administracion_med": ["medicamento", "dosis", "observaciones"],
}


def encrypt_record(tenant_id: str, table: str, record: dict[str, Any]) -> dict[str, Any]:
    """Cifra campos PHI de un registro antes de INSERT/UPDATE.

    Args:
        tenant_id: Slug del tenant.
        table: Nombre de la tabla.
        record: Dict con datos del registro.

    Returns:
        Registro con campos PHI cifrados.
    """
    fields = PHI_FIELDS_CONFIG.get(table, [])
    encrypted = dict(record)
    for field in fields:
        if field in encrypted and encrypted[field]:
            encrypted[field] = ColumnEncryptor.encrypt(tenant_id, str(encrypted[field]))
            encrypted[f"{field}_enc"] = True
    return encrypted


def decrypt_record(tenant_id: str, table: str, record: dict[str, Any]) -> dict[str, Any]:
    """Descifra campos PHI de un registro post-SELECT.

    Args:
        tenant_id: Slug del tenant.
        table: Nombre de la tabla.
        record: Dict con datos cifrados.

    Returns:
        Registro con campos PHI descifrados.
    """
    fields = PHI_FIELDS_CONFIG.get(table, [])
    decrypted = dict(record)
    for field in fields:
        if field in decrypted and isinstance(decrypted[field], str):
            # Si parece cifrado (base64 + longitud adecuada)
            val = decrypted[field]
            if val and not val.startswith("[cifrado]") and len(val) > 40:
                decrypted[field] = ColumnEncryptor.decrypt(tenant_id, val)
    return decrypted
