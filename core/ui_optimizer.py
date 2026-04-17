"""
Optimizador de UI para mejor performance y experiencia de usuario.

- Virtualización de listas grandes
- Lazy loading de componentes
- Debouncing de inputs
- Throttling de eventos
- Optimización de re-renders
"""

from __future__ import annotations

import functools
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, TypeVar, Generic

import streamlit as st

T = TypeVar('T')


class Debouncer:
    """
    Debouncer para inputs de usuario.
    
    Espera a que el usuario deje de escribir antes de ejecutar.
    """

    def __init__(self, wait_seconds: float = 0.3):
        self.wait = wait_seconds
        self._timer: Optional[threading.Timer] = None
        self._lock = threading.Lock()

    def debounce(self, func: Callable) -> Callable:
        """Decorador para debouncear una función."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self._lock:
                if self._timer:
                    self._timer.cancel()
                
                self._timer = threading.Timer(self.wait, func, args, kwargs)
                self._timer.start()
        
        return wrapper


class Throttler:
    """
    Throttler para limitar frecuencia de ejecución.
    
    Útil para scroll, resize, y eventos frecuentes.
    """

    def __init__(self, limit_seconds: float = 0.1):
        self.limit = limit_seconds
        self._last_run = 0.0
        self._lock = threading.Lock()

    def throttle(self, func: Callable) -> Callable:
        """Decorador para throttlear una función."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            with self._lock:
                now = time.time()
                if now - self._last_run >= self.limit:
                    self._last_run = now
                    return func(*args, **kwargs)
        
        return wrapper


@dataclass
class VirtualListState:
    """Estado de lista virtualizada."""
    item_height: int = 50
    viewport_height: int = 400
    scroll_position: int = 0
    buffer_items: int = 5
    total_items: int = 0

    @property
    def visible_count(self) -> int:
        """Cantidad de items visibles."""
        return (self.viewport_height // self.item_height) + (2 * self.buffer_items)

    @property
    def start_index(self) -> int:
        """Índice de inicio de items visibles."""
        return max(0, (self.scroll_position // self.item_height) - self.buffer_items)

    @property
    def end_index(self) -> int:
        """Índice de fin de items visibles."""
        return min(self.total_items, self.start_index + self.visible_count)


class VirtualListRenderer:
    """
    Renderizador de listas virtualizadas para grandes datasets.
    
    Solo renderiza los items visibles + buffer.
    """

    def __init__(self, container_key: str):
        self.key = container_key
        self._state_key = f"_virtual_list_{container_key}"

    def _get_state(self) -> VirtualListState:
        """Obtiene estado de la lista virtualizada."""
        if self._state_key not in st.session_state:
            st.session_state[self._state_key] = VirtualListState()
        return st.session_state[self._state_key]

    def render(
        self,
        items: List[T],
        render_item: Callable[[T, int], Any],
        item_height: int = 50,
        viewport_height: int = 400,
    ) -> List[Any]:
        """
        Renderiza solo los items visibles.
        
        Args:
            items: Lista completa de items
            render_item: Función (item, index) -> widget
            item_height: Altura de cada item en píxeles
            viewport_height: Altura del viewport visible
        
        Returns:
            Lista de widgets renderizados
        """
        state = self._get_state()
        state.total_items = len(items)
        state.item_height = item_height
        state.viewport_height = viewport_height

        # Calcular rango visible
        start = state.start_index
        end = state.end_index

        # Espaciador superior (para scroll)
        top_spacer = start * item_height
        
        # Renderizar items visibles
        rendered = []
        
        if top_spacer > 0:
            st.markdown(
                f"<div style='height:{top_spacer}px'></div>",
                unsafe_allow_html=True
            )

        for i in range(start, end):
            if i < len(items):
                rendered.append(render_item(items[i], i))

        # Espaciador inferior
        bottom_spacer = (len(items) - end) * item_height
        if bottom_spacer > 0:
            st.markdown(
                f"<div style='height:{bottom_spacer}px'></div>",
                unsafe_allow_html=True
            )

        return rendered

    def update_scroll(self, scroll_position: int):
        """Actualiza posición de scroll."""
        state = self._get_state()
        state.scroll_position = scroll_position

    def get_visible_range(self) -> Tuple[int, int]:
        """Retorna rango de índices visibles."""
        state = self._get_state()
        return (state.start_index, state.end_index)


class LazyComponentLoader:
    """
    Cargador lazy de componentes pesados.
    
    Retrasa la carga hasta que sean necesarios.
    """

    def __init__(self):
        self._loaded: Dict[str, bool] = {}
        self._components: Dict[str, Callable[[], Any]] = {}

    def register(self, key: str, loader: Callable[[], Any]):
        """Registra un componente para carga lazy."""
        self._components[key] = loader

    def load(self, key: str, force: bool = False) -> Optional[Any]:
        """Carga un componente si no está cargado."""
        if key in self._loaded and not force:
            return None
        
        loader = self._components.get(key)
        if loader:
            self._loaded[key] = True
            return loader()
        return None

    def is_loaded(self, key: str) -> bool:
        """Verifica si un componente está cargado."""
        return self._loaded.get(key, False)

    def unload(self, key: str):
        """Marca un componente como no cargado."""
        self._loaded.pop(key, None)


class RenderOptimizer:
    """
    Optimizador de re-renders de Streamlit.
    
    Previende re-renders innecesarios usando cacheo de estado.
    """

    def __init__(self, key_prefix: str):
        self.prefix = key_prefix
        self._state_key = f"_render_opt_{key_prefix}"

    def should_render(self, *args, **kwargs) -> bool:
        """
        Determina si se debe renderizar basado en cambios.
        
        Compara hash de argumentos con la última ejecución.
        """
        import hashlib
        import json

        # Crear hash de argumentos
        data = json.dumps({"args": args, "kwargs": kwargs}, sort_keys=True, default=str)
        current_hash = hashlib.md5(data.encode()).hexdigest()

        # Verificar si cambió
        state_key = f"{self._state_key}_last_hash"
        if state_key in st.session_state:
            if st.session_state[state_key] == current_hash:
                return False  # No hay cambios, no renderizar

        st.session_state[state_key] = current_hash
        return True

    def memoize(self, func: Callable) -> Callable:
        """Decorador para memoizar un componente."""
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            if self.should_render(*args, **kwargs):
                return func(*args, **kwargs)
            return None
        return wrapper


class InputOptimizer:
    """
    Optimizador de inputs de usuario.
    
    Reduce latencia y mejora UX.
    """

    def __init__(self):
        self._pending_updates: Dict[str, Any] = {}
        self._debouncer = Debouncer(0.2)

    def optimized_text_input(
        self,
        label: str,
        key: str,
        value: str = "",
        on_change: Optional[Callable] = None,
        **kwargs
    ) -> str:
        """
        Text input con debouncing automático.
        """
        # Session key para valor debounced
        debounced_key = f"{key}_debounced"
        
        # Crear input
        current = st.text_input(
            label,
            value=value,
            key=key,
            **kwargs
        )

        # Aplicar debounce
        if current != st.session_state.get(debounced_key, value):
            self._debouncer.debounce(
                lambda: self._commit_change(key, debounced_key, current, on_change)
            )()

        return st.session_state.get(debounced_key, current)

    def _commit_change(self, key: str, debounced_key: str, value: Any, callback: Optional[Callable]):
        """Aplica cambio debounced."""
        st.session_state[debounced_key] = value
        if callback:
            callback(value)

    def search_input(
        self,
        label: str,
        key: str,
        search_fn: Callable[[str], List[T]],
        result_renderer: Callable[[T], Any],
        debounce_ms: float = 300,
    ) -> Optional[T]:
        """
        Input de búsqueda con resultados en tiempo real.
        """
        import time

        query = st.text_input(label, key=key)
        
        # Debounce manual
        last_query_key = f"{key}_last_query"
        last_time_key = f"{key}_last_time"
        results_key = f"{key}_results"
        
        now = time.time()
        last_time = st.session_state.get(last_time_key, 0)
        
        if query != st.session_state.get(last_query_key, ""):
            if now - last_time >= debounce_ms / 1000:
                # Ejecutar búsqueda
                results = search_fn(query)
                st.session_state[results_key] = results
                st.session_state[last_query_key] = query
                st.session_state[last_time_key] = now

        # Mostrar resultados
        results = st.session_state.get(results_key, [])
        if results:
            selected = st.selectbox(
                "Resultados",
                options=results,
                format_func=lambda x: str(x),
                key=f"{key}_results_select"
            )
            return selected
        
        return None


# Utilidades para optimización de DataFrames

def optimize_dataframe_display(df, max_rows: int = 1000, sample_size: int = 100):
    """
    Optimiza display de DataFrames grandes.
    
    Muestra muestra representativa si es muy grande.
    """
    import pandas as pd

    total_rows = len(df)
    
    if total_rows <= max_rows:
        return df
    
    # Muestreo estratificado si es posible
    if 'categoria' in df.columns:
        # Muestrear por categoría
        samples = []
        for cat in df['categoria'].unique():
            cat_df = df[df['categoria'] == cat]
            sample_count = max(1, int(sample_size * len(cat_df) / total_rows))
            samples.append(cat_df.sample(min(sample_count, len(cat_df))))
        return pd.concat(samples)
    else:
        # Muestreo simple
        return df.sample(min(sample_size, total_rows))


def paginated_dataframe(df, page_size: int = 50, key: str = "df_pag"):
    """
    Muestra DataFrame con paginación.
    """
    import pandas as pd
    import math

    total_pages = math.ceil(len(df) / page_size)
    
    page_key = f"{key}_page"
    if page_key not in st.session_state:
        st.session_state[page_key] = 1
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col1:
        if st.button("← Anterior", key=f"{key}_prev"):
            st.session_state[page_key] = max(1, st.session_state[page_key] - 1)
    
    with col2:
        st.write(f"Página {st.session_state[page_key]} de {total_pages}")
    
    with col3:
        if st.button("Siguiente →", key=f"{key}_next"):
            st.session_state[page_key] = min(total_pages, st.session_state[page_key] + 1)
    
    # Mostrar página actual
    page = st.session_state[page_key]
    start = (page - 1) * page_size
    end = start + page_size
    
    return df.iloc[start:end]


# Instancias globales
_debouncer_instance: Optional[Debouncer] = None
_throttler_instance: Optional[Throttler] = None


def get_debouncer(wait_seconds: float = 0.3) -> Debouncer:
    """Obtiene debouncer global."""
    global _debouncer_instance
    if _debouncer_instance is None:
        _debouncer_instance = Debouncer(wait_seconds)
    return _debouncer_instance


def get_throttler(limit_seconds: float = 0.1) -> Throttler:
    """Obtiene throttler global."""
    global _throttler_instance
    if _throttler_instance is None:
        _throttler_instance = Throttler(limit_seconds)
    return _throttler_instance


def debounced(wait_seconds: float = 0.3):
    """Decorador para debouncear una función."""
    def decorator(func: Callable) -> Callable:
        debouncer = Debouncer(wait_seconds)
        return debouncer.debounce(func)
    return decorator


def throttled(limit_seconds: float = 0.1):
    """Decorador para throttlear una función."""
    def decorator(func: Callable) -> Callable:
        throttler = Throttler(limit_seconds)
        return throttler.throttle(func)
    return decorator
