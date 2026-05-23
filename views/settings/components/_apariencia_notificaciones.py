"""Configuracion de apariencia y notificaciones."""

from __future__ import annotations

import streamlit as st

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType
from core.database import guardar_datos
from core.i18n import render_language_selector


def _guardar_config():
    guardar_datos(spinner=False, force=True)


def render_appearance_settings():
    st.header("🎨 Apariencia")
    _s = st.session_state.setdefault("settings_db", {})
    st.subheader("Idioma")
    render_language_selector()
    st.divider()

    st.subheader("Tema")
    _theme_opts = ["Claro", "Oscuro", "Auto"]
    _s_theme = _s.get("app_theme", "Claro")
    theme = st.radio("Tema de color", options=_theme_opts, index=_theme_opts.index(_s_theme) if _s_theme in _theme_opts else 0)
    if st.button("💾 Guardar Tema"):
        _s["app_theme"] = theme
        st.session_state["theme"] = theme.lower()
        _guardar_config()
        st.success(f"✅ Tema cambiado a {theme}")

    st.divider()
    st.subheader("Densidad de Interfaz")
    density = st.select_slider("Densidad", options=["Compacta", "Normal", "Espaciada"], value=_s.get("app_density", "Normal"))
    if st.button("💾 Guardar Densidad"):
        _s["app_density"] = density.lower()
        st.session_state["ui_density"] = density.lower()
        _guardar_config()
        st.success(f"✅ Densidad cambiada a {density}")

    st.divider()
    user = st.session_state.get("u_actual", {})
    if str(user.get("rol", "")).strip().lower() in {"admin", "superadmin"}:
        st.subheader("Personalizacion de Colores (Admin)")
        col1, col2 = st.columns(2)
        with col1:
            primary_color = st.color_picker("Color Primario", value=_s.get("app_primary_color", "#14b8a6"))
        with col2:
            secondary_color = st.color_picker("Color Secundario", value=_s.get("app_secondary_color", "#0f172a"))
        if st.button("💾 Guardar Colores"):
            _s["app_primary_color"] = primary_color
            _s["app_secondary_color"] = secondary_color
            st.session_state["primary_color"] = primary_color
            st.session_state["secondary_color"] = secondary_color
            _guardar_config()
            st.success("✅ Colores actualizados")
            audit_log(AuditEventType.CONFIG_CHANGE, resource_type="appearance", resource_id="colors", action="UPDATE", description=f"Colors updated")


def render_notification_settings():
    st.header("🔔 Notificaciones")
    _s = st.session_state.setdefault("settings_db", {})
    st.caption("Configura las notificaciones push y alertas del sistema.")
    push_enabled = st.toggle("Habilitar notificaciones push", value=_s.get("push_notifications", False), help="Recibe notificaciones en tu navegador")
    if push_enabled != _s.get("push_notifications", False):
        _s["push_notifications"] = push_enabled
        _guardar_config()
        st.success(f"Notificaciones push {'activadas' if push_enabled else 'desactivadas'}")
    st.caption("Las notificaciones por correo se configuran desde la integracion SMTP en Avanzado.")
