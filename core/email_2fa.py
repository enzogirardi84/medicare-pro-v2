"""
Segundo factor por correo tras contraseña correcta (opcional).

Secrets:
- LOGIN_EMAIL_2FA = true para activar (requiere SMTP y email en el usuario).
- SMTP_HOST, SMTP_PORT (587 o 465), SMTP_USER, SMTP_PASSWORD, SMTP_FROM
- SMTP_USE_TLS = true (STARTTLS en puerto 587); en puerto 465 se usa SSL implícito.
- EMAIL_2FA_HMAC_SECRET (recomendado): cadena larga para firmar el código; si falta, se usa SMTP_PASSWORD.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
import smtplib
import ssl
import time
import html as html_lib
from email.message import EmailMessage

import streamlit as st

from core.app_logging import log_event
from core.input_validation import email_formato_aceptable

SESSION_KEY = "_mc_email_2fa"
CODE_TTL_SEC = 600
RESEND_COOLDOWN_SEC = 90
MAX_CODE_TRIES = 5


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return s in ("1", "true", "yes", "si", "on")


def login_email_2fa_enabled() -> bool:
    try:
        return _truthy(st.secrets.get("LOGIN_EMAIL_2FA", False))
    except Exception:
        return False


def _smtp_settings():
    try:
        s = st.secrets
        host = str(s.get("SMTP_HOST", "") or "").strip()
        port = int(s.get("SMTP_PORT", 587))
        user = str(s.get("SMTP_USER", "") or "").strip()
        pwd = str(s.get("SMTP_PASSWORD", "") or "").strip()
        from_addr = str(s.get("SMTP_FROM", "") or "").strip() or user
        use_tls = _truthy(s.get("SMTP_USE_TLS", True))
        return host, port, user, pwd, from_addr, use_tls
    except Exception:
        return "", 587, "", "", "", True


def smtp_config_ok() -> bool:
    host, _port, _user, pwd, from_addr, _tls = _smtp_settings()
    return bool(host and pwd and from_addr)


def _hmac_key() -> bytes:
    try:
        raw = st.secrets.get("EMAIL_2FA_HMAC_SECRET", "") or st.secrets.get("SMTP_PASSWORD", "")
    except Exception:
        raw = ""
    raw = str(raw).strip()
    if len(raw) < 8:
        return b"mc-email-2fa-dev-key-change-in-secrets"
    return raw.encode("utf-8")[:128]


def _digest(code: str, login_key: str, exp: float) -> str:
    msg = f"{login_key}|{exp}|{code.strip()}"
    return hmac.new(_hmac_key(), msg.encode("utf-8"), hashlib.sha256).hexdigest()


def usuario_email_2fa_valido(user_dict: dict) -> bool:
    e = str(user_dict.get("email") or "").strip()
    return email_formato_aceptable(e)


def requiere_2fa_correo(user_dict: dict) -> bool:
    return login_email_2fa_enabled() and smtp_config_ok() and usuario_email_2fa_valido(user_dict)


def limpiar_desafio_email_2fa() -> None:
    st.session_state.pop(SESSION_KEY, None)


def _mascarar_email(e: str) -> str:
    e = e.strip()
    if "@" not in e:
        return "***"
    a, b = e.split("@", 1)
    if len(a) <= 2:
        return f"**@{b}"
    return f"{a[0]}***{a[-1]}@{b}"


def _generar_codigo() -> str:
    return f"{secrets.randbelow(900000) + 100000:06d}"


def _cuerpo_html_codigo(codigo: str, linea_extra: str = "") -> str:
    c = html_lib.escape(codigo.strip())
    extra = html_lib.escape(linea_extra) if linea_extra else ""
    bloque_extra = f"<p style='color:#444'>{extra}</p>" if extra else ""
    return (
        "<!DOCTYPE html><html><body style='font-family:system-ui,Segoe UI,sans-serif;background:#f8fafc;padding:24px'>"
        "<div style='max-width:480px;margin:0 auto;background:#fff;padding:28px;border-radius:12px;"
        "box-shadow:0 4px 24px rgba(0,0,0,.08)'>"
        "<p style='margin:0 0 12px;color:#334155'>Código de verificación <strong>MediCare</strong></p>"
        f"<p style='font-size:30px;letter-spacing:10px;font-weight:700;color:#0f172a;margin:16px 0'>{c}</p>"
        f"<p style='color:#64748b;font-size:14px'>Vence en {CODE_TTL_SEC // 60} minutos. "
        "Si no intentaste ingresar, ignorá este mensaje.</p>"
        f"{bloque_extra}</div></body></html>"
    )


def enviar_correo_smtp(destino: str, asunto: str, cuerpo_texto: str, cuerpo_html: str | None = None) -> tuple[bool, str]:
    """Envío genérico por SMTP (2FA, recuperación de contraseña, avisos)."""
    return _enviar_correo(destino, asunto, cuerpo_texto, cuerpo_html)


def _enviar_correo(destino: str, asunto: str, cuerpo_texto: str, cuerpo_html: str | None = None) -> tuple[bool, str]:
    host, port, user, pwd, from_addr, use_tls = _smtp_settings()
    context = ssl.create_default_context()
    try:
        msg = EmailMessage()
        msg["Subject"] = asunto
        msg["From"] = from_addr
        msg["To"] = destino.strip()
        msg.set_content(cuerpo_texto)
        if cuerpo_html:
            msg.add_alternative(cuerpo_html, subtype="html")

        if port == 465:
            with smtplib.SMTP_SSL(host, port, context=context, timeout=45) as server:
                if user:
                    server.login(user, pwd)
                server.send_message(msg)
        else:
            with smtplib.SMTP(host, port, timeout=45) as server:
                if use_tls:
                    server.starttls(context=context)
                if user:
                    server.login(user, pwd)
                server.send_message(msg)
        return True, ""
    except Exception as e:
        log_event("auth", f"email_2fa_smtp_error:{type(e).__name__}")
        return False, f"No se pudo enviar el correo ({type(e).__name__}). Revisá la configuración SMTP."


def iniciar_desafio_login(destino_email: str, usuario_key: str, u_limpio: str) -> tuple[bool, str]:
    now = time.time()
    codigo = _generar_codigo()
    exp = now + CODE_TTL_SEC
    d = _digest(codigo, u_limpio, exp)
    txt = (
        f"Tu código de verificación es: {codigo}\n\n"
        f"Vence en {CODE_TTL_SEC // 60} minutos.\n"
        "Si no intentaste ingresar al sistema, ignorá este mensaje."
    )
    ok, err = enviar_correo_smtp(
        destino_email.strip(),
        "Código de acceso — MediCare",
        txt,
        _cuerpo_html_codigo(codigo),
    )
    if not ok:
        return False, err
    st.session_state[SESSION_KEY] = {
        "digest": d,
        "expires": exp,
        "usuario_key": usuario_key,
        "u_limpio": u_limpio,
        "last_send": now,
        "tries": 0,
        "destino_mascarado": _mascarar_email(destino_email),
    }
    log_event("auth", "email_2fa_codigo_enviado")
    return True, ""


def reenviar_codigo_login() -> tuple[bool, str]:
    p = st.session_state.get(SESSION_KEY)
    if not p:
        return False, "No hay verificación pendiente."
    now = time.time()
    if now > float(p.get("expires") or 0):
        limpiar_desafio_email_2fa()
        return False, "El código venció. Volvé a iniciar sesión."
    ls = float(p.get("last_send") or 0)
    if now - ls < RESEND_COOLDOWN_SEC:
        return False, f"Esperá {int(RESEND_COOLDOWN_SEC - (now - ls))} s para reenviar."
    uk = p.get("usuario_key")
    ud = st.session_state.get("usuarios_db", {}).get(uk) or {}
    em = str(ud.get("email") or "").strip()
    if not em:
        return False, "Usuario sin email."
    codigo = _generar_codigo()
    exp = now + CODE_TTL_SEC
    d = _digest(codigo, str(p.get("u_limpio") or ""), exp)
    txt_r = f"Tu nuevo código: {codigo}\n\nVence en {CODE_TTL_SEC // 60} minutos."
    ok, err = enviar_correo_smtp(
        em,
        "Código de acceso — MediCare",
        txt_r,
        _cuerpo_html_codigo(codigo, "Este reemplaza al código anterior."),
    )
    if not ok:
        return False, err
    p["digest"] = d
    p["expires"] = exp
    p["last_send"] = now
    p["tries"] = 0
    st.session_state[SESSION_KEY] = p
    log_event("auth", "email_2fa_reenvio")
    return True, ""


def verificar_codigo_ingresado(codigo_ingresado: str) -> tuple[bool, str]:
    p = st.session_state.get(SESSION_KEY)
    if not p:
        return False, "No hay verificación pendiente."
    now = time.time()
    if now > float(p.get("expires") or 0):
        limpiar_desafio_email_2fa()
        return False, "El código venció. Iniciá sesión de nuevo."
    tries = int(p.get("tries") or 0)
    if tries >= MAX_CODE_TRIES:
        limpiar_desafio_email_2fa()
        return False, "Demasiados intentos fallidos. Iniciá sesión de nuevo."
    dig = str(p.get("digest") or "")
    u_limpio = str(p.get("u_limpio") or "")
    exp = float(p.get("expires") or 0)
    c = (codigo_ingresado or "").strip()
    ok = bool(c.isdigit() and len(c) == 6 and secrets.compare_digest(dig, _digest(c, u_limpio, exp)))
    if not ok:
        p["tries"] = tries + 1
        st.session_state[SESSION_KEY] = p
        log_event("auth", "email_2fa_codigo_incorrecto")
        return False, "Código incorrecto."
    log_event("auth", "email_2fa_ok")
    return True, ""


def desafio_email_2fa_activo() -> bool:
    p = st.session_state.get(SESSION_KEY)
    if not p:
        return False
    return time.time() <= float(p.get("expires") or 0)


def texto_ayuda_email_2fa_config() -> str | None:
    if not login_email_2fa_enabled():
        return None
    if not smtp_config_ok():
        return (
            "**2FA por correo** está activado en configuración pero faltan datos SMTP "
            "(HOST, PASSWORD, FROM). Hasta completarlos el ingreso sigue solo con contraseña."
        )
    return (
        "**Verificación en dos pasos** por correo: si tu usuario tiene **email** cargado en Mi equipo, "
        "tras la contraseña te pediremos un código de 6 dígitos. "
        "Sin email en ficha, el ingreso sigue solo con contraseña hasta que coordinación cargue el correo."
    )
