"""Rotacion automatizada de claves de cifrado de columnas.
Versionado de claves: cada payload cifrado incluye key_version_id
para que el sistema sepa que clave usar al descifrar datos historicos.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. VERSIONADO DE CLAVES
# ═══════════════════════════════════════════════════════════════════

@dataclass
class KeyVersion:
    """Una version de clave de cifrado."""
    version_id: str  # UUID v4
    created_at: float = field(default_factory=time.time)
    activa: bool = True
    razon_rotacion: str = ""


class KeyRotationManager:
    """Gestiona multiples versiones de claves de cifrado.

    - key_actual: se usa para NUEVOS cifrados (INSERT/UPDATE)
    - keys_historicas: permiten descifrar datos viejos

    Cada payload cifrado incluye key_version_id para saber
    que clave usar al descifrar.
    """

    KEY_PREFIX = "ck_"  # Column Key
    KEY_STORE_KEY = "_encryption_keys"

    def __init__(self, tenant_id: str):
        self._tenant_id = tenant_id
        self._keys: dict[str, bytes] = {}
        self._versions: list[KeyVersion] = []
        self._load_keys()

    def _load_keys(self) -> None:
        """Carga las claves desde session_state o env."""
        import streamlit as st
        store = st.session_state.setdefault(self.KEY_STORE_KEY, {})

        # Cargar versiones
        versions_data = store.get(f"versions_{self._tenant_id}", [])
        self._versions = [KeyVersion(**v) if isinstance(v, dict) else v for v in versions_data]

        # Cargar claves
        for v in self._versions:
            key_id = f"{self.KEY_PREFIX}{v.version_id}"
            if key_id in store:
                self._keys[v.version_id] = bytes.fromhex(store[key_id])

        # Si no hay claves, crear la inicial
        if not self._keys:
            self._crear_nueva_clave("inicializacion")

    def _crear_nueva_clave(self, razon: str = "rotacion_programada") -> str:
        """Deriva una nueva clave AES-256 a partir del master secret."""
        import uuid
        version_id = str(uuid.uuid4())

        master = os.environ.get("COLUMN_ENCRYPTION_KEY", "")
        if not master:
            raise ValueError("COLUMN_ENCRYPTION_KEY no configurada")

        # Derivar clave unica para esta version + tenant
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=f"{self._tenant_id}:{version_id}".encode("utf-8"),
            iterations=600000,
        )
        key = kdf.derive(master.encode("utf-8"))

        # Almacenar
        self._keys[version_id] = key
        self._versions.append(KeyVersion(
            version_id=version_id,
            razon_rotacion=razon,
        ))

        # Persistir
        import streamlit as st
        store = st.session_state.setdefault(self.KEY_STORE_KEY, {})
        store[f"ck_{version_id}"] = key.hex()
        store[f"versions_{self._tenant_id}"] = [v.__dict__ for v in self._versions]

        log_event("key_rotation", f"nueva_clave:{version_id[:12]}:{razon}")
        return version_id

    @property
    def key_actual_id(self) -> str:
        """ID de la clave actual (la mas reciente)."""
        if not self._versions:
            self._crear_nueva_clave()
        return self._versions[-1].version_id

    @property
    def key_actual(self) -> bytes:
        return self._keys[self.key_actual_id]

    def obtener_clave(self, version_id: str) -> Optional[bytes]:
        """Obtiene una clave por su version ID."""
        return self._keys.get(version_id)

    def rotar(self, razon: str = "rotacion_programada") -> str:
        """Rota a una nueva clave. La anterior queda como historica.

        Los datos existentes cifrados con la clave anterior
        siguen siendo legibles (la clave anterior se conserva).
        """
        return self._crear_nueva_clave(razon)


# ═══════════════════════════════════════════════════════════════════
# 2. CIFRADO CON VERSIONADO
# ═══════════════════════════════════════════════════════════════════

def encrypt_with_version(tenant_id: str, plaintext: str) -> str:
    """Cifra incluyendo key_version_id en el payload.

    El payload resultante incluye la version de clave usada
    para que el descifrado sepa que clave usar.

    Formato: base64(key_version_id[:12] + nonce + ciphertext)
    """
    if not plaintext:
        return ""

    mgr = KeyRotationManager(tenant_id)
    key = mgr.key_actual
    version_id = mgr.key_actual_id

    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)

    # Incluir version_id en el payload (primeros 12 bytes)
    payload = version_id[:12].encode("utf-8") + nonce + ct
    return base64.b64encode(payload).decode("ascii")


def decrypt_with_version(tenant_id: str, ciphertext_b64: str) -> str:
    """Descifra usando key_version_id del payload."""
    if not ciphertext_b64:
        return ""

    try:
        data = base64.b64decode(ciphertext_b64)
        version_id_prefix = data[:12].decode("utf-8")
        nonce = data[12:24]
        ct = data[24:]

        mgr = KeyRotationManager(tenant_id)

        # Buscar clave por version_id (primeros 12 chars)
        key = None
        for vid, k in mgr._keys.items():
            if vid.startswith(version_id_prefix):
                key = k
                break

        if key is None:
            log_event("key_rotation", f"clave_no_encontrada:{version_id_prefix}")
            return "[clave_no_disponible]"

        aesgcm = AESGCM(key)
        return aesgcm.decrypt(nonce, ct, None).decode("utf-8")

    except Exception as exc:
        log_event("key_rotation", f"decrypt_error:{type(exc).__name__}")
        return "[error_descifrado]"


# ═══════════════════════════════════════════════════════════════════
# 3. SCRIPT DE ROTACION PROGRAMADA
# ═══════════════════════════════════════════════════════════════════

def rotar_claves_todos_tenants(razon: str = "rotacion_mensual") -> dict[str, str]:
    """Rota las claves de todos los tenants registrados.

    Ejecutar via cron mensual.
    """
    tenants = os.environ.get("MEDICARE_TENANTS", "default,avalian,sancor").split(",")
    resultados = {}
    for t in tenants:
        t = t.strip()
        if t:
            mgr = KeyRotationManager(t)
            new_id = mgr.rotar(razon)
            resultados[t] = new_id[:12]
            log_event("key_rotation", f"rotado:{t}:{new_id[:12]}")
    return resultados
