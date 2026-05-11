"""Autenticacion para Medicare Billing Pro.

Comparte la misma tabla `usuarios` de Medicare Pro en Supabase.
"""
from __future__ import annotations

import base64
import gzip
import json
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
        except Exception:
            log_event("auth", "payload_decompress_error")
            return {}
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str) and raw.strip():
        try:
            data = json.loads(raw)
            return data if isinstance(data, dict) else {}
        except Exception:
            log_event("auth", "payload_json_error")
    return {}


def _verificar_password_medicare(user: Dict[str, Any], plain: str) -> bool:
    stored_hash = str(user.get("pass_hash") or user.get("password_hash") or "").strip()
    if stored_hash:
        if stored_hash.startswith(("$2a$", "$2b$", "$2y$")):
            if not bcrypt:
                return False
            try:
                return bcrypt.checkpw(str(plain or "").encode("utf-8"), stored_hash.encode("ascii"))
            except Exception:
                log_event("auth", "bcrypt_verify_error")
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
    except Exception as exc:
        log_event("auth", f"usuarios_table_unavailable:{type(exc).__name__}")
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
    except Exception as exc:
        log_event("auth", f"auth_error:{type(exc).__name__}:{exc}")
        return None


def render_login() -> bool:
    """Renderiza la pantalla de login."""
    if st.session_state.get("billing_authenticated"):
        return True

    st.markdown(
        """
        <style>
        header[data-testid="stHeader"] { background: transparent; }
        .main .block-container {
            max-width: 1180px;
            padding: 5rem 2rem 3rem !important;
        }
        .stApp {
            background: linear-gradient(180deg, #080d18 0%, #090e17 100%) !important;
        }
        .billing-login-hero,
        .billing-login-card {
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 8px;
            background: #0f172a;
            box-shadow: 0 18px 44px rgba(2, 6, 23, 0.34);
        }
        .billing-login-hero { padding: 1.5rem; background: rgba(15, 23, 42, 0.72); }
        .billing-login-card { padding: 1.25rem; }
        .billing-login-hero h1 {
            color: #f8fafc;
            font-size: 2.1rem;
            line-height: 1.08;
            margin: 0 0 0.65rem;
            letter-spacing: 0;
        }
        .billing-login-card h2 {
            color: #f8fafc;
            font-size: 1.35rem;
            margin: 0 0 0.25rem;
            letter-spacing: 0;
        }
        .billing-login-hero p,
        .billing-login-card p {
            color: #cbd5e1 !important;
            font-size: 0.96rem;
            margin: 0 0 1.15rem;
        }
        .billing-login-metrics {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.7rem;
        }
        .billing-login-metric {
            border: 1px solid rgba(148, 163, 184, 0.14);
            border-radius: 8px;
            padding: 0.85rem;
            background: rgba(2, 6, 23, 0.28);
        }
        .billing-login-metric span {
            display: block;
            color: #94a3b8;
            font-size: 0.72rem;
            font-weight: 700;
            text-transform: uppercase;
            margin-bottom: 0.35rem;
        }
        .billing-login-metric strong {
            color: #f8fafc;
            font-size: 0.98rem;
        }
        label, [data-testid="stCaptionContainer"] { color: #cbd5e1 !important; }
        [data-baseweb="input"] > div {
            background: rgba(15, 23, 42, 0.82) !important;
            border: 1px solid #334155 !important;
            border-radius: 8px !important;
            color: #f8fafc !important;
        }
        [data-baseweb="input"] > div:focus-within {
            border-color: #14b8a6 !important;
            box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.16) !important;
        }
        input { color: #f8fafc !important; }
        .stButton > button[kind="primary"],
        .stButton > button[data-testid="stBaseButton-primary"] {
            background: linear-gradient(135deg, #14b8a6 0%, #2563eb 100%) !important;
            border: 1px solid rgba(94, 234, 212, 0.35) !important;
            border-radius: 8px !important;
            color: #ffffff !important;
            font-weight: 700 !important;
            box-shadow: 0 8px 22px rgba(14, 165, 233, 0.24) !important;
        }
        .stButton > button[kind="primary"] p,
        .stButton > button[data-testid="stBaseButton-primary"] p { color: #ffffff !important; }
        @media (max-width: 760px) {
            .main .block-container { padding: 1.25rem 1rem 2rem !important; }
            .billing-login-metrics { grid-template-columns: 1fr; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    left, right = st.columns([1.25, 0.9], gap="large", vertical_alignment="center")
    with left:
        st.markdown(
            """
            <section class="billing-login-hero">
                <h1>Medicare Billing Pro</h1>
                <p>Gestion de presupuestos, pre-facturas, cobros y reportes contables conectada a Supabase.</p>
                <div class="billing-login-metrics">
                    <div class="billing-login-metric"><span>Datos</span><strong>Supabase</strong></div>
                    <div class="billing-login-metric"><span>Acceso</span><strong>Medicare Pro</strong></div>
                    <div class="billing-login-metric"><span>Modulo</span><strong>Facturacion</strong></div>
                </div>
            </section>
            """,
            unsafe_allow_html=True,
        )

    with right:
        st.markdown(
            """
            <section class="billing-login-card">
                <h2>Ingresar</h2>
                <p>Usa el mismo usuario de Medicare Pro.</p>
            </section>
            """,
            unsafe_allow_html=True,
        )
        with st.form("billing_login_form", border=False, clear_on_submit=False):
            usuario = st.text_input("Usuario", key="billing_login_user", placeholder="admin")
            password = st.text_input("Contrasena", type="password", key="billing_login_pw", placeholder="********")
            submitted = st.form_submit_button("Ingresar", use_container_width=True, type="primary")

        if submitted:
            usuario_limpio = str(usuario or st.session_state.get("billing_login_user", "")).strip()
            password_limpio = str(password or st.session_state.get("billing_login_pw", "")).strip()
            if not usuario_limpio or not password_limpio:
                st.error("Completa usuario y contrasena.")
            else:
                user = authenticate_user(usuario_limpio, password_limpio)
                if user:
                    st.session_state["billing_authenticated"] = True
                    st.session_state["billing_user"] = user
                    st.session_state["billing_empresa_id"] = user.get("empresa_id", "")
                    st.session_state["billing_empresa_nombre"] = user.get("empresa", "Mi Empresa")
                    st.rerun()
                else:
                    st.error("Credenciales invalidas o sin acceso.")
        st.caption("Los datos se guardan en Supabase cuando el servicio esta conectado.")

    return False


def render_logout_button() -> None:
    if st.sidebar.button("Cerrar sesion", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key.startswith("billing_"):
                del st.session_state[key]
        st.rerun()


def require_auth() -> bool:
    """Asegura que el usuario este autenticado antes de mostrar la app."""
    if not st.session_state.get("billing_authenticated"):
        render_login()
        return False
    return True
