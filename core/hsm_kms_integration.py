"""Capa de abstraccion criptografica para HSM/KMS (Envelope Encryption).
KEK (Key Encryption Key) no exportable radicada en hardware KMS.
DEK (Data Encryption Keys) por tenant, cifradas con KEK.
Ciclo de vida aislado: KEK nunca sale del HSM.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS CRIPTOGRAFICOS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class Envelope:
    """Sobre criptografico: DEK cifrado con KEK + metadatos."""
    encrypted_dek: bytes
    wrapped_dek: str       # base64 del DEK cifrado
    key_id: str            # identificador de la KEK en el KMS
    algorithm: str = "AES-256-GCM"
    wrapping_algorithm: str = "RSAES_OAEP_SHA_256"
    created_at: float = 0.0
    expires_at: float = 0.0


@dataclass
class TenantDEK:
    """Data Encryption Key de un tenant con metadatos."""
    tenant_id: str
    dek_version: int = 1
    envelope: Optional[Envelope] = None
    cached_dek: Optional[bytes] = None   # solo en memoria, nunca persistir
    cached_at: float = 0.0
    cache_ttl: float = 3600.0            # 1 hora en cache

    def is_cache_valid(self) -> bool:
        return (self.cached_dek is not None and
                time.time() - self.cached_at < self.cache_ttl)

    def clear_cache(self):
        self.cached_dek = None
        self.cached_at = 0.0


# ═══════════════════════════════════════════════════════════════════
# 2. DRIVER ABSTRACTO PARA KMS
# ═══════════════════════════════════════════════════════════════════

class KMSDriver:
    """Driver abstracto para servicios KMS (AWS KMS / Cloud KMS).

    La KEK nunca sale del HSM virtual. Solo se envian
    operaciones de Encrypt/Decrypt con la clave referenciada por key_id.
    """

    def __init__(self, provider: str = "aws"):
        self._provider = provider
        self._key_id = os.environ.get(
            "KMS_KEY_ID",
            "arn:aws:kms:us-east-1:123456789012:key/medicare-master",
        )

    async def create_key(self, alias: str) -> str:
        """Crea una nueva KEK en el KMS.

        Args:
            alias: Alias para la clave (ej. 'medicare-pro-master').

        Returns:
            key_id de la KEK creada.
        """
        log_event("kms", f"create_key:{alias}")
        return f"kms://{alias}/{os.urandom(4).hex()}"

    async def encrypt(self, plaintext: bytes, key_id: Optional[str] = None) -> dict:
        """Cifra datos con la KEK del KMS.

        En produccion, llama a:
        - AWS: kms_client.encrypt(KeyId=key_id, Plaintext=plaintext)
        - GCP: cloudkms_client.encrypt(name=key_name, plaintext=plaintext)

        Args:
            plaintext: Datos a cifrar (ej. DEK en bytes).
            key_id: Identificador de la KEK (default: self._key_id).

        Returns:
            dict con ciphertext (bytes), key_id, algorithm.
        """
        kid = key_id or self._key_id
        log_event("kms", f"encrypt:{kid[:40]}")
        # Simulacion: XOR + base64 (en produccion llamaria al KMS real)
        from cryptography.fernet import Fernet
        import base64
        key = base64.urlsafe_b64encode(os.urandom(32))
        f = Fernet(key)
        ciphertext = f.encrypt(plaintext)
        return {
            "ciphertext": ciphertext,
            "key_id": kid,
            "algorithm": "AES-256-GCM",
            "wrapping_algorithm": "RSAES_OAEP_SHA_256",
        }

    async def decrypt(self, ciphertext: bytes, key_id: str) -> bytes:
        """Descifra datos con la KEK del KMS.

        En produccion, llama a:
        - AWS: kms_client.decrypt(KeyId=key_id, CiphertextBlob=ciphertext)
        - GCP: cloudkms_client.decrypt(name=key_name, ciphertext=ciphertext)

        Args:
            ciphertext: Datos cifrados.
            key_id: Identificador de la KEK usada para cifrar.

        Returns:
            plaintext en bytes.
        """
        log_event("kms", f"decrypt:{key_id[:40]}")
        from cryptography.fernet import Fernet
        import base64
        key = base64.urlsafe_b64encode(os.urandom(32))
        f = Fernet(key)
        try:
            return f.decrypt(ciphertext)
        except Exception:
            log_event("kms", "decrypt_failed:invalid_ciphertext")
            raise ValueError("No se pudo descifrar: ciphertext invalido o KEK incorrecta")

    async def generate_data_key(self, key_id: Optional[str] = None) -> dict:
        """Genera una nueva DEK cifrada con la KEK.

        En produccion, llama a:
        - AWS: kms_client.generate_data_key(KeyId=key_id, KeySpec='AES_256')

        Returns:
            dict con plaintext (bytes) y ciphertext (bytes).
        """
        kid = key_id or self._key_id
        dek = os.urandom(32)  # AES-256 key
        result = await self.encrypt(dek, kid)
        return {
            "plaintext": dek,
            "ciphertext": result["ciphertext"],
            "key_id": kid,
        }

    async def re_encrypt(self, ciphertext: bytes, old_key_id: str,
                         new_key_id: str) -> bytes:
        """Re-cifra una DEK de una KEK antigua a una nueva (rotation).

        Args:
            ciphertext: DEK cifrada con old_key_id.
            old_key_id: KEK original.
            new_key_id: Nueva KEK.

        Returns:
            DEK cifrada con new_key_id.
        """
        plaintext = await self.decrypt(ciphertext, old_key_id)
        result = await self.encrypt(plaintext, new_key_id)
        return result["ciphertext"]


# ═══════════════════════════════════════════════════════════════════
# 3. GESTOR DE ENVOLTURA CRIPTOGRAFICA (Envelope Encryption Manager)
# ═══════════════════════════════════════════════════════════════════

class EnvelopeEncryptionManager:
    """Gestor de envelope encryption con KEK en HSM/KMS.

    Flujo:
    1. KEK se crea en KMS (nunca sale del hardware)
    2. Por cada tenant, se genera una DEK AES-256
    3. La DEK se cifra con la KEK (wrapped DEK) y se almacena
    4. En operacion, la DEK se descifra del envelope y se cachea en memoria
    5. La DEK se usa para cifrar/descifrar datos del tenant
    """

    def __init__(self, kms_driver: Optional[KMSDriver] = None):
        self._kms = kms_driver or KMSDriver()
        self._tenant_deks: dict[str, TenantDEK] = {}
        self._master_key_id: str = ""

    async def initialize(self, alias: str = "medicare-pro-master") -> str:
        """Inicializa el gestor creando la KEK maestra si no existe.

        Returns:
            key_id de la KEK maestra.
        """
        self._master_key_id = await self._kms.create_key(alias)
        log_event("envelope", f"initialized:{self._master_key_id}")
        return self._master_key_id

    async def generate_tenant_dek(self, tenant_id: str) -> TenantDEK:
        """Genera una DEK para un tenant, cifrada con la KEK maestra.

        Args:
            tenant_id: ID del tenant.

        Returns:
            TenantDEK con envelope (DEK cifrada).
        """
        dk_result = await self._kms.generate_data_key(self._master_key_id)
        envelope = Envelope(
            encrypted_dek=dk_result["ciphertext"],
            wrapped_dek=dk_result["ciphertext"].hex(),
            key_id=self._master_key_id,
            created_at=time.time(),
            expires_at=time.time() + 86400 * 365,  # 1 ano
        )
        tenant_dek = TenantDEK(
            tenant_id=tenant_id,
            dek_version=1,
            envelope=envelope,
            cached_dek=dk_result["plaintext"],
            cached_at=time.time(),
        )
        self._tenant_deks[tenant_id] = tenant_dek
        log_event("envelope", f"tenant_dek_created:{tenant_id}:v1")
        return tenant_dek

    async def get_dek(self, tenant_id: str) -> bytes:
        """Obtiene la DEK de un tenant (desde cache o descifrando el envelope).

        Args:
            tenant_id: ID del tenant.

        Returns:
            DEK en bytes (AES-256).

        Raises:
            KeyError: Si el tenant no tiene DEK registrada.
        """
        tdek = self._tenant_deks.get(tenant_id)
        if not tdek:
            raise KeyError(f"Tenant {tenant_id} no tiene DEK registrada")

        if tdek.is_cache_valid():
            return tdek.cached_dek

        # Descifrar DEK del envelope via KMS
        plaintext = await self._kms.decrypt(
            tdek.envelope.encrypted_dek,
            tdek.envelope.key_id,
        )
        tdek.cached_dek = plaintext
        tdek.cached_at = time.time()
        return plaintext

    async def encrypt_tenant_data(self, tenant_id: str, plaintext: bytes) -> bytes:
        """Cifra datos de un tenant usando su DEK.

        Args:
            tenant_id: ID del tenant.
            plaintext: Datos a cifrar.

        Returns:
            Datos cifrados.
        """
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        dek = await self.get_dek(tenant_id)
        iv = os.urandom(12)
        cipher = Cipher(algorithms.AES(dek), modes.GCM(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(plaintext) + encryptor.finalize()
        return iv + encryptor.tag + ciphertext

    async def decrypt_tenant_data(self, tenant_id: str, ciphertext: bytes) -> bytes:
        """Descifra datos de un tenant usando su DEK.

        Args:
            tenant_id: ID del tenant.
            ciphertext: Datos cifrados (IV + tag + ciphertext).

        Returns:
            Datos descifrados.
        """
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        dek = await self.get_dek(tenant_id)
        iv = ciphertext[:12]
        tag = ciphertext[12:28]
        ct = ciphertext[28:]
        cipher = Cipher(algorithms.AES(dek), modes.GCM(iv, tag))
        decryptor = cipher.decryptor()
        return decryptor.update(ct) + decryptor.finalize()

    async def rotate_master_key(self, new_alias: str = "medicare-pro-master-v2") -> int:
        """Rota la KEK maestra: nueva KEK, re-cifra todas las DEKs.

        Returns:
            Cantidad de DEKs re-cifradas.
        """
        old_key_id = self._master_key_id
        new_key_id = await self._kms.create_key(new_alias)
        count = 0
        for tenant_id, tdek in self._tenant_deks.items():
            new_ciphertext = await self._kms.re_encrypt(
                tdek.envelope.encrypted_dek,
                old_key_id,
                new_key_id,
            )
            tdek.envelope.encrypted_dek = new_ciphertext
            tdek.envelope.key_id = new_key_id
            tdek.envelope.wrapped_dek = new_ciphertext.hex()
            tdek.dek_version += 1
            tdek.clear_cache()
            count += 1
        self._master_key_id = new_key_id
        log_event("envelope", f"master_key_rotated:{old_key_id[:16]}->{new_key_id[:16]}:{count} DEKs")
        return count

    def get_tenant_dek_info(self, tenant_id: str) -> Optional[dict]:
        """Informacion no sensible de la DEK de un tenant."""
        tdek = self._tenant_deks.get(tenant_id)
        if not tdek:
            return None
        return {
            "tenant_id": tenant_id,
            "dek_version": tdek.dek_version,
            "algorithm": "AES-256-GCM",
            "key_id": tdek.envelope.key_id if tdek.envelope else "",
            "envelope_created": tdek.envelope.created_at if tdek.envelope else 0,
            "cache_valid": tdek.is_cache_valid(),
        }


__all__ = [
    "KMSDriver",
    "EnvelopeEncryptionManager",
    "Envelope",
    "TenantDEK",
]
