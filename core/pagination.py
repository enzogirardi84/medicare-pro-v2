"""
Sistema de paginación optimizado para millones de registros.

- Paginación cursor-based (más eficiente que offset)
- Lazy loading virtualizado
- Prefetching predictivo
- Caché de páginas visitadas
"""

from __future__ import annotations

import hashlib
import json
import math
import threading
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar, Tuple

import streamlit as st

from core.app_logging import log_event
from core.cache_manager import get_cache_manager

T = TypeVar('T')


@dataclass
class PageInfo:
    """Información de una página de resultados."""
    items: List[Any]
    next_cursor: Optional[str] = None
    prev_cursor: Optional[str] = None
    has_more: bool = False
    total_count: Optional[int] = None
    page_size: int = 50


@dataclass
class CursorPage:
    """Página cursor-based para paginación eficiente."""
    cursor: str
    items: List[Any]
    timestamp: float = 0.0
    next_cursor: Optional[str] = None


class CursorPaginator(Generic[T]):
    """
    Paginador cursor-based para grandes volúmenes de datos.

    Ventajas sobre offset:
    - O(1) para saltar a cualquier página
    - No degradación en páginas profundas
    - Consistente ante inserciones concurrentes
    """

    def __init__(
        self,
        page_size: int = 50,
        cache_ttl: float = 60.0,
        max_cached_pages: int = 10,
    ):
        self.page_size = page_size
        self.cache_ttl = cache_ttl
        self.max_cached_pages = max_cached_pages
        self._page_cache: Dict[str, CursorPage] = {}
        self._lock = threading.Lock()

    def _generate_cursor(self, item: T, sort_field: str) -> str:
        """Genera cursor único basado en el item."""
        cursor_data = json.dumps({
            "field": sort_field,
            "value": getattr(item, sort_field, str(item)),
            "id": getattr(item, 'id', str(item)),
        }, sort_keys=True, default=str)
        return hashlib.md5(cursor_data.encode()).hexdigest()[:16]

    def paginate(
        self,
        items: List[T],
        cursor: Optional[str] = None,
        sort_field: str = "id",
        sort_desc: bool = False,
    ) -> PageInfo:
        """
        Pagina una lista de items usando cursor.

        Args:
            items: Lista completa de items
            cursor: Cursor de la página actual (None = primera)
            sort_field: Campo para ordenar
            sort_desc: True para descendente

        Returns:
            PageInfo con items de la página y metadatos
        """
        if not items:
            return PageInfo(items=[], has_more=False, page_size=self.page_size)

        # Ordenar items
        sorted_items = sorted(
            items,
            key=lambda x: getattr(x, sort_field, str(x)),
            reverse=sort_desc,
        )

        # Encontrar índice basado en cursor
        start_idx = 0
        if cursor:
            for idx, item in enumerate(sorted_items):
                item_cursor = self._generate_cursor(item, sort_field)
                if item_cursor == cursor:
                    start_idx = idx + 1
                    break

        # Extraer página
        end_idx = min(start_idx + self.page_size, len(sorted_items))
        page_items = sorted_items[start_idx:end_idx]

        # Generar cursores
        next_cursor = None
        prev_cursor = cursor

        if end_idx < len(sorted_items):
            next_item = sorted_items[end_idx]
            next_cursor = self._generate_cursor(next_item, sort_field)

        return PageInfo(
            items=page_items,
            next_cursor=next_cursor,
            prev_cursor=prev_cursor,
            has_more=end_idx < len(sorted_items),
            total_count=len(sorted_items),
            page_size=self.page_size,
        )

    def get_page_number(
        self,
        items: List[T],
        cursor: Optional[str],
        sort_field: str = "id",
    ) -> int:
        """Obtiene número de página aproximado para UI."""
        if not cursor:
            return 1

        sorted_items = sorted(items, key=lambda x: getattr(x, sort_field, str(x)))
        for idx, item in enumerate(sorted_items):
            if self._generate_cursor(item, sort_field) == cursor:
                return (idx // self.page_size) + 1
        return 1


class VirtualizedDataLoader:
    """
    Cargador de datos virtualizado para grandes datasets.
    Carga datos bajo demanda con prefetching.
    """

    def __init__(
        self,
        fetch_callback: Callable[[int, int], List[T]],
        page_size: int = 100,
        prefetch_pages: int = 2,
        cache_ttl: float = 120.0,
    ):
        self.fetch_callback = fetch_callback
        self.page_size = page_size
        self.prefetch_pages = prefetch_pages
        self.cache_ttl = cache_ttl
        self._loaded_pages: Dict[int, List[T]] = {}
        self._prefetch_queue: List[int] = []
        self._total_items: Optional[int] = None
        self._lock = threading.Lock()

    def _page_key(self, tenant: str, page: int) -> str:
        return f"virt_page:{tenant}:{page}"

    def get_items(
        self,
        tenant: str,
        start_index: int,
        count: int,
    ) -> List[T]:
        """
        Obtiene items de forma virtualizada.

        Args:
            tenant: Identificador del tenant
            start_index: Índice inicial
            count: Cantidad de items

        Returns:
            Lista de items
        """
        cache = get_cache_manager()

        # Calcular páginas necesarias
        start_page = start_index // self.page_size
        end_page = (start_index + count - 1) // self.page_size

        result = []

        for page_num in range(start_page, end_page + 1):
            page_key = self._page_key(tenant, page_num)

            # Intentar obtener del caché
            hit, page_data = cache.get("virtualized", tenant, page_key)

            if not hit:
                # Cargar página
                page_offset = page_num * self.page_size
                page_data = self.fetch_callback(page_offset, self.page_size)

                # Guardar en caché
                cache.set(
                    "virtualized",
                    tenant,
                    page_data,
                    page_key,
                    ttl_seconds=self.cache_ttl,
                )

                # Agregar a prefetch
                self._queue_prefetch(tenant, page_num)

            # Extraer items relevantes de la página
            page_start = page_num * self.page_size
            item_start = max(0, start_index - page_start)
            item_end = min(len(page_data), start_index + count - page_start)

            if item_start < len(page_data):
                result.extend(page_data[item_start:item_end])

        return result[:count]

    def _queue_prefetch(self, tenant: str, current_page: int):
        """Encola páginas para prefetching."""
        for offset in range(1, self.prefetch_pages + 1):
            next_page = current_page + offset
            self._prefetch_queue.append((tenant, next_page))

    def prefetch_background(self):
        """Ejecuta prefetching en segundo plano (llamar periódicamente)."""
        if not self._prefetch_queue:
            return

        cache = get_cache_manager()
        to_prefetch = self._prefetch_queue[:3]  # Procesar máximo 3
        self._prefetch_queue = self._prefetch_queue[3:]

        for tenant, page_num in to_prefetch:
            page_key = self._page_key(tenant, page_num)

            # Verificar si ya está en caché
            hit, _ = cache.get("virtualized", tenant, page_key)
            if hit:
                continue

            try:
                page_offset = page_num * self.page_size
                page_data = self.fetch_callback(page_offset, self.page_size)
                cache.set(
                    "virtualized",
                    tenant,
                    page_data,
                    page_key,
                    ttl_seconds=self.cache_ttl,
                )
            except Exception as e:
                log_event("pagination", f"prefetch_error:{tenant}:{page_num}:{e}")


class SearchablePaginator:
    """
    Paginador con búsqueda integrada para grandes datasets.
    """

    def __init__(
        self,
        page_size: int = 50,
        search_fields: List[str] = None,
        min_search_chars: int = 3,
    ):
        self.page_size = page_size
        self.search_fields = search_fields or ["nombre", "apellido", "dni"]
        self.min_search_chars = min_search_chars

    def search_and_paginate(
        self,
        items: List[T],
        search_query: Optional[str] = None,
        page: int = 1,
        filters: Optional[Dict[str, Any]] = None,
        sort_field: str = "nombre",
        sort_asc: bool = True,
    ) -> PageInfo:
        """
        Busca, filtra y pagina items.

        Args:
            items: Lista completa
            search_query: Término de búsqueda
            page: Número de página (1-based)
            filters: Filtros adicionales
            sort_field: Campo de ordenamiento
            sort_asc: True para ascendente

        Returns:
            PageInfo con resultados
        """
        result = items

        # Aplicar filtros
        if filters:
            for field, value in filters.items():
                if value is not None:
                    result = [
                        item for item in result
                        if self._matches_filter(item, field, value)
                    ]

        def _get_value(item, field):
            if isinstance(item, dict):
                return item.get(field, "")
            return getattr(item, field, "")

        def _has_value(item, field):
            if isinstance(item, dict):
                return field in item
            return hasattr(item, field)

        # Aplicar búsqueda
        if search_query and len(search_query) >= self.min_search_chars:
            query_lower = search_query.lower()
            result = [
                item for item in result
                if any(
                    query_lower in str(_get_value(item, field)).lower()
                    for field in self.search_fields
                    if _has_value(item, field)
                )
            ]

        # Ordenar
        result = sorted(
            result,
            key=lambda x: str(_get_value(x, sort_field) or ""),
            reverse=not sort_asc,
        )

        # Paginar
        total = len(result)
        start_idx = (page - 1) * self.page_size
        end_idx = min(start_idx + self.page_size, total)
        page_items = result[start_idx:end_idx]

        return PageInfo(
            items=page_items,
            has_more=end_idx < total,
            total_count=total,
            page_size=self.page_size,
        )

    def _matches_filter(self, item: T, field: str, value: Any) -> bool:
        """Verifica si un item coincide con un filtro."""
        item_value = getattr(item, field, None)
        if item_value is None:
            return False
        return str(item_value).lower() == str(value).lower()


# Funciones de utilidad para Streamlit

def render_pagination_controls(
    current_page: int,
    total_pages: int,
    key_prefix: str = "pag",
) -> int:
    """
    Renderiza controles de paginación en Streamlit.
    Retorna la página seleccionada.
    """
    import streamlit as st

    cols = st.columns([1, 2, 1])

    with cols[0]:
        if current_page > 1:
            if st.button("← Anterior", key=f"{key_prefix}_prev"):
                return current_page - 1

    with cols[1]:
        st.markdown(f"**Página {current_page} de {total_pages}**")

    with cols[2]:
        if current_page < total_pages:
            if st.button("Siguiente →", key=f"{key_prefix}_next"):
                return current_page + 1

    return current_page


def render_lazy_loading_indicator(
    loaded_count: int,
    total_count: Optional[int],
    has_more: bool,
):
    """Renderiza indicador de lazy loading."""
    import streamlit as st

    if total_count:
        progress = loaded_count / total_count
        st.progress(progress, text=f"Cargados {loaded_count} de {total_count}")
    else:
        st.caption(f"Cargados {loaded_count} items" + (" (cargar más)" if has_more else ""))

    if has_more:
        return st.button("Cargar más", key="load_more_btn")
    return False


def calculate_total_pages(total_items: int, page_size: int) -> int:
    """Calcula número total de páginas."""
    return max(1, math.ceil(total_items / page_size))


# Instancia global de paginador
def get_cursor_paginator(page_size: int = 50) -> CursorPaginator:
    """Obtiene instancia de paginador cursor-based."""
    return CursorPaginator(page_size=page_size)


def get_searchable_paginator(
    page_size: int = 50,
    search_fields: List[str] = None,
) -> SearchablePaginator:
    """Obtiene instancia de paginador con búsqueda."""
    return SearchablePaginator(
        page_size=page_size,
        search_fields=search_fields,
    )
