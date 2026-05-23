"""Orquestador de Configuracion del Sistema.
Importa componentes desde views/settings/components/.
"""

from __future__ import annotations

import streamlit as st

from core.app_logging import log_event
from core.database import guardar_datos
from views.settings.components._apariencia_notificaciones import (
    render_appearance_settings,
    render_notification_settings,
)
from views.settings.components._integraciones_api import (
    render_integration_settings,
)
from views.settings.components._seguridad_avanzada import (
    render_security_settings,
    render_advanced_settings,
    render_insumos_rules_settings,
)
from views.admin_usuarios import render_admin_usuarios


# Funciones helper exportadas para uso externo
def get_version() -> str:
    import importlib.metadata
    try:
        return importlib.metadata.version("medicare-pro")
    except importlib.metadata.PackageNotFoundError:
        return "2.0.0-dev"


def get_environment() -> str:
    import os
    return os.getenv("MEDICARE_ENV", "development")


def get_python_version() -> str:
    import sys
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_os_info() -> str:
    import platform
    return f"{platform.system()} {platform.release()}"


def render_settings_page():
    """Renderiza pagina completa de configuracion."""
    user = st.session_state.get("u_actual", {})
    is_admin = str(user.get("rol", "")).strip().lower() in {"admin", "superadmin"}

    st.title("⚙️ Configuracion")
    st.caption(f"Usuario: {user.get('nombre', 'N/A')}")

    _tabs_list = [
        "🎨 Apariencia",
        "🔔 Notificaciones",
        "🔗 Integraciones",
        "📦 Reglas de Insumos",
        "🔒 Seguridad",
        "⚡ Avanzado",
    ]
    if is_admin:
        _tabs_list.append("👥 Usuarios")

    tabs = st.tabs(_tabs_list)

    with tabs[0]:
        render_appearance_settings()
    with tabs[1]:
        render_notification_settings()
    with tabs[2]:
        render_integration_settings(is_admin)
    with tabs[3]:
        render_insumos_rules_settings(is_admin)
    with tabs[4]:
        render_security_settings(is_admin)
    with tabs[5]:
        render_advanced_settings(is_admin)
    if is_admin:
        with tabs[6]:
            render_admin_usuarios()
