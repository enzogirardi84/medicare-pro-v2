"""Configuracion centralizada de empresa_id para integraciones SQL/dual-write."""

from __future__ import annotations

import os
import uuid
from typing import Dict, Optional

import streamlit as st


EMPRESA_UUID_DEFAULT = "15b42b80-83a4-41c4-82e0-23df2dec7497"
_UUID_CONFIG_KEYS = (
    "EMPRESA_ID",
    "DEFAULT_EMPRESA_ID",
    "NEXTGEN_DEFAULT_EMPRESA_ID",
    "empresa_id",
)


def _uuid_valido(valor) -> str:
    texto = str(valor or "").strip()
    if not texto:
        return ""
    try:
        return str(uuid.UUID(texto))
    except Exception:
        return ""


def empresa_uuid_configurada(nombre_empresa: str = "") -> str:
    """
    Resuelve un UUID de empresa configurable para despliegues single-tenant.

    Prioridad:
    1. `st.secrets`
    2. variables de entorno
    3. fallback por defecto del despliegue actual
    """
    for clave in _UUID_CONFIG_KEYS:
        try:
            valor = _uuid_valido(st.secrets.get(clave, ""))
        except Exception:
            valor = ""
        if valor:
            return valor

    for clave in _UUID_CONFIG_KEYS:
        valor = _uuid_valido(os.getenv(clave, ""))
        if valor:
            return valor

    return _uuid_valido(EMPRESA_UUID_DEFAULT)


def empresa_record_configurado(nombre_empresa: str = "") -> Optional[Dict[str, str]]:
    """Devuelve un registro minimo de empresa para despliegues single-tenant."""
    nombre_limpio = str(nombre_empresa or "").strip()
    empresa_id = empresa_uuid_configurada(nombre_limpio)
    if not empresa_id or not nombre_limpio:
        return None
    return {
        "id": empresa_id,
        "nombre": nombre_limpio,
    }
