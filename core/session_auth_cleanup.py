"""Limpia claves de sesión ligadas a login / 2FA / lockout (al cerrar sesión o expulsar)."""

from __future__ import annotations

import streamlit as st

from core.email_2fa import SESSION_KEY as EMAIL_2FA_SESSION_KEY


def limpiar_estado_sesion_login_efimero() -> None:
    for k in (
        EMAIL_2FA_SESSION_KEY,
        "_mc_2fa_resend_toast",
        "_mc_login_protect",
        "_login_clinica_rechazo_guardado_once",
        "_debounce_guardar_logs_clinica_ts",
    ):
        st.session_state.pop(k, None)
