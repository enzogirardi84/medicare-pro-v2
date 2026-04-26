"""Navegación de módulos: query params, grilla responsive, resolución de vistas.

Consolida lo que antes estaba duplicado entre main.py y core/view_dispatch.py.
"""

import html
from html import escape as html_escape
from importlib import import_module
from urllib.parse import quote_plus

import streamlit as st

from core.app_logging import log_event
from core.nav_helpers import (
    MC_FILTRO_TODAS,
    categorias_con_modulos_en_menu,
    etiqueta_filtro_categoria,
    get_categorias_modulos,
)
from core.user_feedback import render_carga_modulo_fallo, render_modulo_fallo_ui

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
    """Procesa links tipo ?modulo=Dashboard. Solo hace st.rerun() si realmente cambió."""
    qp = getattr(st, "query_params", None)
    if qp is None:
        return
    try:
        raw_mod = qp.get("modulo")
        if raw_mod is None:
            return
        modulo_nuevo = str(raw_mod[0] if isinstance(raw_mod, list) else raw_mod).strip()
        if not modulo_nuevo or modulo_nuevo not in menu_set:
            # Limpiar param inválido sin rerun
            try:
                del st.query_params["modulo"]
            except Exception:
                pass
            return
        modulo_actual = st.session_state.get("modulo_actual")
        if modulo_actual == modulo_nuevo:
            # Ya está en el módulo pedido; solo limpiar param
            try:
                del st.query_params["modulo"]
            except Exception:
                pass
            return
        st.session_state["modulo_anterior"] = modulo_actual
        st.session_state["modulo_actual"] = modulo_nuevo
        try:
            del st.query_params["modulo"]
        except Exception:
            pass
        st.rerun()
    except Exception as exc:
        log_event("main_nav", f"query_params_nav_error:{type(exc).__name__}:{exc}")


def resolve_menu_for_role(rol, user, view_config, obtener_modulos_fn=None):
    """Devuelve la lista de módulos visibles para el rol del usuario."""
    if callable(obtener_modulos_fn):
        menu_base = obtener_modulos_fn(rol, list(view_config), user) or []
    else:
        menu_base = list(view_config)
    return [modulo for modulo in menu_base if modulo in view_config]


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
    """Renderiza la navegación de módulos en un solo bloque de columnas.

    - Un solo st.columns(len(modulos)) para que CSS Grid pueda controlar el layout.
    - Escritorio: 6 columnas horizontales.
    - Móvil: 3 columnas compactas (grilla 3xN).
    - CSS inyectado vía st.markdown con @media queries.
    - Botones usan on_click callback (sin st.rerun() manual) para evitar crasheos en móviles.
    """
    if not modulos:
        return

    # CSS Maestro: Grid adaptativo + estética Bento
    if not st.session_state.get("_mc_nav_css_master"):
        st.markdown(
            """
            <style>
            /* ATRAPAR el bloque maestro usando el ANCLA INVISIBLE */
            div[data-testid="stVerticalBlock"]:has(#menu-grilla-maestra) > div[data-testid="stHorizontalBlock"] {
                display: grid !important;
                gap: 8px !important;
                padding: 5px 0 !important;
            }

            /* DESTRUIR el ancho inline que inyecta Streamlit */
            div[data-testid="stVerticalBlock"]:has(#menu-grilla-maestra) > div[data-testid="stHorizontalBlock"] > div[data-testid="column"] {
                width: 100% !important;
                min-width: 100% !important;
                max-width: 100% !important;
                padding: 0 !important;
            }

            /* ESTÉTICA COMÚN (Botones Oscuros Premium) */
            div[data-testid="stVerticalBlock"]:has(#menu-grilla-maestra) button {
                background-color: #1e293b !important;
                border: 1px solid rgba(255,255,255,0.15) !important;
                transition: all 0.2s !important;
            }
            /* Letras blancas forzadas y en una línea */
            div[data-testid="stVerticalBlock"]:has(#menu-grilla-maestra) button * {
                color: #ffffff !important;
                fill: #ffffff !important;
                white-space: nowrap !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
                margin: 0 !important;
            }

            /* VISTA ESCRITORIO (PC) - 6 Columnas Horizontales */
            @media (min-width: 769px) {
                div[data-testid="stVerticalBlock"]:has(#menu-grilla-maestra) > div[data-testid="stHorizontalBlock"] {
                    grid-template-columns: repeat(6, 1fr) !important;
                }
                div[data-testid="stVerticalBlock"]:has(#menu-grilla-maestra) button {
                    height: 55px !important;
                    border-radius: 16px !important;
                    display: flex !important;
                    flex-direction: row !important;
                    align-items: center !important;
                    justify-content: flex-start !important;
                    padding: 0 15px !important;
                }
            }

            /* VISTA MÓVIL (Teléfono) - 3 Columnas Compactas */
            @media (max-width: 768px) {
                div[data-testid="stVerticalBlock"]:has(#menu-grilla-maestra) > div[data-testid="stHorizontalBlock"] {
                    grid-template-columns: repeat(3, 1fr) !important;
                    gap: 5px !important;
                }
                div[data-testid="stVerticalBlock"]:has(#menu-grilla-maestra) button {
                    height: 60px !important;
                    border-radius: 14px !important;
                    display: flex !important;
                    flex-direction: column !important;
                    align-items: center !important;
                    justify-content: center !important;
                    padding: 2px !important;
                }
                div[data-testid="stVerticalBlock"]:has(#menu-grilla-maestra) button p {
                    font-size: 0.65rem !important;
                    margin-top: 3px !important;
                }

                /* Ocultar las flechas nativas (<<) de cerrar sidebar */
                [data-testid="stSidebar"] [aria-label="Collapse sidebar"],
                [data-testid="stSidebar"] button[kind="headerNoPadding"] {
                    display: none !important;
                }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.session_state["_mc_nav_css_master"] = True

    def cambiar_modulo_callback(modulo_seleccionado):
        st.session_state["modulo_actual"] = modulo_seleccionado

    # Ancla invisible para que el CSS atrape el bloque maestro tras cualquier rerun
    st.markdown('<span id="menu-grilla-maestra"></span>', unsafe_allow_html=True)

    cols = st.columns(len(modulos))

    for i, modulo in enumerate(modulos):
        nombre_raw = str(modulo)
        if not nombre_raw:
            continue
        label = (view_nav_labels or {}).get(nombre_raw, nombre_raw)
        icono, texto = _split_icon_label(label)
        btn_label = f"{icono} {texto}".strip()
        tipo = "primary" if nombre_raw == modulo_actual else "secondary"
        with cols[i]:
            st.button(
                btn_label,
                key=f"nav_btn_{nombre_raw}",
                use_container_width=True,
                type=tipo,
                on_click=cambiar_modulo_callback,
                args=(nombre_raw,),
            )


def render_module_nav(menu, vista_actual, view_nav_labels, menu_set=None):
    """Renderiza la navegación de módulos con filtro por categoría + botonera nativa (st.columns)."""
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

    render_modulos_grid(pill_options, default_sel, view_nav_labels)
    return default_sel


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
