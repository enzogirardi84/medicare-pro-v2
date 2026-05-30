"""Router de vistas optimizado con Registry Pattern y lazy loading.
Carga UNICAMENTE el modulo activo en memoria.
Libera ramas muertas para el garbage collector.
50 modulos sin degradar el arbol de compilacion de Streamlit.
"""
from __future__ import annotations

import sys
import time
from functools import lru_cache
from html import escape
from importlib import import_module
from pathlib import Path
from typing import Any, Callable, Optional

import streamlit as st

from core.app_logging import log_event
from core.perf_metrics import record_perf


# ═══════════════════════════════════════════════════════════════════
# 1. REGISTRY DE MODULOS
# ═══════════════════════════════════════════════════════════════════

class ModuleRegistry:
    """Registry de modulos con lazy loading y cache LRU.

    Cada modulo se importa SOLO cuando se solicita por primera vez.
    La cache LRU mantiene los ultimos 5 modulos en memoria.
    """

    def __init__(self):
        self._registro: dict[str, tuple[str, str]] = {}
        # Cache: ultimos 5 modulos usados (LRU)
        self._cache_lru: dict[str, Callable] = {}
        self._orden_uso: list[str] = []
        self._max_cache = 5

    def registrar_modulo(self, nombre: str, module_path: str, function_name: str) -> None:
        """Registra un modulo en el registry.

        Args:
            nombre: Nombre visible del modulo (ej. "Dashboard").
            module_path: Ruta del modulo (ej. "views.dashboard").
            function_name: Nombre de la funcion render (ej. "render_dashboard").
        """
        self._registro[nombre] = (module_path, function_name)

    def obtener_modulo(self, nombre: str) -> Optional[Callable]:
        """Obtiene la funcion render de un modulo con lazy loading + cache LRU.

        Si el modulo ya esta en cache, lo retorna inmediatamente.
        Si no, lo importa, lo cachea y retorna.
        Si excede el maximo de cache, elimina el menos usado.
        """
        if nombre not in self._registro:
            log_event("router", f"modulo_no_registrado:{nombre}")
            return None

        # Cache hit
        if nombre in self._cache_lru:
            self._actualizar_orden(nombre)
            return self._cache_lru[nombre]

        # Lazy load
        module_path, function_name = self._registro[nombre]
        try:
            mod = import_module(module_path)
            fn = getattr(mod, function_name)
            self._cache_lru[nombre] = fn
            self._actualizar_orden(nombre)
            log_event("router", f"lazy_load:{module_path}.{function_name}")

            # LRU eviction
            if len(self._cache_lru) > self._max_cache:
                menos_usado = self._orden_uso.pop(0)
                self._cache_lru.pop(menos_usado, None)
                log_event("router", f"lru_evict:{menos_usado}")

            return fn
        except Exception as exc:
            log_event("router", f"load_error:{module_path}:{type(exc).__name__}:{exc}")
            return None

    def _actualizar_orden(self, nombre: str) -> None:
        if nombre in self._orden_uso:
            self._orden_uso.remove(nombre)
        self._orden_uso.append(nombre)

    @property
    def modulos_disponibles(self) -> list[str]:
        return list(self._registro.keys())

    @property
    def cache_actual(self) -> list[str]:
        return list(self._cache_lru.keys())

    def limpiar_cache(self) -> None:
        self._cache_lru.clear()
        self._orden_uso.clear()


# ═══════════════════════════════════════════════════════════════════
# 2. RENDERIZADOR DE TARJETAS DE NAVEGACION
# ═══════════════════════════════════════════════════════════════════

def render_nav_pills(modulos_disponibles: list[str], vista_actual: str) -> str:
    """Renderiza navegacion tipo pills como HTML liviano.

    Reemplaza widgets nativos de Streamlit para evitar rerenders.
    Solo se actualiza cuando el usuario hace click (navegacion completa).
    """
    html = '<div style="display:flex;flex-wrap:wrap;gap:6px;padding:4px 0;">'
    for mod in modulos_disponibles:
        activo = mod == vista_actual
        bg = "rgba(14,165,233,0.15)" if activo else "rgba(15,23,42,0.5)"
        color = "#38bdf8" if activo else "#e2e8f0"
        border = "1px solid rgba(14,165,233,0.3)" if activo else "1px solid rgba(51,65,85,0.3)"
        html += (
            f'<a href="?modulo={escape(mod)}" '
            f'style="display:inline-flex;align-items:center;padding:8px 16px;'
            f'border-radius:9999px;background:{bg};color:{color};'
            f'border:{border};font-size:0.82rem;font-weight:600;'
            f'text-decoration:none;transition:all 0.15s;'
            f'min-height:38px;">{escape(mod)}</a>'
        )
    html += "</div>"
    return html


# ═══════════════════════════════════════════════════════════════════
# 3. TABLA HTML LIVIANA (reemplazo de st.dataframe para movil)
# ═══════════════════════════════════════════════════════════════════

def render_tabla_liviana(data: list[dict[str, Any]], max_filas: int = 25) -> str:
    """Renderiza una tabla HTML liviana y scrolleable.

    Reemplaza st.dataframe cuando hay datos voluminosos en movil.
    No crea canvas nativo, solo DOM HTML -> menos memoria y GPU.

    Args:
        data: Lista de diccionarios con los datos.
        max_filas: Maximo de filas a mostrar.

    Returns:
        HTML de la tabla.
    """
    if not data:
        return "<p style='color:#94a3b8;font-size:0.85rem;'>Sin datos</p>"

    rows = data[:max_filas]
    columns = list(rows[0].keys())

    html = (
        '<div style="overflow-x:auto;border:1px solid rgba(100,180,255,0.06);'
        'border-radius:12px;">'
        '<table style="width:100%;border-collapse:collapse;font-size:0.82rem;'
        'white-space:nowrap;">'
        '<thead><tr>'
    )
    for col in columns:
        html += f'<th style="padding:10px 12px;background:rgba(14,165,233,0.04);'
        html += f'border-bottom:1px solid rgba(100,180,255,0.08);'
        html += f'color:#c0d8e8;font-weight:700;text-align:left;">{escape(str(col))}</th>'
    html += '</tr></thead><tbody>'

    for row in rows:
        html += '<tr>'
        for col in columns:
            val = str(row.get(col, ""))
            html += f'<td style="padding:8px 12px;border-bottom:1px solid rgba(100,180,255,0.04);'
            html += f'color:#e2e8f0;">{escape(val)}</td>'
        html += '</tr>'
    html += '</tbody></table></div>'

    if len(data) > max_filas:
        html += f'<p style="color:#94a3b8;font-size:0.78rem;margin:6px 0;">'
        html += f'Mostrando {max_filas} de {len(data)} registros</p>'

    return html


# ═══════════════════════════════════════════════════════════════════
# 4. RENDERIZADOR PRINCIPAL
# ═══════════════════════════════════════════════════════════════════

_registry: Optional[ModuleRegistry] = None


def get_registry() -> ModuleRegistry:
    """Singleton del registry."""
    global _registry
    if _registry is None:
        _registry = ModuleRegistry()
    return _registry


def render_vista(vista_actual: str, **kwargs: Any) -> None:
    """Renderiza la vista activa usando el router lazy.

    Args:
        vista_actual: Nombre del modulo a renderizar.
        **kwargs: Argumentos para la funcion render (paciente_sel, mi_empresa, etc).
    """
    registry = get_registry()
    t0 = time.monotonic()
    ok = True

    try:
        render_fn = registry.obtener_modulo(vista_actual)
        if render_fn is None:
            st.error(f"Modulo '{vista_actual}' no encontrado")
            log_event("router", f"render_error:modulo_no_encontrado:{vista_actual}")
            return

        render_fn(**kwargs)

    except Exception as exc:
        ok = False
        log_event("router", f"render_exception:{vista_actual}:{type(exc).__name__}:{exc}")
        st.error(f"Error al cargar {vista_actual}")
        if st.session_state.get("_debug_mode"):
            with st.expander("Detalle"):
                st.code(f"{type(exc).__name__}: {exc}", language="text")

    finally:
        dt = (time.monotonic() - t0) * 1000
        record_perf(f"router.{vista_actual}", dt, ok=ok)
