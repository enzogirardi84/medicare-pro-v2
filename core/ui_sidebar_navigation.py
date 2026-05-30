"""Menu de navegacion resiliente y controlado por st.session_state.
Reemplaza widgets rigidos por botones con callbacks atomicos.
En mobile: pills HTML planas que evitan colisiones tactiles.
"""
from __future__ import annotations

from typing import Any

import streamlit as st

from core.app_logging import log_event
from core.ui_nav_interceptor import (
    boton_modulo_seguro,
    generar_key_unica,
    procesar_cambio_submodulo,
)

# Configuracion de categorias y sus modulos
CATEGORIAS: dict[str, list[tuple[str, str]]] = {
    "Clinica": [
        ("Dashboard", "Dashboard"),
        ("Mi Equipo", "Mi Equipo"),
        ("Admision", "Admision"),
    ],
    "Gestion": [
        ("Visitas", "Visitas y Agenda"),
        ("Turnos", "Turnos Online"),
        ("Recetas", "Recetas"),
        ("Caja", "Caja"),
        ("Inventario", "Inventario"),
    ],
    "Emergencias": [
        ("Emergencias", "Emergencias y Ambulancia"),
        ("Telemedicina", "Telemedicina"),
    ],
    "Legal": [
        ("Auditoria", "Auditoria"),
        ("PDF", "Visor PDF"),
        ("Historial", "Historial"),
    ],
}


def _render_mobile_pills(modulos: list[str], vista_actual: str) -> None:
    """Renderiza navegacion mobile como pills HTML puras.

    Sin widgets de Streamlit, cero re-renders. Click navega via URL.
    """
    from html import escape

    html = '<div style="display:flex;flex-wrap:wrap;gap:6px;padding:4px 0;">'
    for mod in modulos:
        activo = mod == vista_actual
        bg = "rgba(14,165,233,0.15)" if activo else "rgba(15,23,42,0.5)"
        color = "#38bdf8" if activo else "#e2e8f0"
        border = "1px solid rgba(14,165,233,0.3)" if activo else "1px solid rgba(51,65,85,0.3)"
        html += (
            f'<a href="?modulo={escape(mod)}" '
            f'style="display:inline-flex;align-items:center;padding:8px 16px;'
            f'border-radius:9999px;background:{bg};color:{color};'
            f'border:{border};font-size:0.82rem;font-weight:600;'
            f'text-decoration:none;min-height:38px;">{escape(mod)}</a>'
        )
    html += "</div>"
    st.markdown(html, unsafe_allow_html=True)


def _render_desktop_accordion(
    cats: dict[str, list[tuple[str, str]]],
    vista_actual: str,
    modo_compacto: bool = False,
) -> None:
    """Renderiza navegacion desktop como acordeon con estado controlado.

    Cada categoria es un boton que abre/cierra su seccion.
    Los submodulos usan boton_modulo_seguro con callback atomico.
    """
    for cat, items in cats.items():
        if not items:
            continue

        cat_key = generar_key_unica(f"_nav_cat_{cat}")
        is_open = st.session_state.get(cat_key, False)

        # Boton de categoria
        icono = "▼" if is_open else "▶"
        if st.button(
            f"{icono}  {cat}",
            key=generar_key_unica(f"_nav_toggle_{cat}"),
            use_container_width=True,
        ):
            # Toggle: cerrar todas, abrir solo esta
            for c in cats:
                st.session_state[generar_key_unica(f"_nav_cat_{c}")] = False
            st.session_state[cat_key] = not is_open
            st.rerun()

        # Submodulos (solo si la categoria esta abierta)
        if st.session_state.get(cat_key, False):
            for label, modulo in items:
                boton_modulo_seguro(
                    label=label,
                    modulo=modulo,
                    key_base=f"nav_sub_{cat}",
                )


def renderizar_navegacion_sidebar(
    menu: list[str],
    vista_actual: str,
    es_movil: bool = False,
) -> None:
    """Renderiza la navegacion completa en la sidebar.

    Args:
        menu: Lista de modulos permitidos para el rol.
        vista_actual: Modulo actualmente activo.
        es_movil: Si es entorno mobile, usa pills HTML.
    """
    # Filtrar categorias a solo modulos permitidos
    menu_set = set(menu)
    cats_filtradas: dict[str, list[tuple[str, str]]] = {}
    for cat, items in CATEGORIAS.items():
        filtrados = [(l, m) for l, m in items if m in menu_set]
        if filtrados:
            cats_filtradas[cat] = filtrados

    if not cats_filtradas:
        # Fallback: lista plana de modulos
        modulos_flat = [m for m in menu if m in [i[1] for sub in CATEGORIAS.values() for i in sub]]
        if es_movil:
            _render_mobile_pills(modulos_flat, vista_actual)
        else:
            for m in modulos_flat:
                boton_modulo_seguro(label=m, modulo=m, key_base="nav_flat")
        return

    if es_movil:
        # Mobile: lista plana de todos los modulos como pills
        todos = [m for sub in cats_filtradas.values() for _, m in sub]
        _render_mobile_pills(todos, vista_actual)
    else:
        # Desktop: acordeon
        _render_desktop_accordion(cats_filtradas, vista_actual)


def inicializar_estado_navegacion(menu: list[str]) -> None:
    """Inicializa el estado de navegacion en session_state.

    Debe llamarse UNA vez por sesion.
    """
    if st.session_state.get("_nav_initialized"):
        return
    st.session_state["_nav_initialized"] = True

    # Inicializar categorias como cerradas
    for cat in CATEGORIAS:
        key = generar_key_unica(f"_nav_cat_{cat}")
        if key not in st.session_state:
            st.session_state[key] = False

    # Abrir categoria del modulo actual si existe
    vista = st.session_state.get("modulo_actual")
    if vista:
        try:
            from core.nav_helpers import get_categorias_modulos
            categorias = get_categorias_modulos()
            for cat, mods in categorias.items():
                if vista in mods:
                    st.session_state[generar_key_unica(f"_nav_cat_{cat}")] = True
                    return
        except Exception:
            pass
