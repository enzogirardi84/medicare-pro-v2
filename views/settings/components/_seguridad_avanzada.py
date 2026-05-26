"""Configuracion de seguridad, opciones avanzadas y reglas de insumos."""

from __future__ import annotations

import streamlit as st

import importlib.metadata
import os
import platform
import sys

from core.app_logging import log_event
from core.database import guardar_datos


def _guardar_config():
    guardar_datos(spinner=False, force=True)


def render_security_settings(is_admin: bool):
    st.header("🔒 Seguridad")
    _s = st.session_state.setdefault("settings_db", {})
    st.caption("Configuracion de politicas de acceso y seguridad del sistema.")
    if not is_admin:
        st.info("Solo administradores pueden modificar la configuracion de seguridad.")
        return

    min_length = st.slider("Longitud minima de contrasena", min_value=6, max_value=20, value=_s.get("sec_min_length", 8))
    require_special = st.checkbox("Requerir caracter especial", value=_s.get("sec_require_special", True))
    require_upper = st.checkbox("Requerir mayuscula", value=_s.get("sec_require_upper", True))
    session_timeout = st.number_input("Tiempo de sesion (minutos)", min_value=5, max_value=120, value=_s.get("sec_session_timeout", 30))

    if st.button("💾 Guardar configuracion de seguridad", use_container_width=True):
        _s["sec_min_length"] = min_length
        _s["sec_require_special"] = require_special
        _s["sec_require_upper"] = require_upper
        _s["sec_session_timeout"] = session_timeout
        _guardar_config()
        st.success("Configuracion de seguridad guardada")
        log_event("settings", "Seguridad guardada")


def render_advanced_settings(is_admin: bool):
    st.header("⚡ Opciones Avanzadas")
    _s = st.session_state.setdefault("settings_db", {})
    st.caption("Configuraciones tecnicas y de desarrollo.")

    st.subheader("Diagnostico del Sistema")
    def _ver():
        try:
            return importlib.metadata.version("medicare-pro")
        except (importlib.metadata.PackageNotFoundError, Exception):
            return "2.0.0-dev"
    def _env(): return os.getenv("MEDICARE_ENV", "development")
    def _py(): return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    def _os(): return f"{platform.system()} {platform.release()}"
    col1, col2 = st.columns(2)
    col1.metric("Version", _ver())
    col1.metric("Entorno", _env())
    col2.metric("Python", _py())
    col2.metric("SO", _os())

    st.divider()
    from services.telemetria_service import render_telemetria_dashboard
    render_telemetria_dashboard()
    st.divider()
    from services.monitoreo_proactivo import render_monitoreo_dashboard
    render_monitoreo_dashboard()
    st.divider()
    st.subheader("Herramientas de Administracion")
    if st.button("🔄 Limpiar cache del sistema", use_container_width=True):
        from core.database import limpiar_cache_app
        n = limpiar_cache_app()
        st.success(f"Cache limpiada: {n} entradas eliminadas.")

    if st.button("📊 Ejecutar diagnostico completo", use_container_width=True):
        from views.diagnosticos import render_diagnosticos
        render_diagnosticos()
        st.stop()

    st.divider()
    st.subheader("Configuracion SMTP (Correo)")
    _s["smtp_host"] = st.text_input("Servidor SMTP", value=_s.get("smtp_host", ""), placeholder="smtp.gmail.com")
    _s["smtp_port"] = st.number_input("Puerto SMTP", min_value=1, max_value=65535, value=_s.get("smtp_port", 587))
    _s["smtp_user"] = st.text_input("Usuario SMTP", value=_s.get("smtp_user", ""), placeholder="correo@clinica.com")
    _s["smtp_pass"] = st.text_input("Contrasena SMTP", type="password", value=_s.get("smtp_pass", ""))
    if st.button("💾 Guardar configuracion SMTP", use_container_width=True):
        _guardar_config()
        st.success("Configuracion SMTP guardada")


def render_insumos_rules_settings(is_admin: bool):
    st.header("📦 Reglas de Insumos")
    _s = st.session_state.setdefault("settings_db", {})
    st.caption("Configura reglas personalizadas para medicamentos y procedimientos.")
    if not is_admin:
        st.info("Solo administradores pueden modificar las reglas de insumos.")
        return

        with st.expander("💊 Reglas de Medicamentos", expanded=False):
            st.info("Sin reglas personalizadas todavia. Usa el vademecum por defecto.")
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Medicamento", placeholder="Ej: Amoxicilina", key="ins_med_name")
        with col2:
            st.number_input("Stock minimo", min_value=0, value=10, key="ins_med_min")
        if st.button("Agregar regla de medicamento", use_container_width=True, key="add_med_rule"):
            st.success("Regla de medicamento agregada (simulado)")

    with st.expander("🩺 Reglas de Procedimientos", expanded=False):
        st.info("Sin reglas personalizadas todavia.")
        col1, col2 = st.columns(2)
        with col1:
            st.text_input("Procedimiento", placeholder="Ej: Curacion simple", key="ins_proc_name")
        with col2:
            st.text_input("Insumos requeridos", placeholder="Gasas,aposito,etc", key="ins_proc_items")
        if st.button("Agregar regla de procedimiento", use_container_width=True, key="add_proc_rule"):
            st.success("Regla de procedimiento agregada (simulado)")
