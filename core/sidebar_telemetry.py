"""Sidebar telemetry - indicadores de session timeout y sync offline.
Versiones ligeras que no fuerzan re-renders completos.
Los fragments no soportan st.sidebar, se usa actualizacion inline.
"""
from __future__ import annotations

import time
import streamlit as st
from core.app_logging import log_event

SESSION_TIMEOUT_MINUTES = 30


def render_timeout_sidebar() -> None:
    """Actualiza el indicador de timeout en la sidebar.

    Es ligero (solo calcula elapsed + renderiza 2 markdowns).
    No afecta el rendimiento del resto de la app.
    """
    if not st.session_state.get("logeado"):
        return

    last_activity = st.session_state.get("_session_last_activity")
    if last_activity is None:
        st.session_state["_session_last_activity"] = time.time()
        return

    elapsed = time.time() - last_activity
    remaining = SESSION_TIMEOUT_MINUTES * 60 - elapsed

    if remaining <= 0:
        _auto_save_and_logout()
        return

    mins = int(remaining // 60)
    secs = int(remaining % 60)
    color = "#94a3b8" if mins > 10 else ("#f59e0b" if mins > 2 else "#ef4444")

    st.sidebar.markdown("---")
    st.sidebar.markdown(
        f"<div style='font-size:0.75rem;color:{color};text-align:center;'>"
        f"Sesion: {mins:02d}:{secs:02d}</div>",
        unsafe_allow_html=True,
    )

    if mins < 2 and not st.session_state.get("_session_timeout_warning_shown"):
        st.session_state["_session_timeout_warning_shown"] = True
        st.sidebar.warning(
            "La sesion expirara en menos de 2 minutos. "
            "Los cambios se guardaran automaticamente."
        )


def render_offline_sidebar() -> None:
    """Actualiza el indicador de sincronizacion offline en la sidebar."""
    if not st.session_state.get("logeado"):
        return

    try:
        from core.offline_sync import SyncManager, render_offline_indicator
        if "_sync_manager" not in st.session_state:
            st.session_state["_sync_manager"] = SyncManager()
        render_offline_indicator(st.session_state["_sync_manager"])
    except Exception as exc:
        log_event("sidebar", f"offline_error:{type(exc).__name__}")


def _auto_save_and_logout() -> None:
    try:
        if st.session_state.get("_guardar_datos_pendiente"):
            from core.database import guardar_datos
            guardar_datos(spinner=False)
    except Exception as exc:
        log_event("session", f"auto_save_error:{type(exc).__name__}")

    st.session_state["logeado"] = False
    for k in ("u_actual", "_session_last_activity", "_session_timeout_warning_shown"):
        st.session_state.pop(k, None)
    st.warning("Sesion expirada por inactividad. Los datos fueron guardados.")
    st.rerun()
