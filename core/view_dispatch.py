"""Compatibilidad: despacho de vistas y navegación.

Las implementaciones vivas se mudaron a core/app_navigation.py.
Este módulo re-exporta para no romper imports existentes.
"""
from core.app_navigation import (  # noqa: F401
    _get_render_fn,
    _split_icon_label,
    procesar_query_params_navegacion,
    render_current_view,
    render_modulos_grid,
    render_module_nav,
    resolve_current_view,
    resolve_menu_for_role,
)
