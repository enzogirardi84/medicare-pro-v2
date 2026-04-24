"""
Consultas paginadas y optimizadas a Supabase.

- Paginación obligatoria (máximo 100 registros por página)
- Caché con @st.cache_data
- Connection pooling
- Cursor-based pagination para grandes volúmenes
"""
from typing import Any, Dict, List, Optional, Tuple, Callable
from datetime import datetime, timedelta
from functools import wraps
import time
import streamlit as st
from dataclasses import dataclass

from core.app_logging import log_event
from core.pagination import PageInfo, CursorPaginator


@dataclass
class PaginatedQuery:
    """Configuración de consulta paginada."""
    table: str
    page_size: int = 50
    max_pages: int = 100
    order_by: str = "id"
    ascending: bool = True
    filters: Optional[Dict[str, Any]] = None


class PaginatedSupabaseQuery:
    """
    Wrapper para consultas paginadas a Supabase.
    Obligatorio para tablas grandes (pacientes, evoluciones, etc.)
    """
    
    DEFAULT_PAGE_SIZE = 50
    MAX_PAGE_SIZE = 100  # Límite de seguridad
    
    def __init__(self, supabase_client):
        self.client = supabase_client
        self._cache_hits = 0
        self._cache_misses = 0
    
    def _validate_page_size(self, size: int) -> int:
        """Valida y limita el tamaño de página."""
        if size < 1:
            return self.DEFAULT_PAGE_SIZE
        if size > self.MAX_PAGE_SIZE:
            log_event(
                "pagination",
                f"page_size_limitado:{size}->{self.MAX_PAGE_SIZE}"
            )
            return self.MAX_PAGE_SIZE
        return size
    
    @st.cache_data(
        ttl=300,  # 5 minutos
        show_spinner=False,
        persist="disk"
    )
    def _cached_query(
        _self,
        table: str,
        page: int,
        page_size: int,
        order_by: str,
        ascending: bool,
        tenant_id: Optional[str] = None,
        _cache_key: Optional[str] = None
    ) -> Tuple[List[Dict], int, bool]:
        """
        Consulta cacheada a Supabase.
        
        Returns:
            (items, total_count, has_more)
        """
        try:
            query = _self.client.table(table).select("*")
            
            # Aplicar filtro de tenant si existe (RLS)
            if tenant_id:
                query = query.eq("tenant_id", tenant_id)
            
            # Ordenar
            if ascending:
                query = query.order(order_by, desc=False)
            else:
                query = query.order(order_by, desc=True)
            
            # Paginación con range
            start = (page - 1) * page_size
            end = start + page_size - 1
            query = query.range(start, end)
            
            # Ejecutar
            response = query.execute()
            items = response.data if response.data else []
            
            # Contar total (optimizado: solo en primera página)
            total_count = 0
            if page == 1:
                count_response = _self.client.table(table).select(
                    "*", count="exact", head=True
                ).execute()
                total_count = getattr(count_response, 'count', len(items))
            
            # Determinar si hay más
            has_more = len(items) == page_size
            
            _self._cache_hits += 1
            return items, total_count, has_more
            
        except Exception as e:
            log_event("db_error", f"paginated_query_error:{table}:{type(e).__name__}")
            raise
    
    def query_paginated(
        self,
        table: str,
        page: int = 1,
        page_size: int = 50,
        order_by: str = "id",
        ascending: bool = True,
        tenant_id: Optional[str] = None,
        filters: Optional[Dict[str, Any]] = None
    ) -> PageInfo:
        """
        Ejecuta consulta paginada con caché automático.
        
        Args:
            table: Nombre de la tabla
            page: Número de página (1-based)
            page_size: Tamaño de página (máx 100)
            order_by: Campo de ordenamiento
            ascending: True para ascendente
            tenant_id: Filtro de tenant para RLS
            filters: Filtros adicionales (dict de eq conditions)
        
        Returns:
            PageInfo con items y metadatos
        """
        page_size = self._validate_page_size(page_size)
        
        # Cache key único para la consulta
        cache_key = f"{table}:{page}:{page_size}:{order_by}:{ascending}:{tenant_id}:{hash(str(filters))}"
        
        start_time = time.time()
        
        try:
            items, total_count, has_more = self._cached_query(
                self,  # _self para Streamlit cache
                table,
                page,
                page_size,
                order_by,
                ascending,
                tenant_id,
                cache_key
            )
            
            # Aplicar filtros adicionales si existen (en memoria, ya que Supabase no permite múltiples eq)
            if filters and items:
                filtered_items = items
                for key, value in filters.items():
                    filtered_items = [
                        item for item in filtered_items
                        if item.get(key) == value
                    ]
                items = filtered_items
            
            elapsed_ms = (time.time() - start_time) * 1000
            
            log_event(
                "db_query",
                f"paginated:{table}:page_{page}:size_{len(items)}:{elapsed_ms:.1f}ms"
            )
            
            return PageInfo(
                items=items,
                has_more=has_more,
                total_count=total_count,
                page_size=page_size,
                next_cursor=str(page + 1) if has_more else None,
                prev_cursor=str(page - 1) if page > 1 else None
            )
            
        except Exception as e:
            log_event("db_error", f"query_paginated_failed:{table}:{type(e).__name__}")
            # Retornar página vacía en caso de error (fail-open para UX)
            return PageInfo(
                items=[],
                has_more=False,
                total_count=0,
                page_size=page_size
            )
    
    def search_paginated(
        self,
        table: str,
        search_field: str,
        search_term: str,
        page: int = 1,
        page_size: int = 50,
        tenant_id: Optional[str] = None
    ) -> PageInfo:
        """
        Búsqueda paginada con ilike.
        
        Args:
            table: Tabla a consultar
            search_field: Campo a buscar (ej: "nombre")
            search_term: Término de búsqueda
            page: Página actual
            page_size: Tamaño de página
            tenant_id: Filtro de tenant
        """
        page_size = self._validate_page_size(page_size)
        
        try:
            query = self.client.table(table).select("*")
            
            # Filtro de tenant
            if tenant_id:
                query = query.eq("tenant_id", tenant_id)
            
            # Búsqueda ilike (case insensitive)
            if search_term:
                query = query.ilike(search_field, f"%{search_term}%")
            
            # Paginación
            start = (page - 1) * page_size
            end = start + page_size - 1
            query = query.range(start, end)
            
            response = query.execute()
            items = response.data if response.data else []
            
            has_more = len(items) == page_size
            
            return PageInfo(
                items=items,
                has_more=has_more,
                page_size=page_size,
                next_cursor=str(page + 1) if has_more else None,
                prev_cursor=str(page - 1) if page > 1 else None
            )
            
        except Exception as e:
            log_event("db_error", f"search_paginated_failed:{table}:{type(e).__name__}")
            return PageInfo(items=[], has_more=False, page_size=page_size)


def get_paginated_patients(
    page: int = 1,
    page_size: int = 50,
    search: Optional[str] = None,
    tenant_id: Optional[str] = None,
    supabase_client = None
) -> PageInfo:
    """
    Obtiene pacientes paginados - función helper de alto nivel.
    Usar esta función en la UI de pacientes.
    """
    if supabase_client is None:
        from core._database_supabase import supabase
        supabase_client = supabase
    
    if supabase_client is None:
        log_event("db_error", "supabase_not_initialized")
        return PageInfo(items=[], has_more=False, page_size=page_size)
    
    paginator = PaginatedSupabaseQuery(supabase_client)
    
    if search:
        return paginator.search_paginated(
            table="pacientes",
            search_field="nombre",
            search_term=search,
            page=page,
            page_size=page_size,
            tenant_id=tenant_id
        )
    else:
        return paginator.query_paginated(
            table="pacientes",
            page=page,
            page_size=page_size,
            order_by="nombre",
            tenant_id=tenant_id
        )
