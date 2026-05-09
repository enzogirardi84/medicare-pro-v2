"""HTML/CSS de la landing pre-login (publicidad)."""

from __future__ import annotations

import html
import os

import streamlit as st

from core._landing_html_parts import _PART_1, _PART_2, _PART_3, _PART_4, _PART_5, _PART_6, _PART_7


def billing_app_url() -> str:
    """URL publica/local de Medicare Billing Pro."""
    value = os.getenv("BILLING_APP_URL", "").strip()
    if value:
        return value
    try:
        return str(st.secrets.get("BILLING_APP_URL", "") or "").strip()
    except Exception:
        return ""


def obtener_html_landing_publicidad(logo_html: str) -> str:
    """Retorna el bloque completo <style> + markup para st.markdown(..., unsafe_allow_html=True)."""
    billing_url = billing_app_url() or "http://localhost:8502"
    return (
        _PART_1 + _PART_2 + _PART_3 + _PART_4 + _PART_5 + _PART_6 + _PART_7
    ).replace("__LOGO__", logo_html).replace("__BILLING_APP_URL__", html.escape(billing_url, quote=True))
