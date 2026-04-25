"""
Generación y validación de tokens para reset de contraseña.
"""

import base64
import hashlib
import secrets
import time


def generar_token_reset(usuario: str, ttl_seconds: int = 3600) -> str:
    """Genera un token seguro para reset de contraseña."""
    salt = secrets.token_hex(8)
    ts = str(int(time.time()))
    payload = f"{usuario}:{ts}:{salt}"
    sig = hashlib.sha256(payload.encode()).hexdigest()[:16]
    return base64.urlsafe_b64encode(f"{payload}:{sig}:{ttl_seconds}".encode()).decode()


def validar_token_reset(token: str) -> str | None:
    """Valida token y retorna el usuario si es válido, o None."""
    try:
        decoded = base64.urlsafe_b64decode(token.encode()).decode()
        parts = decoded.rsplit(":", 2)
        if len(parts) != 3:
            return None
        payload, sig, ttl = parts
        usuario, ts, salt = payload.split(":")
        expected_sig = hashlib.sha256(payload.encode()).hexdigest()[:16]
        if not secrets.compare_digest(sig, expected_sig):
            return None
        if time.time() - float(ts) > float(ttl):
            return None
        return usuario
    except Exception:
        return None
