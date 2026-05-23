"""Cifrado de grado militar AES-256-GCM para campos PHI.

Cifra campos sensibles antes de persistir en Supabase.
La clave maestra se inyecta via st.secrets o variable de entorno.
"""

from __future__ import annotations

import base64
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class FieldEncryptor:
    """Cifrado/descifrado de campos sensibles con AES-256-GCM.
    
    Uso:
        ciphertext = FieldEncryptor.encrypt_field("texto sensible")
        plaintext = FieldEncryptor.decrypt_field(ciphertext)
    """
    
    _MASTER_KEY: Optional[bytes] = None
    
    @classmethod
    def _get_key(cls) -> bytes:
        if cls._MASTER_KEY is None:
            raw = os.getenv("MEDICARE_MASTER_CRYPTO_KEY", "")
            if not raw:
                import streamlit as st
                raw = st.secrets.get("MEDICARE_MASTER_CRYPTO_KEY", "ClaveMaestraDe32BytesParaPruebasLocal")
            # Derive 32 bytes for AES-256
            key = raw.encode("utf-8").ljust(32, b'\0')[:32]
            cls._MASTER_KEY = base64.urlsafe_b64encode(key)
        return base64.urlsafe_b64decode(cls._MASTER_KEY)
    
    @classmethod
    def encrypt_field(cls, plaintext: str) -> str:
        """Cifra un campo de texto con AES-256-GCM.
        
        Retorna: base64(nonce 12 bytes + ciphertext)
        """
        if not plaintext:
            return plaintext
        aesgcm = AESGCM(cls._get_key())
        nonce = os.urandom(12)
        ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
        return base64.b64encode(nonce + ct).decode("utf-8")
    
    @classmethod
    def decrypt_field(cls, ciphertext_b64: str) -> str:
        """Descifra un campo previamente cifrado con encrypt_field()."""
        if not ciphertext_b64:
            return ciphertext_b64
        try:
            data = base64.b64decode(ciphertext_b64.encode("utf-8"))
            if len(data) < 13:
                return ciphertext_b64
            nonce = data[:12]
            ct = data[12:]
            aesgcm = AESGCM(cls._get_key())
            return aesgcm.decrypt(nonce, ct, None).decode("utf-8")
        except Exception:
            return ciphertext_b64
