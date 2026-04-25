from __future__ import annotations

"""Helpers para la navegación por categorías en el sidebar de módulos."""
from core.module_catalog import categorias_navegacion_sidebar
from core.feature_flags import ALERTAS_APP_PACIENTE_VISIBLE

MC_FILTRO_TODAS = "Todas las áreas"

_CATEGORIAS_MODULOS = None
_CATEGORIAS_ORDEN = None


def _ensure_catalogo() -> None:
    """Inicializa el catálogo de categorías de módulos si aún no está cargado."""
    global _CATEGORIAS_MODULOS, _CATEGORIAS_ORDEN
    if _CATEGORIAS_MODULOS is None:
        _CATEGORIAS_MODULOS = categorias_navegacion_sidebar(alertas_app_visible=ALERTAS_APP_PACIENTE_VISIBLE)
        _CATEGORIAS_ORDEN = list(_CATEGORIAS_MODULOS.keys())


def get_categorias_modulos() -> dict[str, list[str]]:
    """Retorna el diccionario de categorías → lista de módulos."""
    _ensure_catalogo()
    return _CATEGORIAS_MODULOS


def get_categorias_orden() -> list[str]:
    """Retorna la lista ordenada de nombres de categorías."""
    _ensure_catalogo()
    return _CATEGORIAS_ORDEN


def categorias_con_modulos_en_menu(menu_set: set[str] | frozenset[str]) -> list[str]:
    """Retorna categorías que tienen al menos un módulo visible para este usuario."""
    _ensure_catalogo()
    if not menu_set:
        return []
    return [c for c in _CATEGORIAS_ORDEN if any(m in menu_set for m in _CATEGORIAS_MODULOS[c])]


def etiqueta_filtro_categoria(nombre: str) -> str:
    """Retorna una etiqueta con emoji para una categoría de navegación."""
    if nombre == MC_FILTRO_TODAS:
        return f"\U0001F5C2\ufe0f  {nombre}"
    prefijos = {
        "Clínica": "\U0001FA7A",
        "Gestión": "\U0001F4CA",
        "Emergencias": "\U0001F691",
        "Legal y documentación": "\u2696\ufe0f",
    }
    return f"{prefijos.get(nombre, '')}  {nombre}".strip()
