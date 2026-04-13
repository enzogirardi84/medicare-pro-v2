"""Normalización de nombre de empresa/clínica (sin dependencias de otros módulos core)."""

from __future__ import annotations

from typing import Optional


def norm_empresa_key(nombre: Optional[str]) -> str:
    return str(nombre or "").strip().lower()
