"""Autenticación simplificada para Medicare Billing Pro.
Comparte la misma tabla `usuarios` de Medicare Pro en Supabase.
"""
from __future__ import annotations

import base64
import gzip
import json
import os
import secrets
from typing import Any, Dict, Optional

import streamlit as st

from core.app_logging import log_event

try:
    import bcrypt
except ImportError:
    bcrypt = None

_COMPRESS_MAGIC = "_mc_gz2"


def check_supabase_connection() -> bool:
    try:
        from core.db_sql import supabase
        return supabase is not None
    except Exception:
        return False


def _decompress_medicare_payload(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict) and _COMPRESS_MAGIC in raw:
        try:
            compressed = base64.b64decode(raw[_COMPRESS_MAGIC])
            data = json.loads(gzip.decompress(compressed).decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except Exception as e:
            log_event("auth", f"payload_decompress_error:{type(e).__name__}")
            return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception as e:
            log_event("auth", f"payload_json_error:{type(e).__name__}")
    return {}


def _verificar_password_medicare(user: Dict[str, Any], plain: str) -> bool:
    stored_hash = str(user.get("pass_hash") or user.get("password_hash") or "").strip()
    if stored_hash:
        if stored_hash.startswith(("$2a$", "$2b$", "$2y$")):
            if not bcrypt:
                return False
            try:
                return bcrypt.checkpw(str(plain or "").encode("utf-8"), stored_hash.encode("ascii"))
            except Exception as e:
                log_event("auth", f"bcrypt_verify_error:{type(e).__name__}")
                return False
        return secrets.compare_digest(str(plain or "").strip(), stored_hash)
    legacy = str(user.get("pass") or user.get("password") or user.get("clave") or "").strip()
    return bool(legacy) and secrets.compare_digest(str(plain or "").strip(), legacy)


def _normalizar_empresa_id(user: Dict[str, Any]) -> str:
    empresa_id = str(user.get("empresa_id") or "").strip()
    if empresa_id:
        return empresa_id
    empresa = str(user.get("empresa") or "Mi Empresa").strip()
    return empresa.lower().replace(" ", "-")[:80] or "mi-empresa"


def _buscar_usuario_en_monolito(usuario: str) -> Optional[Dict[str, Any]]:
    from core.db_sql import supabase

    resp = supabase.table("medicare_db").select("datos").eq("id", 1).limit(1).execute()
    if not resp.data:
        return None
    blob = _decompress_medicare_payload(resp.data[0].get("datos"))
    usuarios_db = blob.get("usuarios_db") if isinstance(blob, dict) else {}
    if not isinstance(usuarios_db, dict):
        return None
    usuario_norm = str(usuario or "").strip().lower()
    for login, data in usuarios_db.items():
        if str(login or "").strip().lower() == usuario_norm and isinstance(data, dict):
            user = dict(data)
            user.setdefault("usuario_login", str(login))
            return user
    return None


def _buscar_usuario_en_tabla(usuario: str) -> Optional[Dict[str, Any]]:
    from core.db_sql import supabase

    try:
        resp = supabase.table("usuarios").select("*").eq("usuario_login", usuario).limit(1).execute()
        if resp.data:
            return dict(resp.data[0])
    except Exception as e:
        log_event("auth", f"usuarios_table_unavailable:{type(e).__name__}")
    return None


def authenticate_user(usuario: str, password: str) -> Optional[Dict[str, Any]]:
    """Autentica con los mismos usuarios de Medicare Pro."""
    try:
        from core.db_sql import supabase
        if not supabase:
            log_event("auth", "supabase_no_disponible")
            return None

        usuario_limpio = str(usuario or "").strip().lower()
        user = _buscar_usuario_en_tabla(usuario_limpio) or _buscar_usuario_en_monolito(usuario_limpio)
        if not user:
            log_event("auth", f"login_fail_user:{usuario}")
            return None

        if _verificar_password_medicare(user, password):
            user["empresa_id"] = _normalizar_empresa_id(user)
            user.setdefault("empresa", "Mi Empresa")
            log_event("auth", f"login_ok:{usuario_limpio}")
            return user
        log_event("auth", f"login_fail_pw:{usuario}")
        return None
    except Exception as e:
        log_event("auth", f"auth_error:{type(e).__name__}:{e}")
        return None


def render_login() -> bool:
    """Renderiza pantalla de login. Retorna True si el usuario se autenticó."""
    if st.session_state.get("billing_authenticated"):
        return True

    st.markdown("""
    <style>
    .billing-login-box {
        max-width: 420px;
        margin: 6vh auto;
        padding: 2.5rem 2rem;
        background: #fff;
        border-radius: 16px;
        box-shadow: 0 8px 32px rgba(0,0,0,0.10);
    }
    .billing-login-box h2 { color: #1e293b; margin-bottom: 0.25rem; }
    .billing-login-box p { color: #64748b; font-size: 0.9rem; margin-bottom: 1.5rem; }
    </style>
    """, unsafe_allow_html=True)

    with st.container():
        st.markdown('<div class="billing-login-box">', unsafe_allow_html=True)
        st.markdown("## 🧾 Medicare Billing Pro")
        st.markdown("<p>Facturación médica profesional</p>", unsafe_allow_html=True)

        usuario = st.text_input("Usuario", key="billing_login_user", placeholder="admin")
        password = st.text_input("Contraseña", type="password", key="billing_login_pw", placeholder="••••••••")

        col1, col2 = st.columns([1, 1])
        with col1:
            if st.button("Ingresar", use_container_width=True, type="primary"):
                if not usuario or not password:
                    st.error("Completá todos los campos.")
                else:
                    user = authenticate_user(usuario, password)
                    if user:
                        st.session_state["billing_authenticated"] = True
                        st.session_state["billing_user"] = user
                        st.session_state["billing_empresa_id"] = user.get("empresa_id", "")
                        st.session_state["billing_empresa_nombre"] = user.get("empresa", "Mi Empresa")
                        st.rerun()
                    else:
                        st.error("Credenciales inválidas o sin acceso.")
        with col2:
            st.caption("Usa las mismas credenciales de Medicare Pro.")

        st.markdown("</div>", unsafe_allow_html=True)

    return False


def render_logout_button() -> None:
    if st.sidebar.button("🚪 Cerrar sesión", use_container_width=True):
        for k in list(st.session_state.keys()):
            if k.startswith("billing_"):
                del st.session_state[k]
        st.rerun()


def require_auth() -> bool:
    """Wrapper: asegura que el usuario esté autenticado antes de mostrar la app."""
    if not st.session_state.get("billing_authenticated"):
        render_login()
        return False
    return True
