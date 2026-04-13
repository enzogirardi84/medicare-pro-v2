"""
Modo anticolapso — prioriza estabilidad del navegador y la sesión Streamlit.

- Secret opcional **MC_ANTICOLAPSO** (`true` / `1` / `on`): aplica a todo el despliegue.
- Checkbox en sidebar: anticolapso solo para la sesión actual (no borra datos).

Efectos: menos filas en el selector de pacientes sin búsqueda, y **UI liviana** forzada
(misma idea que «Modo liviano siempre» en Rendimiento).
"""

from __future__ import annotations

import streamlit as st

LIMITE_PACIENTES_SIDEBAR_NORMAL = 80
LIMITE_PACIENTES_SIDEBAR_ANTICOLAPSO = 40


def _truthy_secret(val) -> bool:
    if isinstance(val, bool):
        return val
    s = str(val or "").strip().lower()
    return s in ("1", "true", "yes", "si", "on")


def anticolapso_por_secret() -> bool:
    try:
        return _truthy_secret(st.secrets.get("MC_ANTICOLAPSO", False))
    except Exception:
        return False


def anticolapso_por_sesion() -> bool:
    return bool(st.session_state.get("mc_anticolapso_sesion"))


def anticolapso_activo() -> bool:
    return anticolapso_por_secret() or anticolapso_por_sesion()


def limite_pacientes_sidebar() -> int:
    return LIMITE_PACIENTES_SIDEBAR_ANTICOLAPSO if anticolapso_activo() else LIMITE_PACIENTES_SIDEBAR_NORMAL


def aplicar_politicas_anticolapso_ui() -> None:
    """Debe ejecutarse antes del selectbox de modo liviano en el mismo run."""
    if anticolapso_activo():
        st.session_state["mc_liviano_modo"] = "on"


def render_estabilidad_anticolapso_sidebar() -> None:
    st.markdown(
        """
        <div class="mc-sidebar-section">
            <div class="mc-sidebar-kicker">Estabilidad</div>
            <div class="mc-sidebar-title">Modo anticolapso</div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    if anticolapso_por_secret():
        st.caption(
            "Anticolapso **fijado por el servidor** (secret `MC_ANTICOLAPSO`): "
            f"hasta **{LIMITE_PACIENTES_SIDEBAR_ANTICOLAPSO}** pacientes sin busqueda e interfaz liviana."
        )
    else:
        st.checkbox(
            "Activar anticolapso esta sesion",
            key="mc_anticolapso_sesion",
            help="Reduce pacientes visibles sin filtro y fuerza interfaz liviana para equipos lentos o conexiones inestables.",
        )
        if anticolapso_por_sesion():
            st.caption(
                f"Activo en esta sesion: maximo **{LIMITE_PACIENTES_SIDEBAR_ANTICOLAPSO}** pacientes sin escribir en el buscador."
            )
