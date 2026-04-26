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
    """Renderiza la navegación de módulos usando chunking nativo (st.columns + st.button).

    - PC: 6 botones por fila nativa de Streamlit.
    - Móvil: 3 botones por fila para evitar saturación del DOM.
    - Sin CSS Grid / Flexbox agresivo sobre stHorizontalBlock.
    - Usa on_click callback (sin st.rerun() manual) para evitar desconexión de websocket.
    """
    from core.app_mobile import cliente_es_movil_probable

    if not modulos:
        return

    es_movil = cliente_es_movil_probable()
    columnas_por_fila = 3 if es_movil else 6

    # CSS: fuerza horizontalidad en móviles para filas de 3 columnas
    if not st.session_state.get("_mc_nav_btn_css_inyectado"):
        st.markdown(
            """
            <style>
            div[data-testid="stButton"] > button {
                border-radius: 12px;
                min-height: 55px;
                white-space: pre-wrap !important;
            }
            @media (max-width: 768px) {
                div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(3):last-child) {
                    display: flex !important;
                    flex-direction: row !important;
                    flex-wrap: nowrap !important;
                    gap: 4px !important;
                }
                div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(3):last-child) > div[data-testid="column"] {
                    width: 33.33% !important;
                    min-width: 33.33% !important;
                    max-width: 33.33% !important;
                    flex: 1 1 33.33% !important;
                    padding: 0 !important;
                }
                div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(3):last-child) div[data-testid="stButton"] > button {
                    width: 100% !important;
                    min-height: 50px !important;
                    height: 100% !important;
                    padding: 2px !important;
                    font-size: 0.65rem !important;
                    white-space: pre-wrap !important;
                    line-height: 1.1 !important;
                    display: flex !important;
                    flex-direction: column !important;
                    justify-content: center !important;
                    align-items: center !important;
                    border-radius: 12px !important;
                }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.session_state["_mc_nav_btn_css_inyectado"] = True

    for i in range(0, len(modulos), columnas_por_fila):
        fila_modulos = modulos[i : i + columnas_por_fila]
        cols = st.columns(columnas_por_fila)
        for j, modulo in enumerate(fila_modulos):
            nombre_raw = str(modulo)
            if not nombre_raw:
                continue
            label = (view_nav_labels or {}).get(nombre_raw, nombre_raw)
            icono, texto = _split_icon_label(label)
            btn_label = f"{icono} {texto}".strip()
            tipo = "primary" if nombre_raw == modulo_actual else "secondary"
            with cols[j]:
                st.button(
                    btn_label,
                    key=f"nav_grid_{nombre_raw}",
                    use_container_width=True,
                    type=tipo,
                    on_click=lambda m=nombre_raw: st.session_state.__setitem__("modulo_actual", m),
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
