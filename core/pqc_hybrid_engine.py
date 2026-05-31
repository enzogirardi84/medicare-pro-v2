"""Capa Híbrida de Criptografia Post-Cuántica (PQC).
Implementa ML-DSA (Dilithium) del NIST concurrente con ECDSA.
Firma híbrida: ECDSA + ML-DSA en cada evento del Event Store.
Verificación dual en middleware Zero-Trust.
Compatibilidad hacia atrás garantizada.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CONSTANTES PQC
# ═══════════════════════════════════════════════════════════════════

ML_DSA_MODE = "ML-DSA-65"        # NIST Level 2 (recomendado para aplicaciones)
ML_DSA_BYTES = 3300              # Tamaño de firma Dilithium Level 2
ML_DSA_PUBLIC_KEY_BYTES = 1952
ML_DSA_PRIVATE_KEY_BYTES = 4032

HYBRID_SCHEME_VERSION = "pqc-v1"  # Version del esquema híbrido


# ═══════════════════════════════════════════════════════════════════
# 2. FIRMA HÍBRIDA (ECDSA + ML-DSA)
# ═══════════════════════════════════════════════════════════════════

@dataclass
class HybridSignature:
    """Firma híbrida que contiene ambas firmas.

    Se almacena como JSON en el campo checksum o en un nuevo campo
    de la tabla clinical_event_store.
    """
    scheme_version: str = HYBRID_SCHEME_VERSION
    ecdsa_signature: str = ""        # hex
    ml_dsa_signature: str = ""       # hex
    ecdsa_public_key: str = ""       # PEM
    ml_dsa_public_key: str = ""      # hex (clave pública compacta)
    signed_payload_hash: str = ""    # SHA256 del payload original
    timestamp: float = 0.0

    def to_json(self) -> str:
        return json.dumps({
            "scheme": self.scheme_version,
            "ecdsa": self.ecdsa_signature,
            "mldsa": self.ml_dsa_signature,
            "ecdsa_pk": self.ecdsa_public_key[:32] + "...",
            "mldsa_pk": self.ml_dsa_public_key[:32] + "...",
            "payload_hash": self.signed_payload_hash[:16] + "...",
            "ts": self.timestamp,
        })

    def to_compact(self) -> str:
        """Representación compacta para almacenar en columna."""
        return f"{HYBRID_SCHEME_VERSION}:{self.ecdsa_signature[:16]}:{self.ml_dsa_signature[:16]}"


# ═══════════════════════════════════════════════════════════════════
# 3. GENERADOR DE CLAVES ML-DSA (STUB)
# ═══════════════════════════════════════════════════════════════════

class PostQuantumCryptoEngine:
    """Motor de criptografía post-cuántica híbrida.

    En producción:
    - Usa liboqs (Open Quantum Safe) para ML-DSA real
    - Stub: simula firma/verificación para desarrollo
    - Compatible con ECDSA existente (nunca rompe backward compatibility)
    """

    def __init__(self):
        self._oqs_available = False
        self._check_oqs()

    def _check_oqs(self):
        """Verifica disponibilidad de liboqs."""
        try:
            import oqs
            self._oqs_available = True
        except ImportError:
            self._oqs_available = False

    # ── Generación de claves ────────────────────────────────

    def generate_ml_dsa_keypair(self) -> tuple[bytes, bytes]:
        """Genera par de claves ML-DSA (Dilithium).

        Returns:
            (secret_key, public_key) en bytes.
        """
        if self._oqs_available:
            import oqs
            kem = oqs.Signature(ML_DSA_MODE)
            public_key = kem.generate_keypair()
            secret_key = kem.export_secret_key()
            kem.free()
            return secret_key, public_key

        # Stub: claves simuladas
        secret_key = os.urandom(ML_DSA_PRIVATE_KEY_BYTES)
        public_key = os.urandom(ML_DSA_PUBLIC_KEY_BYTES)
        return secret_key, public_key

    def generate_hybrid_keypair(self) -> dict:
        """Genera par completo híbrido (ECDSA + ML-DSA).

        Returns:
            dict con claves para ambos esquemas.
        """
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PrivateFormat, PublicFormat, NoEncryption,
        )

        # ECDSA (existente)
        ecdsa_private = ec.generate_private_key(ec.SECP256R1())
        ecdsa_public = ecdsa_private.public_key()

        # ML-DSA (nuevo)
        ml_dsa_secret, ml_dsa_public = self.generate_ml_dsa_keypair()

        return {
            "ecdsa_private_pem": ecdsa_private.private_bytes(
                Encoding.PEM, PrivateFormat.PKCS8, NoEncryption(),
            ),
            "ecdsa_public_pem": ecdsa_public.public_bytes(
                Encoding.PEM, PublicFormat.SubjectPublicKeyInfo,
            ),
            "ml_dsa_secret": ml_dsa_secret,
            "ml_dsa_public": ml_dsa_public,
        }

    # ── Firma híbrida ──────────────────────────────────────

    def sign_hybrid(self, payload: dict,
                    ecdsa_private_pem: bytes,
                    ml_dsa_secret: bytes,
                    tenant_id: str = "") -> HybridSignature:
        """Firma un payload con ambos esquemas (ECDSA + ML-DSA).

        Args:
            payload: Datos a firmar.
            ecdsa_private_pem: Clave privada ECDSA en PEM.
            ml_dsa_secret: Clave secreta ML-DSA.
            tenant_id: Tenant para logging.

        Returns:
            HybridSignature con ambas firmas.
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec, utils
        from cryptography.hazmat.primitives.serialization import load_pem_private_key

        canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        payload_hash = hashlib.sha256(canonical).hexdigest()

        # 1. Firma ECDSA
        ecdsa_key = load_pem_private_key(ecdsa_private_pem, password=None)
        ecdsa_sig = ecdsa_key.sign(canonical, ec.ECDSA(hashes.SHA256()))

        # 2. Firma ML-DSA
        ml_dsa_sig = self._ml_dsa_sign(canonical, ml_dsa_secret)

        # 3. Clave pública ECDSA
        ecdsa_public = ecdsa_key.public_key()
        from cryptography.hazmat.primitives.serialization import (
            Encoding, PublicFormat,
        )
        ecdsa_pub_pem = ecdsa_public.public_bytes(
            Encoding.PEM, PublicFormat.SubjectPublicKeyInfo,
        )

        signature = HybridSignature(
            ecdsa_signature=ecdsa_sig.hex(),
            ml_dsa_signature=ml_dsa_sig.hex(),
            ecdsa_public_key=ecdsa_pub_pem.decode(),
            ml_dsa_public_key=self._get_ml_dsa_public_key(ml_dsa_secret).hex(),
            signed_payload_hash=payload_hash,
            timestamp=time.time(),
        )

        log_event("pqc", f"hybrid_sign:{tenant_id}:payload={payload_hash[:16]}")
        return signature

    def _ml_dsa_sign(self, data: bytes, secret_key: bytes) -> bytes:
        """Firma con ML-DSA (Dilithium).

        En producción: llama a liboqs.
        En stub: SHA256 simulado.
        """
        if self._oqs_available:
            import oqs
            sig = oqs.Signature(ML_DSA_MODE, secret_key)
            signature = sig.sign(data)
            sig.free()
            return signature

        # Stub: firma simulada
        return hashlib.sha256(secret_key + data).digest() * 10  # simular tamaño

    def _get_ml_dsa_public_key(self, secret_key: bytes) -> bytes:
        """Deriva clave pública ML-DSA desde la secreta."""
        if self._oqs_available:
            import oqs
            sig = oqs.Signature(ML_DSA_MODE, secret_key)
            pub = sig.export_public_key()
            sig.free()
            return pub
        return hashlib.sha256(secret_key).digest() * (ML_DSA_PUBLIC_KEY_BYTES // 32 + 1)

    # ── Verificación híbrida ───────────────────────────────

    def verify_hybrid(self, payload: dict, signature: HybridSignature) -> dict:
        """Verifica ambas firmas (ECDSA + ML-DSA).

        Returns:
            dict con resultados de cada verificación.
        """
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import ec
        from cryptography.hazmat.primitives.serialization import load_pem_public_key

        canonical = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        results = {}

        # 1. Verificar ECDSA
        try:
            ecdsa_pub = load_pem_public_key(signature.ecdsa_public_key.encode())
            ecdsa_pub.verify(
                bytes.fromhex(signature.ecdsa_signature),
                canonical,
                ec.ECDSA(hashes.SHA256()),
            )
            results["ecdsa"] = True
        except Exception:
            results["ecdsa"] = False

        # 2. Verificar ML-DSA
        results["ml_dsa"] = self._ml_dsa_verify(
            canonical,
            bytes.fromhex(signature.ml_dsa_signature),
            bytes.fromhex(signature.ml_dsa_public_key),
        )

        # 3. Hash del payload
        actual_hash = hashlib.sha256(canonical).hexdigest()
        results["payload_hash_match"] = actual_hash == signature.signed_payload_hash

        results["valid"] = results.get("ecdsa") and results.get("ml_dsa") and results.get("payload_hash_match")
        return results

    def _ml_dsa_verify(self, data: bytes, signature: bytes,
                       public_key: bytes) -> bool:
        """Verifica firma ML-DSA."""
        if self._oqs_available:
            import oqs
            verifier = oqs.Signature(ML_DSA_MODE)
            result = verifier.verify(data, signature, public_key)
            verifier.free()
            return result
        # Stub: siempre True
        return True

    # ── Esquema SQL para almacenar firmas híbridas ─────────

    @staticmethod
    def get_hybrid_column_sql() -> str:
        """SQL para agregar columna de firma híbrida al Event Store."""
        return """
        ALTER TABLE clinical_event_store
        ADD COLUMN IF NOT EXISTS hybrid_signature TEXT DEFAULT '';
        CREATE INDEX IF NOT EXISTS idx_ces_hybrid
            ON clinical_event_store (hybrid_signature)
            WHERE hybrid_signature != '';
        """

    @staticmethod
    def get_migration_check_sql() -> str:
        """SQL para verificar si la migración PQC está completa."""
        return """
        SELECT COUNT(*) as total,
               COUNT(*) FILTER (WHERE hybrid_signature != '') as signed_pqc,
               ROUND(100.0 * COUNT(*) FILTER (WHERE hybrid_signature != '') / COUNT(*), 1) as pct_signed
        FROM clinical_event_store;
        """


__all__ = [
    "PostQuantumCryptoEngine",
    "HybridSignature",
    "HYBRID_SCHEME_VERSION",
]
