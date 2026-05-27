"""Navegación de módulos: query params, acordeón por categorías, resolución de vistas.

Consolida lo que antes estaba duplicado entre main.py y core/view_dispatch.py.
"""
from __future__ import annotations

from importlib import import_module

import streamlit as st

from core.app_logging import log_event
from core.nav_helpers import (
    categorias_con_modulos_en_menu,
    get_categorias_modulos,
    obtener_subgrupos_categoria,
)
from core.user_feedback import render_carga_modulo_fallo, render_modulo_fallo_ui
from core.view_helpers import aplicar_compactacion_movil_por_vista

_VIEW_FN_CACHE: dict = {}

_CATEGORY_EMOJIS = {
    "Clínica": "\U0001FA7A",
    "Gestión": "\U0001F4CA",
    "Emergencias": "\U0001F691",
    "Legal y documentación": "\u2696\ufe0f",
}


def _colapsar_todas_categorias():
    for cat in list(_CATEGORY_EMOJIS.keys()):
        st.session_state[f"_nav_cat_{cat}"] = False


def set_modulo_actual(modulo_seleccionado, rerun=False):
    """Actualiza el modulo activo y preserva el anterior para atajos de vuelta."""
    modulo_nuevo = str(modulo_seleccionado or "").strip()
    if not modulo_nuevo:
        return

    modulo_actual = st.session_state.get("modulo_actual")
    if modulo_actual == modulo_nuevo:
        return

    if modulo_actual:
        st.session_state["modulo_anterior"] = modulo_actual
    st.session_state["modulo_actual"] = modulo_nuevo

    # Cerrar cortina de navegacion si estaba abierta
    st.session_state.pop("_show_nav_cortina", None)
    # Colapsar todas las categorias
    _colapsar_todas_categorias()

    if rerun:
        st.rerun()


_set_modulo_actual = set_modulo_actual


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
            try:
                del st.query_params["modulo"]
            except Exception:
                pass
            return
        if st.session_state.get("modulo_actual") == modulo_nuevo:
            try:
                del st.query_params["modulo"]
            except Exception:
                pass
            return
        set_modulo_actual(modulo_nuevo)
        try:
            del st.query_params["modulo"]
        except Exception:
            pass
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


from streamlit import fragment as st_fragment


# ── Grilla de botones (3 columnas, más equilibrada dentro del acordeón) ──────

_NAV_COLS = 3


def _nav_select_y_colapsar(modulo):
    """Selecciona un módulo (el colapso de categorias esta en set_modulo_actual)."""
    set_modulo_actual(modulo, rerun=True)


def render_modulos_grid(modulos, modulo_actual=None, view_nav_labels=None):
    """Renderiza una grilla compacta de botones de módulos.

    Expuesta públicamente para tests. Usa 3 columnas para una distribución
    más equilibrada dentro de los expanders.
    """
    if not modulos:
        return
    for i in range(0, len(modulos), _NAV_COLS):
        fila = modulos[i:i + _NAV_COLS]
        cols = st.columns(_NAV_COLS)
        for j, modulo in enumerate(fila):
            nombre_raw = str(modulo)
            if not nombre_raw:
                continue
            label = (view_nav_labels or {}).get(nombre_raw, nombre_raw)
            icono, texto = _split_icon_label(label)
            tipo = "primary" if nombre_raw == modulo_actual else "secondary"
            with cols[j]:
                if st.button(
                    f"{icono} {texto}",
                    key=f"nav_g_{nombre_raw}",
                    width='stretch',
                    type=tipo,
                ):
                    set_modulo_actual(nombre_raw, rerun=True)


def _render_modulos_sub(modulos, modulo_actual=None, view_nav_labels=None):
    """Versión interna con 3 columnas (2 en mobile) para el acordeón."""
    if not modulos:
        return
    _mobile = st.session_state.get("mc_liviano_modo") == "on" or st.session_state.get("_mc_liviano_activo")
    _cols = 2 if _mobile else _NAV_COLS
    for i in range(0, len(modulos), _cols):
        fila = modulos[i:i + _cols]
        cols = st.columns(_cols)
        for j, modulo in enumerate(fila):
            nombre_raw = str(modulo)
            if not nombre_raw:
                continue
            label = (view_nav_labels or {}).get(nombre_raw, nombre_raw)
            icono, texto = _split_icon_label(label)
            tipo = "primary" if nombre_raw == modulo_actual else "secondary"
            with cols[j]:
                if st.button(
                    f"{icono} {texto}",
                    key=f"nav_a_{nombre_raw}",
                    width='stretch',
                    type=tipo,
                ):
                    _nav_select_y_colapsar(nombre_raw)


# ── Render principal (acordeón igual en desktop y móvil) ─────────────────


def render_module_nav(menu, vista_actual, view_nav_labels, menu_set=None):
    """
    Renderiza la navegación de módulos como acordeón por categorías.

    Desktop y móvil comparten el mismo acordeón. Cada categoría es un
    ``st.expander``. Solo la categoría activa aparece expandida en la primera
    carga; al hacer clic en un módulo todas colapsan (experiencia premium).
    """
    if not menu:
        return None
    menu_set = frozenset(menu) if menu_set is None else menu_set

    opciones_menu = [m for m in menu if m in menu_set]
    if not opciones_menu:
        return vista_actual

    cats_ok = categorias_con_modulos_en_menu(menu_set)
    if not cats_ok:
        return st.session_state.get("modulo_actual", vista_actual)

    categorias_modulos = get_categorias_modulos()

    cat_activa = next(
        (c for c, mods in categorias_modulos.items() if vista_actual in mods),
        None,
    )

    _mobile = st.session_state.get("mc_liviano_modo") == "on" or st.session_state.get("_mc_liviano_activo")

    for cat in cats_ok:
        mods_in_cat = [m for m in categorias_modulos.get(cat, []) if m in menu_set]
        if not mods_in_cat:
            continue

        emoji = _CATEGORY_EMOJIS.get(cat, "\U0001F4CB")
        label = f"{emoji}  {cat}"
        cat_key = f"_nav_cat_{cat}"

        if cat_key not in st.session_state:
            st.session_state[cat_key] = not _mobile and (cat == cat_activa) and (st.session_state.get("modulo_actual") is None)

        is_open = st.session_state.get(cat_key, False)
        arrow = "▼" if is_open else "▶"
        if st.button(f"{arrow} {label}", key=f"_nav_btn_{cat}", use_container_width=True):
            st.session_state[cat_key] = not is_open
            st.rerun()

        if is_open:
            todos = [
                m
                for sg in obtener_subgrupos_categoria(cat).values()
                for m in sg
                if m in menu_set
            ] or mods_in_cat
            if todos:
                _render_modulos_sub(todos, vista_actual, view_nav_labels)

    return st.session_state.get("modulo_actual", vista_actual)


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
    fn = _VIEW_FN_CACHE[tab_name]
    # Verificar que la referencia en cache siga siendo válida (protección ante re-deploys en caliente)
    if not callable(fn):
        _VIEW_FN_CACHE.pop(tab_name, None)
        return _get_render_fn(tab_name, view_config)
    return fn


def render_current_view(tab_name, paciente_sel, mi_empresa, user, rol, view_config, menu_set=None):
    """Renderiza la vista activa. Captura errores y muestra UI de fallback."""
    if menu_set is None:
        menu_set = frozenset(resolve_menu_for_role(rol, user, view_config))
    if tab_name not in menu_set:
        log_event("app_navigation", "error: No tienes permisos para acceder a este modulo.")
        st.error("No tienes permisos para acceder a este modulo.")
        return

    # Barra de navegación rápida (breadcrumb)
    try:
        _mod_ant = st.session_state.get("modulo_anterior", "")
        if _mod_ant and _mod_ant != tab_name:
            _crumbs = st.columns([5, 1])
            with _crumbs[0]:
                st.caption(f"📍 {tab_name}")
            with _crumbs[1]:
                if st.button(f"← Volver a {_mod_ant[:20]}", key="nav_volver", use_container_width=True):
                    set_modulo_actual(_mod_ant, rerun=True)
            st.divider()
    except Exception as _e_bread:
        log_event("app_navigation", f"breadcrumb_fallo:{type(_e_bread).__name__}")

    try:
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
        elif tab_name in ("Estadisticas", "Turnos Online"):
            render_fn(mi_empresa, rol)
        elif tab_name == "Percentilo":
            render_fn(paciente_sel, user)
        elif tab_name in ("Cierre Diario", "Auditoria", "Auditoria Legal", "Documentos Legales", "Asistencia en Vivo"):
            render_fn(mi_empresa, user)
        elif tab_name == "RRHH y Fichajes":
            render_fn(mi_empresa, rol, user)
        elif tab_name == "Proyecto y Roadmap":
            render_fn(mi_empresa, user, rol)
        elif tab_name == "Diagnosticos":
            render_fn(user)
        elif tab_name == "Reportes Financieros":
            render_fn(mi_empresa, rol)
        elif tab_name == "Admin Feature Flags":
            render_fn()
        elif tab_name == "Self-Healing IA":
            render_fn(paciente_sel, mi_empresa, user, rol)
        elif tab_name == "Asistente IA":
            render_fn(paciente_sel, mi_empresa, user, rol)
        elif tab_name == "APS / Dispensario":
            render_fn(paciente_sel, mi_empresa, user, rol)
        elif tab_name == "Vacunacion":
            render_fn(paciente_sel, mi_empresa, user, rol)
        elif tab_name == "Chatbot IA":
            render_fn(paciente_sel, mi_empresa, user, rol)
        elif tab_name == "Calc. Dosis Pediatricas":
            render_fn(paciente_sel, mi_empresa, user, rol)
        else:
            render_fn(paciente_sel, mi_empresa, user, rol)
    except Exception as exc:
        # Fix 2026-05-14 anti-pantalla-azul: bloque visible aunque showErrorDetails=False
        import traceback as _tb
        log_event("ui", "modulo_fallo:" + tab_name + ":" + type(exc).__name__ + ":" + str(exc))
        try:
            from core.error_tracker import report_exception
            report_exception(
                module="navigation." + tab_name,
                exc_info=exc,
                context="render_current_view tab_name=" + tab_name,
                severity="error",
            )
        except Exception:
            pass
        _html_aviso = (
            "<div style=\"background:#fff;color:#0f172a;padding:14px 18px;"
            "border-left:4px solid #dc2626;border-radius:6px;margin:10px 0;\">"
            "<strong style=\"color:#dc2626;\">Error al cargar el modulo</strong>"
            "<br><span style=\"font-size:.9em;\">"
            "Reporta esto al admin con la hora exacta. Detalle tecnico abajo."
            "</span></div>"
        )
        st.markdown(_html_aviso, unsafe_allow_html=True)
        st.error("Error en modulo **" + tab_name + "**: " + type(exc).__name__)
        try:
            render_modulo_fallo_ui(tab_name, exc)
        except Exception:
            pass
