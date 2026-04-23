"""Helpers privados de autenticación. Extraído de core/auth.py."""
import secrets
import time
from html import escape

import streamlit as st

from core.app_logging import log_event
from core.auth_security import limpiar_fallos_login
from core.database import (
    cargar_datos,
    guardar_datos,
    login_usa_monolito_legacy,
    modo_shard_activo,
    tenant_key_normalizado,
)
from core.email_2fa import (
    SESSION_KEY,
    desafio_email_2fa_activo,
    limpiar_desafio_email_2fa,
    reenviar_codigo_login,
    verificar_codigo_ingresado,
)
from core.password_crypto import (
    aplicar_hash_tras_login_ok,
)
from core.utils import (
    ahora,
    normalizar_usuario_sistema,
    obtener_pin_usuario,
)

_DEBOUNCE_GUARDAR_LOGS_CLINICA_SEC = 60.0
_SESSION_LOGIN_FLASH = "_mc_auth_login_flash"


def _auth_set_flash(key: str, kind: str, message: str) -> None:
    return None


def _auth_pop_flash(key: str) -> None:
    return None


def _auth_loader_markup(subtitle: str) -> str:
    texto = escape(str(subtitle or "Autenticando..."))
    return f"""
<style>
.mc-auth-overlay{{position:fixed;inset:0;background:rgba(3,6,15,0.82);
backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);display:flex;
flex-direction:column;justify-content:center;align-items:center;z-index:9999999;
gap:16px;padding:1rem;text-align:center;
animation:mc-auth-fadeout 0.4s ease 4s forwards;}}
.mc-auth-spinner{{display:block;flex:0 0 auto;width:46px;height:46px;
border:3px solid rgba(255,255,255,0.08);border-left-color:#14b8a6;
border-top-color:#60a5fa;border-radius:50%;animation:mc-auth-spin 0.9s linear infinite;
-webkit-animation:mc-auth-spin 0.9s linear infinite;transform-origin:center center;
will-change:transform;backface-visibility:hidden;-webkit-backface-visibility:hidden;}}
.mc-auth-title{{color:#f1f5f9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
font-size:18px;font-weight:700;letter-spacing:0.2px;margin:0;}}
.mc-auth-sub{{color:#94a3b8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
font-size:13px;font-weight:500;letter-spacing:0.25px;margin:0;}}
@keyframes mc-auth-spin{{to{{transform:rotate(360deg);}}}}
@-webkit-keyframes mc-auth-spin{{to{{transform:rotate(360deg);}}}}
@keyframes mc-auth-fadeout{{from{{opacity:1}}to{{opacity:0;pointer-events:none;visibility:hidden;}}}}
@media (max-width: 767px){{
  .mc-auth-overlay{{gap:14px;padding:0.9rem;background:rgba(3,6,15,0.9);}}
  .mc-auth-spinner{{width:42px;height:42px;}}
  .mc-auth-title{{font-size:16px;}}
  .mc-auth-sub{{font-size:12px;}}
}}
</style>
<div class="mc-auth-overlay" role="status" aria-live="polite">
  <div class="mc-auth-spinner mc-spinner" aria-hidden="true"></div>
  <p class="mc-auth-title">MediCare Enterprise PRO</p>
  <p class="mc-auth-sub">{texto}</p>
</div>
"""


def _auth_strip_pwreset_url_si_hay_param() -> bool:
    """
    Sin recuperación por correo en esta instalación: si la URL trae ?pwreset=, se elimina el parámetro
    y se devuelve True para mostrar un aviso único en la pantalla de login.
    """
    qp = getattr(st, "query_params", None)
    if qp is None:
        return False
    try:
        if qp.get("pwreset") is None:
            return False
    except Exception:
        return False
    _auth_strip_pwreset_query_param()
    st.session_state.pop("mc_pwreset_token", None)
    st.session_state.pop("mc_auth_mode_radio", None)
    return True


def _auth_strip_pwreset_query_param() -> None:
    # Soporte moderno para st.query_params
    try:
        if "pwreset" in st.query_params:
            del st.query_params["pwreset"]
    except Exception:
        # Fallback: API antigua (versiones muy viejas de Streamlit)
        qp = getattr(st, "query_params", None)
        if qp is None:
            return
        try:
            qp.pop("pwreset", None)
        except Exception:
            pass


def _auth_strip_modulo_query_param() -> None:
    """Quita ?modulo= de la URL en la pantalla de login (marcadores viejos). Compatible con Streamlit sin query_params."""
    if st.session_state.get("logeado"):
        return
    qp = getattr(st, "query_params", None)
    if qp is None:
        return
    try:
        raw = qp.get("modulo")
        if raw is None:
            return
        if isinstance(raw, list):
            effective = "".join(str(x) for x in raw).strip()
        else:
            effective = str(raw).strip()
        if not effective:
            return
        qp.pop("modulo", None)
    except Exception:
        pass


def _buscar_usuario_por_login(login_texto: str):
    login_normalizado = str(login_texto or "").strip().lower()
    if not login_normalizado:
        return None
    for key_db in st.session_state.get("usuarios_db", {}).keys():
        if str(key_db or "").strip().lower() == login_normalizado:
            return key_db
    return None


def _pin_coincide_tiempo_constante(user_data: dict, pin_raw: str) -> bool:
    pin = str(pin_raw or "").strip()
    if len(pin) != 4 or not pin.isdigit():
        return False
    alm = str(obtener_pin_usuario(user_data) or "").strip()
    if not alm:
        return False
    try:
        return secrets.compare_digest(pin, alm)
    except Exception:
        return False


def _cargar_db_login(empresa_login: str, u_limpio: str):
    """En modo shard: admin y allowlist cargan monolito legacy; el resto solo su clínica."""
    st.session_state.pop("_db_monolito_sesion", None)
    if not modo_shard_activo():
        d = cargar_datos(force=True)
        return (d, None) if d is not None else (None, "No se pudieron cargar los datos.")
    if login_usa_monolito_legacy(u_limpio):
        st.session_state["_db_monolito_sesion"] = True
        d = cargar_datos(force=True, monolito_legacy=True)
        return (d, None) if d is not None else (None, "No se pudo cargar la base global (monolito).")
    tk = tenant_key_normalizado(empresa_login)
    if not tk:
        return None, "En modo multiclínica debés ingresar **Empresa / Clínica** (como está dada de alta)."
    d = cargar_datos(force=True, tenant_key=tk)
    if d is None:
        return None, "No hay datos para esa clínica. Verificá el nombre o contactá a soporte."
    return d, None


def _persistir_logs_tras_rechazo_clinica():
    """Primer rechazo en la sesion guarda enseguida; los siguientes, como maximo cada ~60s."""
    if not st.session_state.get("_login_clinica_rechazo_guardado_once"):
        st.session_state["_login_clinica_rechazo_guardado_once"] = True
        guardar_datos()
        return
    ahora_ts = time.time()
    clave = "_debounce_guardar_logs_clinica_ts"
    ultimo = float(st.session_state.get(clave, 0) or 0)
    if ahora_ts - ultimo < _DEBOUNCE_GUARDAR_LOGS_CLINICA_SEC:
        return
    st.session_state[clave] = ahora_ts
    guardar_datos()


def _completar_login_exitoso(user_data: dict, u_limpio: str, accion_log: str, evento_log: str):
    limpiar_desafio_email_2fa()
    limpiar_fallos_login(u_limpio)
    sesion = dict(user_data)
    login_key = str(sesion.get("usuario_login") or u_limpio or "").strip().lower()
    sesion = normalizar_usuario_sistema(sesion)
    sesion["usuario_login"] = login_key or u_limpio.strip().lower()
    st.session_state["u_actual"] = sesion
    st.session_state["logeado"] = True
    st.session_state.setdefault("logs_db", [])
    st.session_state["logs_db"].append(
        {
            "F": ahora().strftime("%d/%m/%Y"),
            "H": ahora().strftime("%H:%M"),
            "U": user_data["nombre"],
            "E": user_data["empresa"],
            "A": accion_log,
        }
    )
    log_event("auth", evento_log)
    try:
        guardar_datos(spinner=False)
    except Exception:
        pass
    st.session_state["_mc_login_transition"] = True
    st.rerun()


def _render_bloque_verificacion_email_2fa() -> bool:
    """Si hay desafío activo, muestra UI y devuelve True (el caller debe st.stop())."""
    fb = st.session_state.pop("_mc_2fa_resend_toast", None)
    if fb:
        if fb[0] == "ok":
            st.success(fb[1])
        else:
            st.error(fb[1])

    p = st.session_state.get(SESSION_KEY)
    if not p:
        return False
    if not desafio_email_2fa_activo():
        limpiar_desafio_email_2fa()
        st.warning("La verificación por correo venció. Volvé a iniciar sesión.")
        return False

    st.subheader("Verificación por correo")
    st.caption(f"Código enviado a **{p.get('destino_mascarado', 'tu correo')}**.")
    with st.form("form_email_2fa"):
        cod = st.text_input("Código de 6 dígitos", max_chars=6, placeholder="000000")
        if st.form_submit_button("Confirmar acceso", use_container_width=True):
            ok, err = verificar_codigo_ingresado(cod)
            if ok:
                uk = p.get("usuario_key")
                u_limpio = str(p.get("u_limpio") or "")
                limpiar_desafio_email_2fa()
                user_data = dict(st.session_state["usuarios_db"][uk])
                user_data["usuario_login"] = uk
                _completar_login_exitoso(user_data, u_limpio, "Login", "login_ok")
            else:
                st.error(err)

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Reenviar código", use_container_width=True):
            ok_r, err_r = reenviar_codigo_login()
            st.session_state["_mc_2fa_resend_toast"] = (
                ("ok", "Nuevo código enviado.") if ok_r else ("err", err_r)
            )
            st.rerun()
    with c2:
        if st.button("Cancelar", use_container_width=True):
            limpiar_desafio_email_2fa()
            st.rerun()
    return True
