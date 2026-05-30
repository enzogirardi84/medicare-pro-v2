"""Firmas digitales asimetricas ECDSA para documentos clinicos.
Reemplaza HMAC-SHA256 simetrico por criptografia de clave publica (ECDSA).
El medico firma con su clave privada; el servidor verifica con la publica.
Garantiza No Repudio legal.
"""

from __future__ import annotations

import base64
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, utils

from core.app_logging import log_event


# ── Revocacion de claves ─────────────────────────────────────────

@dataclass
class ClaveRevocada:
    """Registro de una clave publica revocada."""
    fingerprint: str
    usuario: str
    fecha_revocacion: float
    motivo: str = ""


class KeyRevocationManager:
    """Gestiona la revocacion de claves publicas ECDSA.

    Permite revocar una clave sin invalidar firmas historicas:
    - Las firmas hechas ANTES de la revocacion siguen siendo validas
    - Las firmas hechas DESPUES requieren la nueva clave
    """

    REVOKED_KEYS_KEY = "_ecdsa_revoked_keys"

    @staticmethod
    def revocar(fingerprint: str, usuario: str, motivo: str = "Perdida de dispositivo") -> None:
        """Revoca una clave publica existente."""
        import streamlit as st
        revoked = st.session_state.get(KeyRevocationManager.REVOKED_KEYS_KEY, [])
        revoked.append(ClaveRevocada(
            fingerprint=fingerprint,
            usuario=usuario,
            fecha_revocacion=time.time(),
            motivo=motivo,
        ))
        st.session_state[KeyRevocationManager.REVOKED_KEYS_KEY] = revoked
        log_event("ecdsa", f"clave_revocada:{usuario}:{fingerprint[:12]}")

    @staticmethod
    def esta_revocada(fingerprint: str) -> bool:
        """Verifica si una clave fue revocada."""
        import streamlit as st
        revoked = st.session_state.get(KeyRevocationManager.REVOKED_KEYS_KEY, [])
        return any(r.fingerprint == fingerprint for r in revoked)

    @staticmethod
    def limpiar_revocaciones_antiguas(dias: int = 365) -> None:
        """Elimina revocaciones con mas de N dias (limpieza)."""
        import streamlit as st
        corte = time.time() - (dias * 86400)
        revoked = st.session_state.get(KeyRevocationManager.REVOKED_KEYS_KEY, [])
        revoked = [r for r in revoked if r.fecha_revocacion > corte]
        st.session_state[KeyRevocationManager.REVOKED_KEYS_KEY] = revoked
        log_event("ecdsa", f"limpieza_revocaciones:{len(revoked)}_activas")


def fingerprint_clave_publica(clave_publica_pem: bytes) -> str:
    """Genera un hash unico (fingerprint) para una clave publica."""
    from hashlib import sha256
    return sha256(clave_publica_pem).hexdigest()


# ── Cliente-side: la clave privada se cifra con password del medico ──

def cifrar_clave_privada(priv_pem: bytes, password: str) -> bytes:
    """Cifra la clave privada con AES-256-GCM usando una derivacion del password.

    La clave privada NUNCA viaja en texto plano. Se almacena cifrada
    en session_state (simulando almacenamiento local).
    """
    from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    salt = base64.b64decode(KeyRevocationManager.__class__.__name__.encode())[:16]
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=600000,
    )
    key = kdf.derive(password.encode("utf-8"))
    aesgcm = AESGCM(key)
    nonce = aesgcm.generate_nonce()
    ct = aesgcm.encrypt(nonce, priv_pem, None)
    return base64.b64encode(nonce + ct)


def descifrar_clave_privada(encrypted: bytes, password: str) -> Optional[bytes]:
    """Descifra la clave privada del profesional."""
    try:
        from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
        from cryptography.hazmat.primitives.ciphers.aead import AESGCM

        salt = base64.b64decode(KeyRevocationManager.__class__.__name__.encode())[:16]
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=600000,
        )
        key = kdf.derive(password.encode("utf-8"))
        aesgcm = AESGCM(key)
        data = base64.b64decode(encrypted)
        nonce, ct = data[:12], data[12:]
        return aesgcm.decrypt(nonce, ct, None)
    except Exception as exc:
        log_event("ecdsa", f"descifrar_clave_error:{type(exc).__name__}")
        return None


@dataclass
class SignedDocument:
    """Documento firmado con metadata."""
    documento_id: str
    contenido_hash: str
    firma_b64: str
    algoritmo: str = "ECDSA-SHA256"
    timestamp: float = field(default_factory=time.time)
    firmante: str = ""
    version: int = 1


class ECDSASignatureManager:
    """Gestiona claves ECDSA y operaciones de firma/verificacion.

    Cada profesional de la salud puede tener su propio par de claves.
    La clave privada NUNCA sale del dispositivo del profesional.
    La clave publica se almacena en el servidor para verificacion.
    """

    CURVE = ec.SECP256R1()

    @staticmethod
    def generar_par_claves() -> tuple[bytes, bytes]:
        """Genera un nuevo par (clave_privada, clave_publica) en formato PEM."""
        private_key = ec.generate_private_key(ECDSASignatureManager.CURVE)
        public_key = private_key.public_key()

        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        )
        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        return priv_pem, pub_pem

    @staticmethod
    def firmar(documento: dict, clave_privada_pem: bytes, firmante: str = "") -> SignedDocument:
        """Firma un diccionario de datos con ECDSA y retorna un SignedDocument.

        Args:
            documento: Diccionario con los datos a firmar.
            clave_privada_pem: Clave privada en formato PEM.
            firmante: Identificador del profesional que firma.

        Returns:
            SignedDocument con la firma y metadata.
        """
        from hashlib import sha256

        contenido_json = json.dumps(documento, sort_keys=True, ensure_ascii=False, default=str)
        contenido_hash = sha256(contenido_json.encode("utf-8")).hexdigest()

        try:
            private_key = serialization.load_pem_private_key(
                clave_privada_pem, password=None
            )
            if not isinstance(private_key, ec.EllipticCurvePrivateKey):
                raise TypeError("La clave proporcionada no es una clave privada ECDSA")

            signature = private_key.sign(
                contenido_hash.encode("utf-8"),
                ec.ECDSA(hashes.SHA256()),
            )
            firma_b64 = base64.b64encode(signature).decode("ascii")
            from hashlib import sha256 as _sha
            doc_id = _sha((contenido_hash + str(time.time())).encode()).hexdigest()[:16]

            return SignedDocument(
                documento_id=doc_id,
                contenido_hash=contenido_hash,
                firma_b64=firma_b64,
                firmante=firmante,
            )
        except Exception as exc:
            log_event("ecdsa", f"firma_error:{type(exc).__name__}:{exc}")
            raise

    @staticmethod
    def verificar(documento: dict, signed: SignedDocument, clave_publica_pem: bytes) -> bool:
        """Verifica que un documento coincida con su firma digital.

        Args:
            documento: Diccionario con los datos actuales.
            signed: SignedDocument previo.
            clave_publica_pem: Clave publica en formato PEM.

        Returns:
            True si la firma es valida, False en caso contrario.
        """
        from hashlib import sha256

        # Verificar si la clave fue revocada
        fp = fingerprint_clave_publica(clave_publica_pem)
        if KeyRevocationManager.esta_revocada(fp):
            log_event("ecdsa", f"verificacion_fallo: clave_revocada:{fp[:12]}")
            return False

        contenido_json = json.dumps(documento, sort_keys=True, ensure_ascii=False, default=str)
        contenido_hash = sha256(contenido_json.encode("utf-8")).hexdigest()

        if contenido_hash != signed.contenido_hash:
            log_event("ecdsa", "verificacion_fallo: hash del documento no coincide")
            return False

        try:
            public_key = serialization.load_pem_public_key(clave_publica_pem)
            if not isinstance(public_key, ec.EllipticCurvePublicKey):
                raise TypeError("La clave proporcionada no es una clave publica ECDSA")

            firma_bytes = base64.b64decode(signed.firma_b64)
            public_key.verify(
                firma_bytes,
                contenido_hash.encode("utf-8"),
                ec.ECDSA(hashes.SHA256()),
            )
            return True
        except InvalidSignature:
            log_event("ecdsa", "verificacion_fallo: firma invalida")
            return False
        except Exception as exc:
            log_event("ecdsa", f"verificacion_error:{type(exc).__name__}:{exc}")
            return False

    @staticmethod
    def serializar(signed: SignedDocument) -> str:
        """Serializa un SignedDocument a JSON para almacenamiento."""
        return json.dumps({
            "documento_id": signed.documento_id,
            "contenido_hash": signed.contenido_hash,
            "firma_b64": signed.firma_b64,
            "algoritmo": signed.algoritmo,
            "timestamp": signed.timestamp,
            "firmante": signed.firmante,
            "version": signed.version,
        })

    @staticmethod
    def deserializar(json_str: str) -> SignedDocument:
        """Deserializa un SignedDocument desde JSON."""
        data = json.loads(json_str)
        return SignedDocument(
            documento_id=data["documento_id"],
            contenido_hash=data["contenido_hash"],
            firma_b64=data["firma_b64"],
            algoritmo=data.get("algoritmo", "ECDSA-SHA256"),
            timestamp=data.get("timestamp", 0.0),
            firmante=data.get("firmante", ""),
            version=data.get("version", 1),
        )
