"""Configuracion central: variables de entorno, constantes y paths."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ASSETS_DIR = PROJECT_ROOT / "assets"

load_dotenv(PROJECT_ROOT / ".env", encoding="utf-8-sig")


def _get_secret(key: str, default: str = "") -> str:
    """Lee variable de entorno; en Streamlit Cloud tambien consulta st.secrets."""
    val = os.getenv(key, "")
    if val:
        return val
    try:
        import streamlit as st
        # Streamlit inyecta secrets como env vars, pero st.secrets es fallback extra
        if hasattr(st, "secrets") and key in st.secrets:
            return str(st.secrets[key])
    except Exception:
        pass
    return default


SUPABASE_URL = _get_secret("SUPABASE_URL")
SUPABASE_KEY = _get_secret("SUPABASE_KEY")
SUPABASE_SERVICE_ROLE_KEY = _get_secret("SUPABASE_SERVICE_ROLE_KEY") or _get_secret("SUPABASE_SERVICE_KEY")

DEBUG = os.getenv("BILLING_DEBUG", "false").strip().lower() in {"1", "true", "yes", "si"}
ALLOW_LOCAL_FALLBACK = os.getenv("BILLING_ALLOW_LOCAL_FALLBACK", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "si",
    "sí",
}

APP_NAME = "Medicare Billing Pro"
APP_VERSION = "1.0.0"
APP_DESCRIPTION = "Gestion de facturacion, cobros y reportes contables para profesionales de la salud."
PAGE_TITLE = "Medicare Billing Pro | Facturacion Medica"

ENABLE_EXCEL_EXPORT = True
ENABLE_PDF_EXPORT = True
ITEMS_PER_PAGE_DEFAULT = 50
