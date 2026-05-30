"""Interceptor de navegacion via callbacks atomicos para evitar UI State Lock.
Ejecuta los cambios de estado en el backend ANTES del re-redibujado.
Limpia keys de acordeon y fuerzas un unico rerun.
"""
from __future__ import annotations

import streamlit as st

from core.app_logging import log_event


def procesar_cambio_submodulo(nuevo_submodulo: str) -> None:
    """Callback atomico de cambio de submodulo.

    Se ejecuta INMEDIATAMENTE en el backend antes del re-redibujado.
    Garantiza que:
    a) modulo_activo se actualiza
    b) El acordeon del menu principal se colapsa
    c) Un unico st.rerun() limpia el arbol de componentes React
    """
    # 1. Preservar modulo anterior
    modulo_anterior = st.session_state.get("modulo_actual")
    if modulo_anterior and modulo_anterior != nuevo_submodulo:
        st.session_state["modulo_anterior"] = modulo_anterior

    # 2. Actualizar modulo activo
    st.session_state["modulo_actual"] = nuevo_submodulo

    # 3. Colapsar TODAS las categorias del menu
    for cat in ("Clínica", "Gestión", "Emergencias", "Legal y documentación"):
        st.session_state[f"_nav_cat_{cat}"] = False

    # 4. Abrir SOLO la categoria del nuevo modulo
    _abrir_categoria_del_modulo(nuevo_submodulo)

    # 5. Limpiar cortina de navegacion
    st.session_state.pop("_show_nav_cortina", None)

    # 6. Un unico rerun para limpiar el buffer React
    st.rerun()


def _abrir_categoria_del_modulo(modulo: str) -> None:
    """Abre la categoria que contiene el modulo especificado."""
    try:
        from core.nav_helpers import get_categorias_modulos
        categorias = get_categorias_modulos()
        for cat, mods in categorias.items():
            if modulo in mods:
                st.session_state[f"_nav_cat_{cat}"] = True
                return
    except Exception as exc:
        log_event("nav_interceptor", f"abrir_categoria_error:{type(exc).__name__}")


def generar_key_unica(base: str) -> str:
    """Genera una key unica para widgets basada en tenant + usuario.

    Previene colisiones de cache entre sesiones o tenants.
    """
    tenant = st.session_state.get("_mc_tenant_id", "default")
    usuario = str(st.session_state.get("u_actual", {}).get("usuario_login", "anon"))
    return f"{base}_{tenant}_{usuario}"


def boton_modulo_seguro(
    label: str,
    modulo: str,
    key_base: str = "nav_mod",
) -> bool:
    """Renderiza un boton de modulo con callback atomico.

    Usa on_click para ejecutar procesar_cambio_submodulo
    ANTES del re-redibujado, eliminando el UI State Lock.

    Args:
        label: Texto del boton.
        modulo: Nombre del modulo destino.
        key_base: Base para generar key unica.

    Returns:
        Siempre False (el callback maneja la navegacion).
    """
    key = generar_key_unica(f"{key_base}_{modulo}")
    is_active = st.session_state.get("modulo_actual") == modulo

    st.button(
        label,
        key=key,
        use_container_width=True,
        type="primary" if is_active else "secondary",
        on_click=procesar_cambio_submodulo,
        args=(modulo,),
    )
    return False
