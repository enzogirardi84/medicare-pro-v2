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
