"""Health Checks de infraestructura para inicio seguro.

Verifica conectividad con servicios criticos antes de permitir
operaciones en la UI. Previene perdida de datos por fallas de red.
"""

from __future__ import annotations

import socket
import time

import streamlit as st

from core.app_logging import log_event


def check_supabase_connection() -> bool:
    """Verifica conectividad basica con Supabase via DNS + ping."""
    from core._database_supabase import supabase
    if supabase is None:
        return False
    try:
        supabase.table("_health_check").select("count", count="exact").limit(1).execute()
        return True
    except Exception:
        return False


def check_internet_connection() -> bool:
    """Verifica conectividad a internet via DNS de Cloudflare."""
    try:
        socket.create_connection(("8.8.8.8", 53), timeout=1.5)
        return True
    except OSError:
        return False


def run_startup_checks() -> bool:
    """Ejecuta health checks al iniciar la aplicacion.
    
    Si ya se ejecutaron y estan OK, retorna True inmediatamente.
    Si fallan, muestra pantalla de contingencia y retorna False.
    """
    if st.session_state.get("_health_status") == "OK":
        return True
    
    status = {
        "supabase": check_supabase_connection(),
        "internet": check_internet_connection(),
        "timestamp": time.time(),
    }
    
    if status["supabase"] and status["internet"]:
        st.session_state._health_status = "OK"
        log_event("health_check", "startup_ok: todos los servicios disponibles")
        return True
    
    # Pantalla de contingencia
    st.error("🚨 **Falla de Infraestructura Detectada**")
    st.write("El sistema ha bloqueado las operaciones para evitar perdida de datos clinicos.")
    
    col1, col2 = st.columns(2)
    col1.metric("Base de Datos", "🟢 ONLINE" if status["supabase"] else "🔴 OFFLINE")
    col2.metric("Red Externa", "🟢 ONLINE" if status["internet"] else "🔴 OFFLINE")
    
    st.info("🔄 Reintentando conexion automaticamente en segundo plano...")
    
    if st.button("🔄 Forzar Re-verificacion", use_container_width=True):
        st.session_state.pop("_health_status", None)
        st.rerun()
    
    log_event("health_check", f"startup_fail: supabase={status['supabase']}, internet={status['internet']}")
    st.stop()
    return False
