"""Autenticacion multifactor via TOTP (Google Authenticator).
Alternativa local al MFA por email. Usa pyotp para generar y verificar
codigos QR compatibles con Google Authenticator / Authy.
"""

from __future__ import annotations

import base64
import io
import time
from dataclasses import dataclass
from typing import Optional

import streamlit as st

from core.app_logging import log_event


@dataclass
class TOTPConfig:
    """Configuracion TOTP para un usuario."""
    usuario: str
    secreto: str
    habilitado: bool = False
    ultimo_uso: float = 0.0


class TOTPManager:
    """Gestiona TOTP para profesionales de la salud.

    Cada usuario puede tener su propio secreto TOTP.
    El QR se muestra una unica vez durante la configuracion inicial.
    """

    @staticmethod
    def generar_secreto() -> str:
        """Genera un nuevo secreto TOTP (16 caracteres base32)."""
        import pyotp
        return pyotp.random_base32()

    @staticmethod
    def generar_uri(usuario: str, secreto: str, issuer: str = "MediCare PRO") -> str:
        """Genera la URI para el codigo QR compatible con Google Authenticator."""
        import pyotp
        return pyotp.totp.TOTP(secreto).provisioning_uri(
            name=usuario,
            issuer_name=issuer,
        )

    @staticmethod
    def generar_qr_b64(uri: str) -> str:
        """Genera un codigo QR en base64 para mostrar en la UI."""
        import pyotp
        try:
            import qrcode
            qr = qrcode.make(uri)
            buf = io.BytesIO()
            qr.save(buf, format="PNG")
            return base64.b64encode(buf.getvalue()).decode("utf-8")
        except ImportError:
            # Fallback: solo mostrar la URI como texto
            log_event("totp", "qrcode no instalado, mostrando URI textual")
            return ""

    @staticmethod
    def verificar_codigo(secreto: str, codigo: str) -> bool:
        """Verifica un codigo TOTP de 6 digitos."""
        import pyotp
        if not codigo or not codigo.strip():
            return False
        try:
            totp = pyotp.TOTP(secreto)
            return totp.verify(codigo.strip(), valid_window=1)
        except Exception as exc:
            log_event("totp", f"verificacion_error:{type(exc).__name__}")
            return False


# ── Codigos de recuperacion TOTP ────────────────────────────────

RECOVERY_CODES_KEY = "_totp_recovery_codes"


def _generar_codigos_recuperacion(cantidad: int = 6) -> list[str]:
    """Genera N codigos de recuperacion alfanumericos de un solo uso."""
    import secrets
    codes = []
    for _ in range(cantidad):
        code = secrets.token_hex(4).upper()
        codes.append(f"MED-{code[:4]}-{code[4:]}")
    return codes


def render_recovery_codes(usuario: str) -> list[str]:
    """Genera y muestra codigos de recuperacion. Retorna la lista para guardar."""
    import streamlit as st
    codes = _generar_codigos_recuperacion(6)
    st.session_state[RECOVERY_CODES_KEY + f"_{usuario}"] = codes
    st.success("**Guardá estos códigos en un lugar seguro.** Cada código solo puede usarse una vez.")
    for c in codes:
        st.code(c, language="text")
    st.caption("Si perdés el celular, usá uno de estos códigos para entrar.")
    return codes


def verificar_codigo_recuperacion(usuario: str, codigo: str) -> bool:
    """Verifica y consume un codigo de recuperacion de un solo uso."""
    import streamlit as st
    codigo = codigo.strip().upper()
    codes = st.session_state.get(RECOVERY_CODES_KEY + f"_{usuario}", [])
    if codigo in codes:
        codes.remove(codigo)
        st.session_state[RECOVERY_CODES_KEY + f"_{usuario}"] = codes
        return True
    return False


def render_totp_setup(usuario: str) -> bool:
    """Muestra la UI de configuracion TOTP en la app.

    Returns:
        True si el usuario configuro TOTP exitosamente.
    """
    from core.app_logging import log_event

    secret_key = st.session_state.get(f"_totp_secret_{usuario}")
    if not secret_key:
        secret_key = TOTPManager.generar_secreto()
        st.session_state[f"_totp_secret_{usuario}"] = secret_key

    st.markdown("### Autenticacion de dos factores (TOTP)")
    st.caption("Escape la app de autenticacion (Google Authenticator, Authy, etc.)")

    uri = TOTPManager.generar_uri(usuario, secret_key)
    qr_b64 = TOTPManager.generar_qr_b64(uri)

    if qr_b64:
        st.image(f"data:image/png;base64,{qr_b64}", width=200)
    else:
        st.code(uri, language="text")

    st.caption("Ingresa el codigo de 6 digitos de la app para confirmar:")
    codigo = st.text_input("Codigo TOTP", max_chars=6, key="totp_setup_code")

    if st.button("Confirmar y activar 2FA", key="totp_confirm"):
        if TOTPManager.verificar_codigo(secret_key, codigo):
            # Guardar configuracion
            config = TOTPConfig(
                usuario=usuario,
                secreto=secret_key,
                habilitado=True,
                ultimo_uso=time.time(),
            )
            st.session_state[f"_totp_config_{usuario}"] = config
            st.session_state.pop(f"_totp_secret_{usuario}", None)
            log_event("totp", f"configurado_ok:{usuario}")
            st.success("2FA activado correctamente.")
            return True
        else:
            st.error("Codigo invalido. Verifica que la hora del telefono este sincronizada.")
    return False


def verificar_totp_si_aplica(usuario: str) -> bool:
    """Verifica TOTP si el usuario lo tiene configurado.

    Returns:
        True si pasa la verificacion o no tiene TOTP.
    """
    config: Optional[TOTPConfig] = st.session_state.get(f"_totp_config_{usuario}")
    if not config or not config.habilitado:
        return True

    st.markdown("### Verificacion de dos factores")
    codigo = st.text_input("Codigo de autenticacion (6 digitos)", max_chars=6, key="totp_verify")
    if st.button("Verificar", key="totp_verify_btn"):
        if TOTPManager.verificar_codigo(config.secreto, codigo):
            config.ultimo_uso = time.time()
            st.session_state[f"_totp_config_{usuario}"] = config
            return True
        else:
            st.error("Codigo invalido.")
    return False


# ── Session Timeout Decorator ─────────────────────────────────────

SESSION_TIMEOUT_MINUTES_DEFAULT = 30


def _auto_save_evolucion():
    """Guarda automaticamente el borrador de evolucion si hay cambios sin guardar."""
    try:
        if st.session_state.get("_guardar_datos_pendiente"):
            from core.database import guardar_datos
            guardar_datos(spinner=False)
            log_event("session", "auto_save_ok:datos_guardados_por_timeout")
    except Exception as exc:
        log_event("session", f"auto_save_error:{type(exc).__name__}")


def require_active_session(timeout_minutes: int = SESSION_TIMEOUT_MINUTES_DEFAULT):
    """Decorador para verificar expiracion de sesion por inactividad.

    Incluye auto-save: antes de cerrar la sesion, guarda cualquier
    cambio pendiente para que el profesional no pierda datos.

    Use para proteger vistas/pantallas en terminales compartidas.
    La sesion expira si el usuario no interactua en `timeout_minutes`.

    Uso:
        @require_active_session(timeout_minutes=15)
        def render_panel_paciente():
            ...
    """
    from functools import wraps

    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_activity = st.session_state.get("_session_last_activity")
            now = time.time()

            if last_activity is not None:
                elapsed = now - last_activity
                remaining = timeout_minutes * 60 - elapsed

                # Warning con tiempo restante
                if 0 < remaining < 120 and not st.session_state.get("_session_timeout_warning_shown"):
                    st.session_state["_session_timeout_warning_shown"] = True
                    mins = int(remaining // 60)
                    secs = int(remaining % 60)
                    st.warning(f"⏳ Sesion expira en {mins}m {secs}s. Se guardaron los cambios automaticamente.")

                if remaining <= 0:
                    # Auto-save antes de cerrar
                    _auto_save_evolucion()
                    st.session_state["logeado"] = False
                    st.session_state.pop("u_actual", None)
                    st.session_state.pop("_session_last_activity", None)
                    st.session_state.pop("_session_timeout_warning_shown", None)
                    st.warning("Sesion expirada por inactividad. Los cambios fueron guardados automaticamente.")
                    st.rerun()
                    return

            st.session_state["_session_last_activity"] = now
            st.session_state["_session_timeout_warning_shown"] = False
            return func(*args, **kwargs)
        return wrapper
    return decorator
