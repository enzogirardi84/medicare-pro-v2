"""Gestión de session_state: login, logout, limpieza segura.

Nunca borra datos clínicos a menos que sea logout explícito.
"""

import streamlit as st


# Claves de autenticación / navegación que se limpian en logout.
_SESION_LOGIN_KEYS = [
    "logeado",
    "u_actual",
    "ultima_actividad",
    "modulo_actual",
    "modulo_anterior",
    "paciente_actual",
    "entered_app",
]

# Claves efímeras de UI / cache que se limpian en logout.
_SESION_UI_KEYS = [
    "_mc_onboarding_oculto",
    "_db_monolito_sesion",
    "_mc_aviso_payload_grande",
    "mc_nav_filtro_cat",
    "_mc_sidebar_logo_b64",
    "_mc_anticolapso_secret_cached",
    "_mc_professional_theme_applied",
    "_mc_login_transition",
    "_mc_cache_headers_liviano",
    "_mc_cache_ua_contexto",
    "_mc_seo_head_inyectado",
]


def limpiar_sesion_app() -> None:
    """Logout seguro: limpia autenticación y UI, NO toca datos clínicos."""
    from core.database import vaciar_datos_app_en_sesion
    from core.session_auth_cleanup import limpiar_estado_sesion_login_efimero

    for clave in _SESION_LOGIN_KEYS:
        st.session_state.pop(clave, None)

    limpiar_estado_sesion_login_efimero()

    # No llamamos a vaciar_datos_app_en_sesion() salvo que sea necesario;
    # logout limpia solo auth para que el próximo login recargue fresco.
    # Si el usuario pide "Abrir" (reset total), sí se vacían datos clínicos.
    # Eso se maneja en la función de reset_total_app().

    for clave in _SESION_UI_KEYS:
        st.session_state.pop(clave, None)

    st.session_state["entered_app"] = False


def reset_total_app() -> None:
    """Reset completo (botón Abrir): limpia TODO incluyendo datos clínicos en sesión."""
    from core.database import vaciar_datos_app_en_sesion
    from core.session_auth_cleanup import limpiar_estado_sesion_login_efimero

    for clave in _SESION_LOGIN_KEYS:
        st.session_state.pop(clave, None)

    limpiar_estado_sesion_login_efimero()
    vaciar_datos_app_en_sesion()

    for clave in _SESION_UI_KEYS:
        st.session_state.pop(clave, None)

    st.session_state["entered_app"] = False
    st.session_state["logeado"] = False


def inicializar_db_state_seguro() -> None:
    """Bootstrap inicial de la base de datos en sesión (solo una vez)."""
    from core.utils import inicializar_db_state

    if "_db_bootstrapped" not in st.session_state:
        inicializar_db_state(None, precargar_usuario_admin_emergencia=False)
        st.session_state["_db_bootstrapped"] = True


def eliminar_overlay_residual() -> None:
    """Limpia flags de transición que pueden quedar colgados."""
    st.session_state.pop("_mc_login_transition", None)
