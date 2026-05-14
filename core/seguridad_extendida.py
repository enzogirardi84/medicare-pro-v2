"""Seguridad: HTTPS, CSRF y logs de acceso.
"""
from __future__ import annotations

import time
from datetime import datetime
from typing import Optional

import streamlit as st

from core.app_logging import log_event


# ============================================================
# 1. FORZAR HTTPS
# ============================================================
def verificar_https():
    """Muestra advertencia si la conexion no es HTTPS."""
    try:
        from urllib.parse import urlparse
        # Streamlit Cloud siempre usa HTTPS, pero verificamos por si acaso
        host = st.context.headers.get("Host", "") if hasattr(st, "context") else ""
        if host and "localhost" not in host and "streamlit.app" in host:
            scheme = st.context.headers.get("X-Forwarded-Proto", "https")
            if scheme != "https":
                st.warning(
                    "Conexion no segura detectada. Usa HTTPS para proteger los datos de los pacientes.",
                    icon="🔒"
                )
    except Exception:
        pass  # Ignorar errores de contexto


# ============================================================
# 2. CSRF TOKEN
# ============================================================
def generar_csrf_token() -> str:
    """Genera un token CSRF unico para esta sesion."""
    import hashlib
    import secrets
    if "_csrf_token" not in st.session_state:
        token = secrets.token_hex(32)
        st.session_state["_csrf_token"] = token
    return st.session_state["_csrf_token"]


def verificar_csrf_token(token_enviado: str) -> bool:
    """Verifica que el token CSRF coincida."""
    token_esperado = st.session_state.get("_csrf_token", "")
    if not token_esperado or not token_enviado:
        return False
    return token_enviado == token_esperado


def inject_csrf_form():
    """Inyecta campo oculto CSRF en formularios. Usar en forms con datos sensibles."""
    token = generar_csrf_token()
    st.markdown(
        f'<input type="hidden" name="csrf_token" value="{token}">',
        unsafe_allow_html=True,
    )


# ============================================================
# 3. LOGS DE ACCESO
# ============================================================
def registrar_acceso(evento: str, detalle: Optional[str] = None):
    """Registra un evento de acceso con timestamp y datos de sesion."""
    user = st.session_state.get("u_actual", {})
    username = str(user.get("usuario_login", user.get("nombre", "?")))
    rol = str(user.get("rol", "?"))
    empresa = str(user.get("empresa", "?"))

    # Obtener IP si disponible
    ip = "?"
    try:
        if hasattr(st, "context") and st.context.headers:
            ip = st.context.headers.get("X-Forwarded-For", "?")
    except Exception:
        pass

    log_event("acceso", f"{username}|{rol}|{empresa}|{ip}|{evento}|{detalle or ''}")


def render_logs_acceso():
    """Muestra los ultimos accesos registrados."""
    logs = st.session_state.get("logs_db", [])
    accesos = [
        l for l in logs
        if isinstance(l, str) and "acceso" in l
    ]
    if accesos:
        with st.expander("Ultimos accesos", expanded=False):
            for log_entry in accesos[-20:]:
                st.caption(log_entry[:120])
