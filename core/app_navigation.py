"""Navegación de módulos: query params, acordeón por categorías, resolución de vistas.

Consolida lo que antes estaba duplicado entre main.py y core/view_dispatch.py.
"""

import html
from html import escape as html_escape
from importlib import import_module
from urllib.parse import quote_plus

import streamlit as st

from core.app_logging import log_event
from core.app_mobile import cliente_es_movil_probable
from core.nav_helpers import (
    categorias_con_modulos_en_menu,
    get_categorias_modulos,
    modulos_en_categoria,
    obtener_subgrupos_categoria,
)
from core.user_feedback import render_carga_modulo_fallo, render_modulo_fallo_ui

_VIEW_FN_CACHE: dict = {}

_CATEGORY_EMOJIS = {
    "Clínica": "\U0001FA7A",
    "Gestión": "\U0001F4CA",
    "Emergencias": "\U0001F691",
    "Legal y documentación": "\u2696\ufe0f",
}


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


from streamlit import fragment as st_fragment


# ── Grilla de botones (3 columnas, más equilibrada dentro del acordeón) ──────

_NAV_COLS = 3


def _nav_select_y_colapsar(modulo):
    """Selecciona un módulo y fuerza el colapso de todas las cortinas."""
    set_modulo_actual(modulo)
    st.session_state["_nav_version"] = st.session_state.get("_nav_version", 0) + 1


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
                st.button(
                    f"{icono} {texto}",
                    key=f"nav_g_{nombre_raw}",
                    use_container_width=True,
                    type=tipo,
                    on_click=set_modulo_actual,
                    args=(nombre_raw,),
                )


def _render_modulos_sub(modulos, modulo_actual=None, view_nav_labels=None):
    """Versión interna con 3 columnas para el acordeón (colapsa al hacer clic)."""
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
                st.button(
                    f"{icono} {texto}",
                    key=f"nav_a_{nombre_raw}",
                    use_container_width=True,
                    type=tipo,
                    on_click=_nav_select_y_colapsar,
                    args=(nombre_raw,),
                )


def _render_modulos_mobile(modulos, modulo_actual=None, view_nav_labels=None):
    """Móvil: popover o expander con botones en grilla 3 columnas."""
    if not modulos:
        return
    if hasattr(st, "popover"):
        with st.popover("Menú de módulos", width='stretch'):
            for i in range(0, len(modulos), 3):
                fila = modulos[i:i + 3]
                cols = st.columns(3)
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
                            key=f"nav_pop_{nombre_raw}",
                            use_container_width=True,
                            type=tipo,
                        ):
                            set_modulo_actual(nombre_raw, rerun=True)
        return

    if "menu_nav_abierto" not in st.session_state:
        st.session_state["menu_nav_abierto"] = False

    def cambiar_modulo_mobile(mod_seleccionado):
        set_modulo_actual(mod_seleccionado)
        st.session_state["menu_nav_abierto"] = False

    with st.expander("Menú de módulos", expanded=st.session_state["menu_nav_abierto"]):
        for i in range(0, len(modulos), 3):
            fila = modulos[i:i + 3]
            cols = st.columns(3)
            for j, modulo in enumerate(fila):
                nombre_raw = str(modulo)
                if not nombre_raw:
                    continue
                label = (view_nav_labels or {}).get(nombre_raw, nombre_raw)
                icono, texto = _split_icon_label(label)
                tipo = "primary" if nombre_raw == modulo_actual else "secondary"
                with cols[j]:
                    st.button(
                        f"{icono} {texto}",
                        key=f"nav_exp_{nombre_raw}",
                        use_container_width=True,
                        type=tipo,
                        on_click=cambiar_modulo_mobile,
                        args=(nombre_raw,),
                    )


# ── Render principal (acordeón en desktop, popover en móvil) ─────────────────


def render_module_nav(menu, vista_actual, view_nav_labels, menu_set=None):
    """
    Renderiza la navegación de módulos como acordeón por categorías.

    - Escritorio: cada categoría es un ``st.expander``. Solo la categoría activa
      aparece expandida. Dentro se muestran sub‑grupos (``st.caption``) y botones.
    - Móvil: popover único con lista vertical.
    """
    if not menu:
        return None
    menu_set = frozenset(menu) if menu_set is None else menu_set

    # ── Móvil ──
    if cliente_es_movil_probable():
        _render_modulos_mobile(menu, vista_actual, view_nav_labels)
        return st.session_state.get("modulo_actual", vista_actual)

    # ── Desktop: acordeón ──
    cats_ok = categorias_con_modulos_en_menu(menu_set)
    if not cats_ok:
        return vista_actual

    categorias_modulos = get_categorias_modulos()

    cat_activa = next(
        (c for c, mods in categorias_modulos.items() if vista_actual in mods),
        None,
    )

    # Versión: al hacer clic en un módulo se incrementa, forzando nuevas
    # claves de expander que arrancan colapsadas (experiencia premium).
    nav_version = st.session_state.get("_nav_version", 0)
    primera_vez = (nav_version == 0)

    for cat in cats_ok:
        mods_in_cat = [m for m in categorias_modulos.get(cat, []) if m in menu_set]
        if not mods_in_cat:
            continue

        emoji = _CATEGORY_EMOJIS.get(cat, "\U0001F4CB")
        label = f"{emoji}  {cat}"
        expandido = primera_vez and (cat == cat_activa)

        with st.expander(
            label, expanded=expandido, key=f"_nav_e_{cat}_{nav_version}"
        ):
            todos = [
                m
                for sg in obtener_subgrupos_categoria(cat).values()
                for m in sg
                if m in menu_set
            ] or mods_in_cat
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
        elif tab_name in ("Estadisticas", "Turnos Online"):
            render_fn(mi_empresa, rol)
        elif tab_name == "Percentilo":
            render_fn(paciente_sel, user)
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
        st.error("Error en modulo **" + tab_name + "**: " + type(exc).__name__ + ": " + str(exc))
        with st.expander("Detalle tecnico (para soporte)"):
            st.code("".join(_tb.format_exception(type(exc), exc, exc.__traceback__)), language="python")
        try:
            render_modulo_fallo_ui(tab_name, exc)
        except Exception:
            pass
