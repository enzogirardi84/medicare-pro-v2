"""Despacho de vistas y navegación por módulos.

Extraído de main.py para mantenerlo liviano.
Contiene: render_current_view, resolve_current_view, render_module_nav,
resolve_menu_for_role y helpers de navegación mobile.
"""
import html
from importlib import import_module
from urllib.parse import quote_plus

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


def _split_icon_label(label: str):
    """Separa icono y texto. Ejemplo: '📍 Visitas' -> ('📍', 'Visitas')"""
    label = str(label or "").strip()
    if not label:
        return "▣", ""
    partes = label.split(maxsplit=1)
    if len(partes) == 2:
        posible_icono, texto = partes
        if not posible_icono.replace("_", "").isalnum():
            return posible_icono, texto
    return "▣", label


def procesar_query_params_navegacion(menu_set):
    """Procesa links tipo ?modulo=Dashboard."""
    qp = getattr(st, "query_params", None)
    if qp is None:
        return
    try:
        raw_mod = qp.get("modulo")
        if raw_mod is None:
            return
        modulo_nuevo = str(raw_mod[0] if isinstance(raw_mod, list) else raw_mod).strip()
        if modulo_nuevo and modulo_nuevo in menu_set:
            modulo_actual = st.session_state.get("modulo_actual")
            if modulo_actual != modulo_nuevo:
                st.session_state["modulo_anterior"] = modulo_actual
                st.session_state["modulo_actual"] = modulo_nuevo
        try:
            del st.query_params["modulo"]
        except Exception:
            pass
        st.rerun()
    except Exception as exc:
        log_event("main_nav", f"query_params_nav_error:{type(exc).__name__}:{exc}")


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


def render_modulos_grid(modulos, modulo_actual=None, view_nav_labels=None):
    """Renderiza una grilla HTML/CSS de módulos sin usar st.columns.

    - PC: botones tipo cápsula 150-170px, icono + texto horizontal.
    - Móvil: 3 botones por fila, icono arriba y texto abajo.
    - Navegación por query param ?modulo=Nombre+Modulo.
    """
    st.markdown(
        """
    <style>
    .mod-grid {
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(150px, 150px));
        gap: 10px;
        margin: 14px 0 28px 0;
        align-items: stretch;
    }
    .mod-card {
        height: 58px;
        padding: 0 14px;
        display: flex;
        align-items: center;
        justify-content: flex-start;
        gap: 9px;
        border-radius: 15px;
        border: 1px solid rgba(148, 163, 184, 0.35);
        background: rgba(15, 23, 42, 0.92);
        color: #ffffff !important;
        text-decoration: none !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.25);
        transition: all 0.15s ease;
        overflow: hidden;
    }
    .mod-card:hover {
        border-color: rgba(56, 189, 248, 0.75);
        background: rgba(30, 41, 59, 0.98);
        transform: translateY(-1px);
    }
    .mod-card.active {
        border-color: #38bdf8;
        background: linear-gradient(135deg, rgba(14,165,233,0.28), rgba(15,23,42,0.95));
        box-shadow: 0 0 0 1px rgba(56,189,248,0.35);
    }
    .mod-icon {
        font-size: 18px;
        line-height: 1;
        flex: 0 0 auto;
    }
    .mod-text {
        font-size: 13px;
        font-weight: 600;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        min-width: 0;
    }
    @media (max-width: 640px) {
        .mod-grid {
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 8px;
        }
        .mod-card {
            height: 66px;
            padding: 8px 6px;
            flex-direction: column;
            justify-content: center;
            text-align: center;
            gap: 5px;
        }
        .mod-icon {
            font-size: 18px;
        }
        .mod-text {
            font-size: 10.5px;
            max-width: 100%;
        }
    }
    </style>
    """,
        unsafe_allow_html=True,
    )

    cards = []
    for modulo in modulos:
        nombre_raw = str(modulo)
        if not nombre_raw:
            continue

        label = (view_nav_labels or {}).get(nombre_raw, nombre_raw)
        icono, texto = _split_icon_label(label)

        active = " active" if nombre_raw == modulo_actual else ""
        url = "?modulo=" + quote_plus(nombre_raw)

        cards.append(
            f'<a class="mod-card{active}" href="{url}" target="_self" title="{html.escape(nombre_raw)}">'
            f'<span class="mod-icon">{html.escape(icono)}</span>'
            f'<span class="mod-text">{html.escape(texto)}</span>'
            f"</a>"
        )

    if cards:
        st.markdown(
            '<div class="mod-grid">' + "\n".join(cards) + "</div>",
            unsafe_allow_html=True,
        )


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

    # Grilla HTML/CSS responsive sin st.columns (evita anclajes angostos de Streamlit).
    render_modulos_grid(pill_options, default_sel, view_nav_labels)
    return default_sel


def resolve_menu_for_role(rol, user, view_config, obtener_modulos_fn=None):
    """Devuelve la lista de módulos visibles para el rol del usuario."""
    if callable(obtener_modulos_fn):
        menu_base = obtener_modulos_fn(rol, list(view_config), user) or []
    else:
        menu_base = list(view_config)
    return [modulo for modulo in menu_base if modulo in view_config]
