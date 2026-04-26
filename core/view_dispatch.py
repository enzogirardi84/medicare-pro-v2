"""Despacho de vistas y navegación por módulos.

Extraído de main.py para mantenerlo liviano.
Contiene: render_current_view, resolve_current_view, render_module_nav,
resolve_menu_for_role y helpers de navegación mobile.
"""
from importlib import import_module

import streamlit as st

from core.app_logging import log_event
from core.user_feedback import render_carga_modulo_fallo, render_modulo_fallo_ui
from core.nav_helpers import (
    MC_FILTRO_TODAS,
    categorias_con_modulos_en_menu,
    etiqueta_filtro_categoria,
    get_categorias_modulos,
)

_VIEW_FN_CACHE: dict = {}


def _get_render_fn(tab_name, view_config):
    """Obtiene la función render del módulo. Maneja errores con mensaje visible."""
    if tab_name not in _VIEW_FN_CACHE:
        try:
            module_name, function_name = view_config[tab_name]
        except KeyError:
            st.error(f"Modulo '{tab_name}' no encontrado en la configuracion de vistas. Contacte al administrador.")
            log_event("view_dispatch", f"modulo_no_configurado:{tab_name}")
            raise
        try:
            mod = import_module(module_name)
            _VIEW_FN_CACHE[tab_name] = getattr(mod, function_name)
        except Exception as exc:
            st.error(f"Error al cargar el modulo '{tab_name}': {type(exc).__name__}")
            log_event("view_dispatch", f"import_fallo:{tab_name}:{type(exc).__name__}:{exc}")
            raise
    return _VIEW_FN_CACHE[tab_name]


def render_current_view(tab_name, paciente_sel, mi_empresa, user, rol, view_config, menu_set=None):
    """Renderiza la vista activa. Captura errores y muestra UI de fallback."""
    if menu_set is None:
        menu_set = frozenset(resolve_menu_for_role(rol, user, view_config))
    if tab_name not in menu_set:
        st.error("No tienes permisos para acceder a este modulo.")
        return
    try:
        from core.view_helpers import aplicar_compactacion_movil_por_vista
        aplicar_compactacion_movil_por_vista(tab_name)
    except Exception as _exc:
        log_event("view_dispatch", f"compactacion_movil_falla:{tab_name}:{type(_exc).__name__}")
    try:
        render_fn = _get_render_fn(tab_name, view_config)
    except Exception as exc:
        render_carga_modulo_fallo(tab_name, exc)
        return

    try:
        if tab_name == "Visitas y Agenda":
            render_fn(paciente_sel, mi_empresa, user, rol)
        elif tab_name == "Clinicas (panel global)":
            render_fn(mi_empresa, user, rol)
        elif tab_name == "Admision":
            render_fn(mi_empresa, rol)
        elif tab_name in ("Clinica", "Pediatria", "Historial", "Escalas Clinicas", "Balance"):
            render_fn(paciente_sel, user)
        elif tab_name in ("Evolucion", "Estudios"):
            render_fn(paciente_sel, user, rol)
        elif tab_name == "PDF":
            render_fn(paciente_sel, mi_empresa, user, rol)
        elif tab_name in ("Materiales", "Emergencias y Ambulancia"):
            render_fn(paciente_sel, mi_empresa, user)
        elif tab_name in ("Recetas", "Caja"):
            render_fn(paciente_sel, mi_empresa, user, rol)
        elif tab_name == "Inventario":
            render_fn(mi_empresa)
        elif tab_name == "Alertas app paciente":
            render_fn(mi_empresa, user, rol)
        elif tab_name == "Red de Profesionales":
            render_fn(mi_empresa, user, rol)
        elif tab_name == "Mi Equipo":
            render_fn(mi_empresa, rol, user)
        elif tab_name == "Telemedicina":
            render_fn(paciente_sel)
        elif tab_name == "Dashboard":
            render_fn(mi_empresa, rol)
        elif tab_name in ("Cierre Diario", "Auditoria", "Auditoria Legal", "Asistencia en Vivo"):
            render_fn(mi_empresa, user)
        elif tab_name == "RRHH y Fichajes":
            render_fn(mi_empresa, rol, user)
        elif tab_name == "Proyecto y Roadmap":
            render_fn(mi_empresa, user, rol)
        elif tab_name == "Diagnosticos":
            render_fn(user)
        else:
            render_fn(paciente_sel, mi_empresa, user, rol)
    except Exception as exc:
        log_event("ui", f"modulo_fallo:{tab_name}:{type(exc).__name__}")
        st.error(f"Error critico en el modulo **{tab_name}**: {exc}")
        st.exception(exc)
        render_modulo_fallo_ui(tab_name, exc)


def resolve_current_view(menu, menu_set=None):
    """Determina qué módulo debe mostrarse según sesión y permisos."""
    if not menu:
        st.session_state.pop("modulo_actual", None)
        return None
    ms = menu_set if menu_set is not None else frozenset(menu)
    vista_actual = st.session_state.get("modulo_actual", menu[0])
    if vista_actual not in ms:
        vista_actual = menu[0]
    st.session_state["modulo_actual"] = vista_actual
    return vista_actual


def render_module_nav(menu, vista_actual, view_nav_labels, menu_set=None):
    """Renderiza la navegación de módulos. Fallback st.radio si st.pills falla."""
    if not menu:
        return None
    menu_set = frozenset(menu) if menu_set is None else menu_set
    st.subheader("Panel de Módulos del Sistema")
    st.caption("Filtrá por área o mostrá todos los módulos habilitados para tu rol.")

    cats_ok = categorias_con_modulos_en_menu(menu_set)
    filtro_opciones = [MC_FILTRO_TODAS] + cats_ok

    if "mc_nav_filtro_cat" not in st.session_state or st.session_state["mc_nav_filtro_cat"] not in filtro_opciones:
        st.session_state["mc_nav_filtro_cat"] = MC_FILTRO_TODAS

    filtro = st.selectbox(
        "Area del sistema",
        filtro_opciones,
        key="mc_nav_filtro_cat",
        format_func=etiqueta_filtro_categoria,
        label_visibility="collapsed",
    )

    categorias_modulos = get_categorias_modulos()
    if filtro == MC_FILTRO_TODAS:
        pill_options = list(menu)
        default_sel = vista_actual if vista_actual in menu_set else pill_options[0]
    else:
        mods_in_cat = [m for m in categorias_modulos.get(filtro, []) if m in menu_set]
        if not mods_in_cat:
            st.caption("No hay módulos en esta área para tu usuario.")
            pill_options = list(menu)
            default_sel = vista_actual if vista_actual in menu_set else pill_options[0]
        elif vista_actual in mods_in_cat:
            pill_options = mods_in_cat
            default_sel = vista_actual
        else:
            pill_options = [vista_actual] + [m for m in mods_in_cat if m != vista_actual]
            default_sel = vista_actual

    # Navegación nativa con botones reales en un solo bloque de columnas
    # (el CSS Bento Flex organiza el layout: 6 por fila en PC, 3 en móvil).
    selected = None
    if pill_options:
        cols = st.columns(len(pill_options))
        for c, opt in zip(cols, pill_options):
            with c:
                label = view_nav_labels.get(opt, opt)
                tipo = "primary" if opt == default_sel else "secondary"
                if st.button(label, key=f"navbtn_{opt}", use_container_width=True, type=tipo):
                    selected = opt
    if selected and selected != vista_actual:
        st.session_state["modulo_anterior"] = vista_actual
        st.session_state["modulo_actual"] = selected
        return selected
    return selected or vista_actual


def resolve_menu_for_role(rol, user, view_config, obtener_modulos_fn=None):
    """Devuelve la lista de módulos visibles para el rol del usuario."""
    if callable(obtener_modulos_fn):
        menu_base = obtener_modulos_fn(rol, list(view_config), user) or []
    else:
        menu_base = list(view_config)
    return [modulo for modulo in menu_base if modulo in view_config]
