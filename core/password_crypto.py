"""
Hash y verificación de contraseñas (bcrypt).

- Si el usuario tiene `pass_hash`, solo se valida contra el hash.
- Si solo tiene `pass` en texto plano (datos viejos), se acepta el match y se puede migrar a hash.
"""

from __future__ import annotations

import re
import secrets
from typing import Optional, Tuple

try:
    import bcrypt
except ImportError:
    bcrypt = None  # type: ignore

BCRYPT_PREFIXES = ("$2a$", "$2b$", "$2y$")


def hashing_disponible() -> bool:
    return bcrypt is not None


def bcrypt_rounds_config() -> int:
    try:
        import streamlit as st

        r = int(st.secrets.get("PASSWORD_BCRYPT_ROUNDS", 10))
        return max(10, min(15, r))
    except Exception:
        return 10


def parece_hash_bcrypt(valor: str) -> bool:
    s = (valor or "").strip()
    return s.startswith(BCRYPT_PREFIXES)


def hash_password(plain: str, rounds: int = 12) -> str:
    if not bcrypt:
        raise RuntimeError("bcrypt no instalado")
    p = (plain or "").encode("utf-8")
    if len(p) > 72:
        p = p[:72]
    return bcrypt.hashpw(p, bcrypt.gensalt(rounds=rounds)).decode("ascii")


def verificar_password(plain: str, almacenado: str) -> bool:
    """Acepta hash bcrypt o texto plano legacy (comparación constante en tiempo)."""
    a = (plain or "").strip()
    b = (almacenado or "").strip()
    if not a or not b:
        return False
    if parece_hash_bcrypt(b):
        if not bcrypt:
            return False
        try:
            return bcrypt.checkpw(a.encode("utf-8"), b.encode("ascii"))
        except Exception:
            return False
    return secrets.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


def password_usuario_coincide(user_dict: dict, plain: str) -> Tuple[bool, bool]:
    """
    Devuelve (coincide, migrar_a_hash).

    migrar_a_hash=True si hubo match por `pass` en claro y conviene guardar `pass_hash`.
    """
    ph = user_dict.get("pass_hash")
    if ph is not None and str(ph).strip():
        return verificar_password(plain, str(ph).strip()), False
    legacy = user_dict.get("pass", "")
    if verificar_password(plain, str(legacy)):
        return True, bool(hashing_disponible())
    return False, False


def aplicar_hash_tras_login_ok(user_dict: dict, plain: str, rounds: int = 12) -> None:
    """Reemplaza almacenamiento en claro por hash; deja `pass` vacío."""
    if not hashing_disponible():
        return
    user_dict["pass_hash"] = hash_password(plain, rounds=rounds)
    user_dict["pass"] = ""


def password_min_length() -> int:
    """Largo mínimo para contraseñas nuevas o recuperadas (secrets PASSWORD_MIN_LENGTH, default 8, rango 4–128)."""
    try:
        import streamlit as st

        n = int(st.secrets.get("PASSWORD_MIN_LENGTH", 8))
    except Exception:
        n = 8
    return max(4, min(128, n))


def password_exigir_letra_y_numero() -> bool:
    try:
        import streamlit as st

        v = st.secrets.get("PASSWORD_REQUIRE_LETTER_AND_DIGIT", False)
        if isinstance(v, bool):
            return v
        return str(v).strip().lower() in ("1", "true", "yes", "si", "on")
    except Exception:
        return False


def mensaje_password_no_cumple_politica(plain: str) -> Optional[str]:
    """
    None si cumple política; si no, mensaje corto en español.
    """
    p = plain or ""
    mn = password_min_length()
    if len(p) < mn:
        return f"La contraseña debe tener al menos {mn} caracteres."
    if len(p) > 128:
        return "La contraseña no puede superar 128 caracteres."
    if password_exigir_letra_y_numero():
        if not re.search(r"[a-zA-ZáéíóúÁÉÍÓÚñÑüÜ]", p):
            return "La contraseña debe incluir al menos una letra."
        if not re.search(r"\d", p):
            return "La contraseña debe incluir al menos un número."
    return None


def texto_ayuda_politica_password_breve() -> str:
    """Texto corto para UI (login / recuperación) según secrets."""
    mn = password_min_length()
    partes = [f"al menos {mn} caracteres"]
    if password_exigir_letra_y_numero():
        partes.append("una letra y un número")
    return "La contraseña debe tener " + " y ".join(partes) + "."


def establecer_password_nuevo(user_dict: dict, plain: str, rounds: int = 12) -> None:
    """Recuperación de contraseña u alta: solo hash si bcrypt está disponible."""
    if hashing_disponible():
        user_dict["pass_hash"] = hash_password(plain, rounds=rounds)
        user_dict["pass"] = ""
    else:
        user_dict["pass"] = plain
        user_dict.pop("pass_hash", None)
