"""
Utilidades de optimización de rendimiento para MediCare Enterprise PRO.
Fase 1: Caché agresivo y gestión de session_state.
"""
from functools import wraps
from typing import Any, Callable, Dict, List, Optional, Set, TypeVar
import time
import inspect

import streamlit as st

F = TypeVar("F", bound=Callable[..., Any])


def track_render_time(func_name: Optional[str] = None):
    """Decorador para trackear tiempo de renderizado de funciones."""
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            name = func_name or func.__name__
            start = time.time()
            result = func(*args, **kwargs)
            elapsed = time.time() - start
            
            # Guardar en session_state para análisis
            key = f"_perf_{name}_last"
            history_key = f"_perf_{name}_history"
            
            st.session_state[key] = elapsed
            
            if history_key not in st.session_state:
                st.session_state[history_key] = []
            st.session_state[history_key].append(elapsed)
            # Mantener solo últimos 10
            st.session_state[history_key] = st.session_state[history_key][-10:]
            
            return result
        return wrapper  # type: ignore[return-value]
    return decorator


def get_render_stats(func_name: str) -> Dict[str, float]:
    """Obtener estadísticas de renderizado de una función."""
    history_key = f"_perf_{func_name}_history"
    history = st.session_state.get(history_key, [])
    
    if not history:
        return {"avg": 0, "min": 0, "max": 0, "count": 0}
    
    return {
        "avg": sum(history) / len(history),
        "min": min(history),
        "max": max(history),
        "count": len(history),
    }


def clear_module_state(module_prefix: str, keep_keys: Optional[Set[str]] = None):
    """
    Limpiar variables de session_state relacionadas con un módulo.
    
    Args:
        module_prefix: Prefijo de las claves a limpiar (ej: "paciente_")
        keep_keys: Set de claves específicas a mantener
    """
    keep = keep_keys or set()
    keys_to_delete = []
    
    for key in st.session_state.keys():
        if key.startswith(module_prefix) and key not in keep:
            # No borrar keys de perf o del sistema
            if not key.startswith("_perf_") and not key.startswith("_mc_"):
                keys_to_delete.append(key)
    
    for key in keys_to_delete:
        del st.session_state[key]
    
    return len(keys_to_delete)


def cleanup_orphan_session_vars():
    """
    Limpiar variables huérfanas de session_state que no se usan en el módulo actual.
    Llamar al cambiar de módulo.
    """
    current_module = st.session_state.get("_current_module", "")
    prev_module = st.session_state.get("_previous_module", "")
    
    if current_module != prev_module and prev_module:
        # Limpiar estado del módulo anterior
        module_prefix = f"{prev_module}_"
        cleared = clear_module_state(module_prefix)
        
        # Limpiar keys específicas de módulos conocidos
        module_specific_keys = {
            "historial": ["_hist_filter_", "_hist_search_", "_hist_page"],
            "paciente": ["_pac_edit_mode", "_pac_temp_data"],
            "evolucion": ["_evo_draft_"],
            "recetas": ["_rec_draft_", "_rec_search"],
        }
        
        if prev_module in module_specific_keys:
            for key_pattern in module_specific_keys[prev_module]:
                for key in list(st.session_state.keys()):
                    if key_pattern in key and not key.startswith("_perf_"):
                        del st.session_state[key]
                        cleared += 1
        
        st.session_state["_cleanup_count"] = st.session_state.get("_cleanup_count", 0) + cleared
    
    # Actualizar módulos
    st.session_state["_previous_module"] = current_module


# ============================================================
# CACHÉ ESPECIALIZADO PARA DATOS CLÍNICOS
# ============================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_cached_catalogos(clinica_id: str) -> Dict[str, List[Dict]]:
    """
    Caché para catálogos estáticos que raramente cambian.
    TTL: 5 minutos
    """
    # Este es un placeholder - los catálogos reales se cargarán desde la BD
    return {
        "medicamentos": [],
        "diagnosticos": [],
        "procedimientos": [],
        "obras_sociales": [],
    }


@st.cache_data(ttl=60, show_spinner=False)
def get_cached_pacientes_resumen(clinica_id: str, limit: int = 100) -> List[Dict]:
    """
    Caché para lista de pacientes (solo datos básicos).
    TTL: 1 minuto
    """
    from core.database import supabase, _supabase_execute_with_retry
    
    if not supabase:
        return []
    
    try:
        response = _supabase_execute_with_retry(
            "get_pacientes_resumen",
            lambda: supabase.table("pacientes")
            .select("id, nombre_completo, dni, obra_social, telefono, estado")
            .eq("empresa_id", clinica_id)
            .order("nombre_completo")
            .limit(limit)
            .execute()
        )
        return response.data if response else []
    except Exception:
        return []


@st.cache_resource(show_spinner=False)
def get_db_connection_pool():
    """
    Caché de recurso para pool de conexiones a la base de datos.
    Mantiene una única instancia durante toda la sesión.
    """
    from core.database import supabase
    return supabase


# ============================================================
# OPTIMIZACIÓN DE RENDERIZADO CONDICIONAL
# ============================================================

def should_rerender(key: str, checksum: Any) -> bool:
    """
    Determinar si un componente necesita re-renderizar basado en checksum.
    
    Args:
        key: Clave única del componente
        checksum: Valor a comparar (hash, timestamp, etc.)
    
    Returns:
        True si necesita re-renderizar, False si el cache es válido
    """
    cache_key = f"_render_cache_{key}"
    prev_checksum = st.session_state.get(cache_key)
    
    if prev_checksum == checksum:
        return False
    
    st.session_state[cache_key] = checksum
    return True


def memoize_component(key: str, render_fn: Callable[[], Any], *deps) -> Any:
    """
    Memoizar un componente de Streamlit basado en dependencias.
    
    Args:
        key: Clave única para el cache
        render_fn: Función que renderiza el componente
        *deps: Dependencias que invalidan el cache al cambiar
    
    Returns:
        Resultado del render_fn (cacheado si deps no cambiaron)
    """
    cache_key = f"_comp_cache_{key}"
    deps_key = f"_comp_deps_{key}"
    
    current_deps = hash(deps)
    prev_deps = st.session_state.get(deps_key)
    
    if current_deps != prev_deps or cache_key not in st.session_state:
        st.session_state[cache_key] = render_fn()
        st.session_state[deps_key] = current_deps
    
    return st.session_state[cache_key]


# ============================================================
# PAGINACIÓN LAZY LOADING
# ============================================================

class Paginator:
    """Paginator para listados grandes con lazy loading."""
    
    def __init__(self, key: str, total_items: int, page_size: int = 20):
        self.key = key
        self.total_items = total_items
        self.page_size = page_size
        self.total_pages = (total_items + page_size - 1) // page_size
        
        # Inicializar estado
        state_key = f"_paginator_{key}"
        if state_key not in st.session_state:
            st.session_state[state_key] = {"page": 0, "loaded_pages": set()}
        self.state = st.session_state[state_key]
    
    @property
    def current_page(self) -> int:
        return self.state["page"]
    
    @property
    def offset(self) -> int:
        return self.current_page * self.page_size
    
    def next_page(self):
        if self.current_page < self.total_pages - 1:
            self.state["page"] += 1
    
    def prev_page(self):
        if self.current_page > 0:
            self.state["page"] -= 1
    
    def go_to_page(self, page: int):
        if 0 <= page < self.total_pages:
            self.state["page"] = page
    
    def render_controls(self):
        """Renderizar controles de paginación en Streamlit."""
        cols = st.columns([1, 3, 1])
        
        with cols[0]:
            if st.button("◀ Anterior", disabled=self.current_page == 0, key=f"{self.key}_prev"):
                self.prev_page()

        with cols[1]:
            st.caption(f"Página {self.current_page + 1} de {self.total_pages} ({self.total_items} items)")

        with cols[2]:
            if st.button("Siguiente ▶", disabled=self.current_page >= self.total_pages - 1, key=f"{self.key}_next"):
                self.next_page()
    
    def get_slice(self, items: List[Any]) -> List[Any]:
        """Obtener slice de items para la página actual."""
        start = self.offset
        end = start + self.page_size
        return items[start:end]


def lazy_load_large_dataset(
    key: str,
    load_fn: Callable[[int, int], List[Any]],
    page_size: int = 50,
    initial_load: int = 100
) -> List[Any]:
    """
    Carga lazy de datasets grandes con scroll infinito simulado.
    
    Args:
        key: Clave única para el dataset
        load_fn: Función que carga datos (offset, limit) -> List
        page_size: Tamaño de página para carga incremental
        initial_load: Cantidad inicial a cargar
    
    Returns:
        Lista de items cargados
    """
    state_key = f"_lazy_load_{key}"
    
    if state_key not in st.session_state:
        # Carga inicial
        st.session_state[state_key] = {
            "items": load_fn(0, initial_load),
            "offset": initial_load,
            "has_more": True,
            "loading": False,
        }
    
    state = st.session_state[state_key]
    
    # Botón "Cargar más" si hay más datos
    if state["has_more"] and not state["loading"]:
        if st.button(f"📥 Cargar más {key}...", key=f"{key}_load_more"):
            state["loading"] = True
            new_items = load_fn(state["offset"], page_size)
            if new_items:
                state["items"].extend(new_items)
                state["offset"] += len(new_items)
                state["has_more"] = len(new_items) == page_size
            else:
                state["has_more"] = False
            state["loading"] = False

    return state["items"]
