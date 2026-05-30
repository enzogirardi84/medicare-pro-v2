"""Enrutador fragmentado para aislamiento de modulos en Streamlit.
Usa @st.fragment para confinar re-renders dentro del modulo activo.
El sidebar permanece estatico, el foco del teclado se conserva.
60 FPS estables en dispositivos mobiles.
"""
from __future__ import annotations

import time
from typing import Any, Callable, Optional

import streamlit as st

from core.app_logging import log_event


class FragmentRouter:
    """Router que envuelve cada vista en un fragmento aislado.

    Las interacciones dentro de un fragmento NO disparan re-run
    del script maestro. Solo el fragmento activo se re-renderiza.

    El sidebar (navegacion + indicadores) queda fuera del fragmento
    y no se ve afectado.
    """

    def __init__(self):
        self._render_fns: dict[str, Callable] = {}

    def registrar_modulo(self, nombre: str, render_fn: Callable) -> None:
        """Registra la funcion render de un modulo.

        La funcion se envuelve automaticamente en @st.fragment.
        """
        @st.fragment
        def _fragment_wrapper(**kwargs: Any) -> None:
            """Wrapper fragmentado que aísla re-renders del modulo."""
            t0 = time.perf_counter()
            try:
                render_fn(**kwargs)
            except Exception as exc:
                st.error(f"Error en modulo {nombre}")
                log_event("fragment_router", f"error:{nombre}:{type(exc).__name__}")
            dt = (time.perf_counter() - t0) * 1000
            log_event("ui_perf", f"fragment:{nombre}:{dt:.0f}ms")

        self._render_fns[nombre] = _fragment_wrapper

    def render_modulo(self, nombre: str, **kwargs: Any) -> None:
        """Renderiza un modulo dentro de su fragmento aislado.

        Args:
            nombre: Nombre del modulo.
            **kwargs: Argumentos para la funcion render.
        """
        fn = self._render_fns.get(nombre)
        if fn is None:
            st.error(f"Modulo '{nombre}' no registrado en FragmentRouter")
            return
        fn(**kwargs)

    @property
    def modulos_registrados(self) -> list[str]:
        return list(self._render_fns.keys())


# ═══════════════════════════════════════════════════════════════════
# FRAGMENTOS DEL SIDEBAR (EVITAN RE-RENDER AL CAMBIAR DE MODULO)
# ═══════════════════════════════════════════════════════════════════

@st.fragment
def _sidebar_logout_fragment() -> None:
    """Fragmento del boton de logout en sidebar.

    Aislado para que el click no rerenderice el modulo activo.
    """
    if st.sidebar.button("Cerrar sesion", use_container_width=True, key="sidebar_logout_frag"):
        from main_medicare import _logout_callback
        _logout_callback()
        st.rerun()


@st.fragment
def _sidebar_settings_fragment() -> None:
    """Fragmento del boton de configuracion."""
    if st.sidebar.button("Configuracion", use_container_width=True, key="sidebar_settings_frag"):
        st.session_state["_show_settings"] = True
        st.rerun()


@st.fragment
def _sidebar_totp_fragment() -> None:
    """Fragmento del boton de 2FA en sidebar."""
    user_login = str(st.session_state.get("u_actual", {}).get("usuario_login", ""))
    if user_login and st.sidebar.button("Mi perfil / 2FA", use_container_width=True, key="sidebar_totp_frag"):
        st.session_state["_show_totp_setup"] = True
        st.rerun()


def render_sidebar_fragments() -> None:
    """Renderiza los fragmentos del sidebar.

    Cada fragmento esta aislado: clicks no afectan el modulo activo.
    """
    _sidebar_logout_fragment()
    _sidebar_settings_fragment()
    _sidebar_totp_fragment()


# ═══════════════════════════════════════════════════════════════════
# INTEGRACION CON EL ROUTER LAZY
# ═══════════════════════════════════════════════════════════════════

def render_vista_fragmentada(
    vista_actual: str,
    lazy_loader: Any,
    **kwargs: Any,
) -> None:
    """Renderiza la vista actual usando lazy loader + fragment router.

    1. Obtiene la funcion render del lazy loader (importacion perezosa)
    2. La envuelve en @st.fragment
    3. Renderiza aisladamente

    Args:
        vista_actual: Nombre del modulo activo.
        lazy_loader: Instancia de StrictLazyLoader.
        **kwargs: Argumentos para el modulo.
    """
    fn = lazy_loader.obtener(vista_actual)
    if fn is None:
        st.error(f"Modulo '{vista_actual}' no disponible")
        return

    # Wrapper fragmentado
    @st.fragment
    def _modulo_fragment(**frag_kwargs: Any) -> None:
        t0 = time.perf_counter()
        try:
            fn(**frag_kwargs)
        except Exception as exc:
            st.error(f"Error en {vista_actual}")
            log_event("fragment_router", f"error:{vista_actual}:{type(exc).__name__}")
        dt = (time.perf_counter() - t0) * 1000
        log_event("ui_perf", f"frag:{vista_actual}:{dt:.0f}ms")

    _modulo_fragment(**kwargs)
