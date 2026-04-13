"""
Plantilla HTML unificada para correos transaccionales (2FA, recuperación de clave, etc.).
Estilo oscuro institucional alineado con la landing MediCare.
"""

from __future__ import annotations

import html as html_lib


def escape(s: str) -> str:
    return html_lib.escape(s.strip() if isinstance(s, str) else str(s or ""), quote=True)


def medicare_email_document(
    *,
    page_title: str,
    preheader_plain: str,
    heading_plain: str,
    alert_plain: str | None,
    body_inner_html: str,
) -> str:
    """
    Documento HTML completo. `body_inner_html` va dentro de la celda principal (sin el pie estándar).
    El pie legal se añade aquí para mantener una sola fuente de verdad.
    """
    pt = escape(page_title)
    pre = escape(preheader_plain)
    h1 = escape(heading_plain)

    alert_row = ""
    if alert_plain and str(alert_plain).strip():
        ap = escape(alert_plain)
        alert_row = (
            '<tr><td style="padding:6px 28px 10px">'
            '<p style="margin:0;padding:10px 14px;background:rgba(20,184,166,0.08);border-radius:10px;'
            'border:1px solid rgba(45,212,191,0.15);font-size:12px;color:#99f6e4;line-height:1.5">'
            f"{ap}</p></td></tr>"
        )

    footer = (
        '<p style="margin:22px 0 0;padding-top:18px;border-top:1px solid rgba(148,163,184,0.1);'
        'font-size:11px;color:#64748b;line-height:1.55">'
        "Correo automático de seguridad · No respondas a esta dirección.<br>"
        "Ante dudas: coordinación de tu institución o soporte MediCare."
        "</p>"
    )

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="color-scheme" content="dark">
  <title>{pt}</title>
</head>
<body style="margin:0;background:#0f172a;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:#e2e8f0;">
  <div style="display:none;max-height:0;overflow:hidden;mso-hide:all">{pre}</div>
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" style="background:#0f172a;padding:36px 16px">
    <tr><td align="center">
      <table role="presentation" width="100%" style="max-width:540px;background:linear-gradient(165deg,#1e293b 0%,#0f172a 55%,#020617 100%);
        border-radius:22px;border:1px solid rgba(148,163,184,0.14);box-shadow:0 28px 64px rgba(0,0,0,0.4),inset 0 1px 0 rgba(255,255,255,0.04)">
        <tr><td style="padding:26px 28px 6px">
          <p style="margin:0 0 4px;font-size:10px;font-weight:800;letter-spacing:0.22em;text-transform:uppercase;color:#2dd4bf">
            MediCare · Seguridad</p>
          <p style="margin:0;font-size:11px;color:#64748b">Enterprise PRO</p>
          <h1 style="margin:14px 0 0;font-size:23px;font-weight:800;color:#f8fafc;letter-spacing:-0.025em;line-height:1.2">
            {h1}</h1>
        </td></tr>
        {alert_row}
        <tr><td style="padding:8px 28px 22px">
          {body_inner_html}
          {footer}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def html_password_reset_body(
    nombre: str,
    url_reset: str,
    token: str,
    minutos: int,
) -> str:
    """Fragmento interno para recuperación de contraseña (sin documento envolvente)."""
    nombre_e = escape(nombre or "usuario")
    token_e = escape(token)
    min_e = escape(str(minutos))
    url_e = escape(url_reset) if url_reset else ""

    boton = ""
    if url_reset:
        boton = (
            f'<a href="{url_e}" style="display:inline-block;margin:22px 0 8px;padding:15px 32px;'
            "border-radius:14px;font-weight:800;font-size:15px;text-decoration:none;color:#ffffff;"
            "background:linear-gradient(135deg,#0d9488 0%,#2563eb 55%,#0891b2 100%);"
            'box-shadow:0 12px 32px rgba(37,99,235,0.3),inset 0 1px 0 rgba(255,255,255,0.12)">'
            "Restablecer contraseña →</a>"
        )
    else:
        boton = (
            "<p style='margin:18px 0 6px;font-size:14px;color:#94a3b8;text-align:center'>"
            "Abrí la aplicación MediCare en el navegador, elegí <strong style='color:#e2e8f0'>Olvidé mi contraseña</strong> "
            "y pegá el token de abajo.</p>"
        )

    bloque_token = (
        f"<p style='margin:18px 0 8px;color:#64748b;font-size:13px;font-weight:600'>"
        "Token (pegar en la app, paso 2)</p>"
        f"<pre style='margin:0;padding:16px 18px;background:#020617;color:#5eead4;border-radius:12px;"
        f"font-size:11px;line-height:1.45;word-break:break-all;overflow-x:auto;"
        f"border:1px solid rgba(45,212,191,0.28);font-family:Consolas,Monaco,monospace'>"
        f"{token_e}</pre>"
    )

    pasos = (
        "<ol style='margin:12px 0 0;padding-left:20px;color:#94a3b8;font-size:13px;line-height:1.65'>"
        "<li style='margin-bottom:6px'>Hacé clic en el botón o copiá el token.</li>"
        "<li style='margin-bottom:6px'>En la pantalla de acceso, abrí <strong style='color:#cbd5e1'>Olvidé mi contraseña</strong>.</li>"
        "<li>Elegí una contraseña nueva y guardá.</li>"
        "</ol>"
    )

    return (
        f"<p style='margin:0 0 14px;font-size:15px;line-height:1.65;color:#cbd5e1'>"
        f"Hola <strong style='color:#f8fafc'>{nombre_e}</strong>, recibimos una solicitud para definir una "
        f"<strong style='color:#e2e8f0'>nueva contraseña</strong>. Tu clave actual <strong>no cambia</strong> "
        f"hasta que completes el proceso en la app.</p>"
        f"<p style='margin:0 0 4px;font-size:13px;color:#94a3b8'>El enlace y el token vencen en "
        f"<strong style='color:#e2e8f0'>{min_e} minutos</strong>.</p>"
        f"<div style='text-align:center'>{boton}</div>"
        f"{bloque_token}{pasos}"
    )


def build_email_2fa_html(codigo: str, ttl_minutes: int, linea_extra: str = "") -> str:
    """Documento HTML completo para el correo de código 2FA al iniciar sesión."""
    return medicare_email_document(
        page_title="Código de acceso MediCare",
        preheader_plain=f"Tu código MediCare es {codigo}. Vence en {ttl_minutes} minutos.",
        heading_plain="Verificación en dos pasos",
        alert_plain=(
            "No compartas este código. Nadie de MediCare ni de tu institución debería pedírtelo por teléfono, "
            "WhatsApp u otro canal."
        ),
        body_inner_html=html_2fa_code_body(codigo, ttl_minutes, linea_extra),
    )


def html_2fa_code_body(codigo: str, ttl_minutes: int, linea_extra: str = "") -> str:
    """Fragmento interno para correo de código 2FA."""
    c = escape(codigo)
    mins = escape(str(ttl_minutes))
    extra = ""
    if (linea_extra or "").strip():
        extra = (
            f"<p style='margin:14px 0 0;padding:12px 14px;background:rgba(59,130,246,0.08);border-radius:10px;"
            f"border:1px solid rgba(96,165,250,0.2);font-size:13px;color:#bfdbfe;line-height:1.5'>"
            f"{escape(linea_extra)}</p>"
        )

    return (
        "<p style='margin:0 0 14px;font-size:15px;line-height:1.65;color:#cbd5e1'>"
        "Ingresaste correctamente tu contraseña. Para completar el acceso a "
        "<strong style='color:#f8fafc'>MediCare Enterprise PRO</strong>, usá este código de verificación:</p>"
        f"<div style='margin:18px 0 20px;text-align:center'>"
        f"<span style='display:inline-block;font-size:32px;letter-spacing:14px;font-weight:800;color:#5eead4;"
        f"font-family:Consolas,Monaco,ui-monospace,monospace;padding:20px 24px;background:#020617;"
        f"border-radius:14px;border:1px solid rgba(45,212,191,0.35);"
        f"box-shadow:0 0 32px rgba(45,212,191,0.12)'>{c}</span></div>"
        f"<p style='margin:0 0 8px;font-size:14px;color:#94a3b8'>Vence en "
        f"<strong style='color:#e2e8f0'>{mins} minutos</strong>. "
        "Si no intentaste ingresar, ignorá este mensaje: la cuenta sigue protegida con tu contraseña.</p>"
        f"{extra}"
        "<ol style='margin:16px 0 0;padding-left:20px;color:#94a3b8;font-size:13px;line-height:1.65'>"
        "<li style='margin-bottom:6px'>Volvé a la ventana del navegador donde está MediCare.</li>"
        "<li>Ingresá el código de 6 dígitos cuando la app lo solicite.</li>"
        "</ol>"
    )


def html_password_changed_body(nombre: str, url_app: str) -> str:
    """Fragmento para correo de confirmación tras cambio de contraseña."""
    nombre_e = escape(nombre or "usuario")
    url_e = escape(url_app) if url_app else ""

    if url_app:
        boton = (
            f'<a href="{url_e}" style="display:inline-block;margin:22px 0 8px;padding:15px 32px;'
            "border-radius:14px;font-weight:800;font-size:15px;text-decoration:none;color:#ffffff;"
            "background:linear-gradient(135deg,#2563eb 0%,#0891b2 55%,#0d9488 100%);"
            'box-shadow:0 12px 32px rgba(8,145,178,0.28),inset 0 1px 0 rgba(255,255,255,0.12)">'
            "Ingresar a MediCare →</a>"
        )
    else:
        boton = (
            "<p style='margin:18px 0 6px;font-size:14px;color:#94a3b8;text-align:center'>"
            "Volvé a la pantalla de acceso de MediCare e ingresá con tu <strong style='color:#e2e8f0'>nueva contraseña</strong>.</p>"
        )

    return (
        f"<p style='margin:0 0 14px;font-size:15px;line-height:1.65;color:#cbd5e1'>"
        f"Hola <strong style='color:#f8fafc'>{nombre_e}</strong>, te confirmamos que la "
        f"<strong style='color:#e2e8f0'>contraseña de tu cuenta se actualizó correctamente</strong>.</p>"
        f"<p style='margin:0 0 14px;font-size:13px;color:#94a3b8'>"
        "Desde ahora debés usar la clave nueva para ingresar.</p>"
        f"<div style='text-align:center'>{boton}</div>"
        "<p style='margin:16px 0 0;font-size:12px;color:#64748b;line-height:1.5'>"
        "Si no fuiste vos, avisá de inmediato a coordinación o soporte para revisar el acceso.</p>"
    )
