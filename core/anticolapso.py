"""
Modo anticolapso — prioriza estabilidad del navegador y la sesión Streamlit.

- Secret opcional **MC_ANTICOLAPSO** (`true` / `1` / `on`): aplica a todo el despliegue.
- Automático: mismas señales que «equipo liviano» (UA antiguo, Save-Data, etc.) vía `headers_sugieren_equipo_liviano`.

Efectos: menos filas en el selector de pacientes sin búsqueda, y **UI liviana** forzada.
"""

from __future__ import annotations

import streamlit as st

from core.ui_liviano import headers_sugieren_equipo_liviano

LIMITE_PACIENTES_SIDEBAR_NORMAL = 80
LIMITE_PACIENTES_SIDEBAR_ANTICOLAPSO = 40


def _truthy_secret(val) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val or "").strip().lower()
    return s in ("1", "true", "yes", "si", "on")


def anticolapso_por_secret() -> bool:
    """El secret no cambia en caliente en una sesión típica; cacheamos lectura."""
    ck = "_mc_anticolapso_secret_cached"
    if ck in st.session_state:
        return bool(st.session_state[ck])
    try:
        out = _truthy_secret(st.secrets.get("MC_ANTICOLAPSO", False))
    except Exception:
        out = False
    st.session_state[ck] = out
    return out


def anticolapso_activo() -> bool:
    return anticolapso_por_secret() or headers_sugieren_equipo_liviano()


def limite_pacientes_sidebar() -> int:
    return LIMITE_PACIENTES_SIDEBAR_ANTICOLAPSO if anticolapso_activo() else LIMITE_PACIENTES_SIDEBAR_NORMAL


def aplicar_politicas_anticolapso_ui() -> None:
    """
    Fuerza interfaz liviana cuando anticolapso está activo (secret o detección automática).

    Llamar al inicio del sidebar **y de nuevo después** del `selectbox` de modo liviano,
    para que un intento de «modo completo» no deje `mc_liviano_modo` en `off` durante ese run.
    """
    if anticolapso_activo():
        st.session_state["mc_liviano_modo"] = "on"


def render_estabilidad_anticolapso_sidebar() -> None:
    """Sin UI manual: solo aviso si el despliegue fuerza anticolapso por secret."""
    if anticolapso_por_secret():
        st.caption(
            "Estabilidad **forzada por servidor** (`MC_ANTICOLAPSO`): listas acotadas e interfaz liviana."
        )
