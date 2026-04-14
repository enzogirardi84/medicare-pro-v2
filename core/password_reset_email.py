"""
Recuperación de contraseña por correo (SMTP), con token firmado (sin estado en servidor).

Secrets (reutiliza los de 2FA si existen):
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_USE_TLS (igual que email_2fa)
- PASSWORD_RESET_HMAC_SECRET (recomendado) o EMAIL_2FA_HMAC_SECRET o SMTP_PASSWORD
- APP_PUBLIC_URL = URL pública de la app (ej. https://tu-app.streamlit.app) para el botón del correo.
  Sin esto, el correo igual llega con el token para copiar y pegar en la app.
- SMTP_REPLY_TO (opcional, ver email_2fa): respuesta a soporte en correos transaccionales.

Opcional: PASSWORD_RESET_TTL_MINUTES (default 60).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import parse_qs, quote, unquote, urlparse

import streamlit as st

from core.app_logging import log_event
from core.email_2fa import enviar_correo_smtp, smtp_config_ok
from core.email_templates_medicare import (
    html_password_changed_body,
    html_password_reset_body,
    medicare_email_document,
)
from core.input_validation import email_formato_aceptable


def password_reset_ttl_seconds() -> int:
    try:
        m = int(st.secrets.get("PASSWORD_RESET_TTL_MINUTES", 60))
    except Exception:
        m = 60
    m = max(15, min(m, 24 * 60))
    return m * 60


def _hmac_key() -> bytes:
    try:
        raw = (
            st.secrets.get("PASSWORD_RESET_HMAC_SECRET", "")
            or st.secrets.get("EMAIL_2FA_HMAC_SECRET", "")
            or st.secrets.get("SMTP_PASSWORD", "")
        )
    except Exception:
        raw = ""
    raw = str(raw).strip()
    if len(raw) < 16:
        return b"mc-password-reset-dev-key-change-in-secrets"
    return raw.encode("utf-8")[:128]


def _app_public_url() -> str:
    try:
        u = str(st.secrets.get("APP_PUBLIC_URL", "") or "").strip().rstrip("/")
    except Exception:
        u = ""
    if not u:
        return ""
    try:
        p = urlparse(u)
        if p.scheme not in ("http", "https") or not p.netloc:
            return ""
    except Exception:
        return ""
    return u


def crear_token_restablecimiento(usuario_key: str, u_limpio: str, empresa: str) -> tuple[str, float]:
    """Devuelve (token_url_safe, exp_epoch)."""
    exp = time.time() + password_reset_ttl_seconds()
    nonce = secrets.token_hex(16)
    payload_obj = {
        "v": 1,
        "uk": str(usuario_key),
        "ul": str(u_limpio).strip().lower(),
        "em": str(empresa or "").strip(),
        "exp": exp,
        "n": nonce,
    }
    payload_str = json.dumps(payload_obj, separators=(",", ":"), sort_keys=True)
    sig = hmac.new(_hmac_key(), payload_str.encode("utf-8"), hashlib.sha256).hexdigest()
    bundle = json.dumps({"p": payload_str, "s": sig}, separators=(",", ":"))
    token = base64.urlsafe_b64encode(bundle.encode("utf-8")).decode("ascii").rstrip("=")
    return token, exp


def verificar_token_restablecimiento(token: str) -> tuple[bool, str, dict | None]:
    """
    Valida firma y vencimiento. Devuelve (ok, mensaje_error, info).
    info = {uk, u_limpio, empresa} para cargar la base correcta.
    """
    raw_t = (token or "").strip().replace("\n", "").replace("\r", "")
    if not raw_t:
        return False, "Falta el token de recuperación.", None
    pad = "=" * ((4 - len(raw_t) % 4) % 4)
    try:
        decoded = base64.urlsafe_b64decode(raw_t + pad)
        bundle = json.loads(decoded.decode("utf-8"))
        payload_str = bundle["p"]
        sig = bundle["s"]
    except Exception:
        return False, "El enlace o token no es válido o está incompleto.", None
    exp_sig = hmac.new(_hmac_key(), payload_str.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(exp_sig, str(sig)):
        return False, "El token de recuperación no es válido.", None
    try:
        pl = json.loads(payload_str)
        uk = str(pl["uk"])
        u_limpio = str(pl["ul"]).strip().lower()
        empresa = str(pl.get("em", "")).strip()
        exp = float(pl["exp"])
    except Exception:
        return False, "El token de recuperación no es válido.", None
    if time.time() > exp:
        return False, "Este enlace venció. Pedí asistencia a coordinación o un token nuevo.", None
    return True, "", {"uk": uk, "u_limpio": u_limpio, "empresa": empresa}


def construir_url_restablecimiento(token: str) -> str:
    base = _app_public_url()
    if not base:
        return ""
    enc = quote(token, safe="")
    return f"{base}/?pwreset={enc}"


def extraer_token_restablecimiento_desde_texto(texto: str) -> str:
    raw = str(texto or "").strip()
    if not raw:
        return ""

    candidato = raw
    try:
        parsed = urlparse(raw)
        query_token = parse_qs(parsed.query or "").get("pwreset", [])
        if query_token:
            candidato = query_token[0]
        elif "pwreset=" in raw:
            candidato = raw.split("pwreset=", 1)[-1].split("&", 1)[0].split("#", 1)[0]
    except Exception:
        candidato = raw

    try:
        candidato = unquote(str(candidato or "").strip())
    except Exception:
        candidato = str(candidato or "").strip()
    return candidato.replace("\n", "").replace("\r", "").strip()


def _html_correo_profesional(nombre: str, url_reset: str, token: str, minutos: int) -> str:
    mins_s = str(minutos)
    return medicare_email_document(
        page_title="Recuperación MediCare",
        preheader_plain=f"MediCare: restablecer contraseña y PIN opcional (vence en {mins_s} min).",
        heading_plain="Recuperación de acceso",
        alert_plain="Mensaje confidencial. Si no solicitaste un cambio de clave, ignorá este correo.",
        body_inner_html=html_password_reset_body(nombre, url_reset, token, minutos),
    )


def _html_confirmacion_password_profesional(
    nombre: str, url_app: str, *, pin_actualizado: bool = False
) -> str:
    pre = (
        "MediCare: tu contraseña y PIN se actualizaron correctamente."
        if pin_actualizado
        else "MediCare: tu contraseña se actualizó correctamente."
    )
    head = "Acceso actualizado" if pin_actualizado else "Contraseña actualizada"
    return medicare_email_document(
        page_title="Contraseña actualizada — MediCare",
        preheader_plain=pre,
        heading_plain=head,
        alert_plain="Aviso de seguridad. Si no reconocés este cambio, contactá de inmediato a coordinación o soporte.",
        body_inner_html=html_password_changed_body(nombre, url_app, pin_actualizado=pin_actualizado),
    )


def enviar_correo_restablecimiento(destino: str, nombre_usuario: str, token: str) -> tuple[bool, str]:
    if not smtp_config_ok():
        return False, "Falta configuración SMTP (HOST, PASSWORD, FROM). El administrador debe completarla en los secretos."
    if not email_formato_aceptable(destino.strip()):
        return False, "Correo de destino inválido."

    url = construir_url_restablecimiento(token)
    mins = max(1, password_reset_ttl_seconds() // 60)
    txt_lines = [
        "MediCare Enterprise PRO — Recuperación de acceso",
        "",
        f"Hola {nombre_usuario or 'usuario'},",
        "",
        "Recibimos una solicitud para definir una nueva contraseña (y, si querés, un PIN de 4 dígitos en el mismo paso).",
        "Tu clave actual no cambia hasta completar el proceso en la app.",
        "Si no fuiste vos, ignorá este mensaje.",
        f"Enlace y token vencen en {mins} minutos.",
        "",
    ]
    if url:
        txt_lines.extend(["1) Abrí este enlace en el navegador:", url, ""])
    else:
        txt_lines.extend(
            [
                "1) Abrí la app MediCare en el navegador.",
                "2) Seguí las instrucciones de tu clínica (muchas asignan la clave desde coordinación).",
                "",
            ]
        )
    txt_lines.extend(
        [
            "Token (paso 2 en la app — definir nueva contraseña):",
            token,
            "",
            "— MediCare · mensaje automático, no responder",
        ]
    )
    cuerpo_txt = "\n".join(txt_lines)

    html = _html_correo_profesional(nombre_usuario, url, token, mins)
    ok, err = enviar_correo_smtp(
        destino.strip(),
        "Recuperá tu acceso — MediCare Enterprise PRO",
        cuerpo_txt,
        html,
    )
    if ok:
        log_event("auth", "password_reset_email_enviado")
    else:
        log_event("auth", f"password_reset_email_smtp_fallo:{err[:80] if err else ''}")
    return ok, err


def enviar_correo_confirmacion_cambio_password(
    destino: str, nombre_usuario: str, *, pin_actualizado: bool = False
) -> tuple[bool, str]:
    if not smtp_config_ok():
        return False, "Falta configuración SMTP."
    if not email_formato_aceptable(destino.strip()):
        return False, "Correo de destino inválido."

    url_app = _app_public_url()
    titulo_txt = (
        "MediCare Enterprise PRO — Contraseña y PIN actualizados"
        if pin_actualizado
        else "MediCare Enterprise PRO — Contraseña actualizada"
    )
    txt_lines = [
        titulo_txt,
        "",
        f"Hola {nombre_usuario or 'usuario'},",
        "",
        "Tu contraseña se actualizó correctamente.",
    ]
    if pin_actualizado:
        txt_lines.append("También quedó actualizado tu PIN de recuperación (4 dígitos). No lo compartas.")
    txt_lines.extend(
        [
            "A partir de ahora debés ingresar con la clave nueva.",
            "",
        ]
    )
    if url_app:
        txt_lines.append("Abrí MediCare desde este enlace:")
        txt_lines.append(url_app)
        txt_lines.append("")
    txt_lines.append("Si no reconocés este cambio, avisá de inmediato a coordinación o soporte.")
    txt_lines.append("")
    txt_lines.append("— MediCare · mensaje automático, no responder")
    cuerpo_txt = "\n".join(txt_lines)

    html = _html_confirmacion_password_profesional(nombre_usuario, url_app, pin_actualizado=pin_actualizado)
    asunto = (
        "Contraseña y PIN actualizados — MediCare Enterprise PRO"
        if pin_actualizado
        else "Tu contraseña fue actualizada — MediCare Enterprise PRO"
    )
    ok, err = enviar_correo_smtp(
        destino.strip(),
        asunto,
        cuerpo_txt,
        html,
    )
    if ok:
        log_event("auth", "password_reset_confirmacion_enviada")
    else:
        log_event("auth", f"password_reset_confirmacion_fallo:{err[:80] if err else ''}")
    return ok, err
