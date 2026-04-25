"""Validaciones de entrada reutilizables (formato email, etc.)."""

from __future__ import annotations

import re

# Local-part y dominio razonables; no pretende cubrir el RFC completo.
_EMAIL_RE = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


def email_formato_aceptable(valor: str) -> bool:
    s = (valor or "").strip()
    if len(s) < 5 or len(s) > 254 or "@" not in s:
        return False
    return bool(_EMAIL_RE.match(s))


def validar_dni(dni: str) -> bool:
    """Valida que el DNI sea numérico y tenga al menos 7 dígitos."""
    s = (dni or "").strip()
    return s.isdigit() and len(s) >= 7


def validar_telefono(telefono: str) -> bool:
    """Valida formato básico de teléfono (7+ dígitos, permite +, espacios, guiones)."""
    s = (telefono or "").strip()
    if len(s) < 7:
        return False
    # Permite +, espacios, guiones, paréntesis, dígitos
    return bool(re.match(r"^[\d\s\+\-\(\)]+$", s))


def validar_email(email: str) -> bool:
    """Alias público de email_formato_aceptable para tests."""
    return email_formato_aceptable(email)
