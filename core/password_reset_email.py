"""
Recuperación de contraseña por correo (SMTP), con token firmado (sin estado en servidor).

Secrets (reutiliza los de 2FA si existen):
- SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_FROM, SMTP_USE_TLS (igual que email_2fa)
- PASSWORD_RESET_HMAC_SECRET (recomendado) o EMAIL_2FA_HMAC_SECRET o SMTP_PASSWORD
- APP_PUBLIC_URL = URL pública de la app (ej. https://tu-app.streamlit.app) para el botón del correo.
  Sin esto, el correo igual llega con el token para copiar y pegar en la app.

Opcional: PASSWORD_RESET_TTL_MINUTES (default 60).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import html as html_lib
import json
import secrets
import time
from urllib.parse import quote, urlparse

import streamlit as st

from core.app_logging import log_event
from core.email_2fa import enviar_correo_smtp, smtp_config_ok
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
        return False, "Este enlace venció. Volvé a pedir uno desde «Olvidé mi contraseña».", None
    return True, "", {"uk": uk, "u_limpio": u_limpio, "empresa": empresa}


def construir_url_restablecimiento(token: str) -> str:
    base = _app_public_url()
    if not base:
        return ""
    enc = quote(token, safe="")
    return f"{base}/?pwreset={enc}"


def _html_correo_profesional(nombre: str, url_reset: str, token: str, minutos: int) -> str:
    nombre_e = html_lib.escape(nombre.strip() or "usuario")
    token_e = html_lib.escape(token)
    url_e = html_lib.escape(url_reset) if url_reset else ""
    min_e = html_lib.escape(str(minutos))

    boton = ""
    if url_reset:
        boton = (
            f'<a href="{url_e}" style="display:inline-block;margin:20px 0;padding:14px 28px;'
            "border-radius:12px;font-weight:700;font-size:15px;text-decoration:none;color:#ffffff;"
            "background:linear-gradient(135deg,#0d9488 0%,#2563eb 100%);"
            'box-shadow:0 10px 28px rgba(37,99,235,0.25)">Restablecer contraseña</a>'
        )

    bloque_token = (
        f"<p style='margin:16px 0 8px;color:#64748b;font-size:14px'>"
        "Si el botón no funciona, copiá este token y pegalo en la app (Olvidé mi contraseña):</p>"
        f"<pre style='margin:0;padding:14px 16px;background:#0f172a;color:#5eead4;border-radius:10px;"
        f"font-size:12px;word-break:break-all;overflow-x:auto;border:1px solid rgba(94,234,212,0.25)'>"
        f"{token_e}</pre>"
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;background:#0f172a;font-family:'Segoe UI',system-ui,sans-serif;color:#e2e8f0;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#0f172a;padding:32px 16px">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:520px;background:linear-gradient(180deg,#1e293b 0%,#0f172a 100%);
        border-radius:20px;border:1px solid rgba(148,163,184,0.15);box-shadow:0 24px 60px rgba(0,0,0,0.35)">
        <tr><td style="padding:28px 28px 8px">
          <p style="margin:0;font-size:11px;font-weight:800;letter-spacing:0.2em;text-transform:uppercase;color:#2dd4bf">
            MediCare Enterprise PRO</p>
          <h1 style="margin:12px 0 0;font-size:22px;font-weight:800;color:#f8fafc;letter-spacing:-0.02em">
            Recuperación de acceso</h1>
        </td></tr>
        <tr><td style="padding:8px 28px 24px">
          <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#cbd5e1">
            Hola <strong style="color:#f1f5f9">{nombre_e}</strong>, recibimos una solicitud para definir una
            <strong>nueva contraseña</strong> en tu cuenta. Si no fuiste vos, ignorá este mensaje: tu clave actual no cambia.
          </p>
          <p style="margin:0 0 8px;font-size:14px;color:#94a3b8">El enlace vence en <strong>{min_e} minutos</strong>.</p>
          <div style="text-align:center">{boton}</div>
          {bloque_token}
          <p style="margin:24px 0 0;padding-top:20px;border-top:1px solid rgba(148,163,184,0.12);
            font-size:12px;color:#64748b;line-height:1.5">
            Mensaje automático de seguridad. No respondas a este correo.
            Ante dudas, contactá al coordinador de tu institución o a soporte MediCare.
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


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
        "Recibimos una solicitud para definir una nueva contraseña. Si no fuiste vos, ignorá este mensaje.",
        f"El enlace o token vence en {mins} minutos.",
        "",
    ]
    if url:
        txt_lines.append("Abrí este enlace en el navegador:")
        txt_lines.append(url)
        txt_lines.append("")
    txt_lines.append("Si el enlace no funciona, en la app elegí «Olvidé mi contraseña» y pegá este token:")
    txt_lines.append(token)
    txt_lines.append("")
    txt_lines.append("— Equipo MediCare (mensaje automático, no responder)")
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
