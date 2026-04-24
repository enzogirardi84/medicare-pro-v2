"""
Optimización de consultas a base de datos (Fase 2).
Paginación eficiente, lazy loading y optimización de queries SQL.
"""
from typing import Any, Dict, List, Optional, Tuple, Callable
from datetime import datetime
import time

import streamlit as st


# ============================================================
# PAGINACIÓN CURSOR-BASED (más eficiente que OFFSET)
# ============================================================

class CursorPaginator:
    """
    Paginación basada en cursor para grandes datasets.
    Más eficiente que OFFSET en tablas con millones de registros.
    """
    
    def __init__(self, page_size: int = 50):
        self.page_size = page_size
        self.cursor_stack: List[Any] = []
        self.current_page = 0
    
    def next_page(self, next_cursor: Any):
        """Avanzar a siguiente página, guardando cursor anterior."""
        if next_cursor:
            self.cursor_stack.append(next_cursor)
        self.current_page += 1
    
    def prev_page(self) -> Optional[Any]:
        """Volver a página anterior, retornando cursor."""
        if self.current_page > 0 and self.cursor_stack:
            self.cursor_stack.pop()
            self.current_page -= 1
        return self.get_current_cursor()
    
    def get_current_cursor(self) -> Optional[Any]:
        """Obtener cursor de página actual."""
        if self.cursor_stack:
            return self.cursor_stack[-1]
        return None
    
    def reset(self):
        """Reiniciar paginador."""
        self.cursor_stack = []
        self.current_page = 0


def fetch_with_cursor(
    table: str,
    columns: List[str],
    order_column: str,
    cursor_value: Optional[Any] = None,
    page_size: int = 50,
    filters: Optional[Dict] = None,
) -> Tuple[List[Dict], Optional[Any]]:
    """
    Fetch datos usando paginación por cursor (más eficiente).
    
    Returns:
        Tuple de (datos, next_cursor)
    """
    from core.database import supabase, _supabase_execute_with_retry
    
    if not supabase:
        return [], None
    
    try:
        # Construir query base
        query = supabase.table(table).select(",".join(columns))
        
        # Aplicar filtros
        if filters:
            for col, val in filters.items():
                query = query.eq(col, val)
        
        # Aplicar cursor si existe
        if cursor_value is not None:
            query = query.gt(order_column, cursor_value)
        
        # Ordenar y limitar
        query = query.order(order_column).limit(page_size + 1)  # +1 para detectar next
        
        response = _supabase_execute_with_retry(
            f"cursor_fetch_{table}",
            lambda: query.execute()
        )
        
        data = response.data if response else []
        
        # Detectar si hay más páginas
        next_cursor = None
        if len(data) > page_size:
            next_cursor = data[-2][order_column]  # Último item de página actual
            data = data[:-1]  # Remover item extra
        
        return data, next_cursor
        
    except Exception as e:
        st.error(f"Error en fetch_with_cursor: {e}")
        return [], None


# ============================================================
# OPTIMIZACIÓN DE QUERIES - COLUMNAS ESPECÍFICAS
# ============================================================

class QueryOptimizer:
    """Utilidades para construir queries optimizadas."""
    
    # Mapeo de tablas a columnas comúnmente usadas (evitar SELECT *)
    TABLE_COLUMNS = {
        "pacientes": [
            "id", "nombre_completo", "dni", "obra_social", 
            "telefono", "email", "fecha_nacimiento", "sexo",
            "estado", "empresa_id", "created_at"
        ],
        "evoluciones": [
            "id", "paciente_id", "fecha_hora", "tipo", "resumen",
            "profesional", "especialidad", "empresa_id", "created_at"
        ],
        "signos_vitales": [
            "id", "paciente_id", "tipo", "valor", "unidad",
            "fecha_hora", "profesional", "empresa_id"
        ],
        "estudios": [
            "id", "paciente_id", "tipo", "subtipo", "fecha",
            "resultados", "profesional_solicitante", "empresa_id"
        ],
        "usuarios": [
            "id", "username", "nombre", "email", "rol",
            "empresa_id", "estado", "last_login"
        ],
        "auditoria_legal": [
            "id", "usuario_id", "accion", "tabla_afectada",
            "registro_id", "fecha_evento", "empresa_id"
        ],
    }
    
    @classmethod
    def get_optimized_columns(cls, table: str, extra_cols: Optional[List[str]] = None) -> str:
        """Obtener lista de columnas optimizada para una tabla."""
        base_cols = cls.TABLE_COLUMNS.get(table, ["*"])
        if extra_cols:
            # Agregar columnas extra sin duplicar
            base_set = set(base_cols)
            final_cols = base_cols + [c for c in extra_cols if c not in base_set]
            return ",".join(final_cols)
        return ",".join(base_cols)
    
    @staticmethod
    def build_paginated_query(
        table: str,
        columns: str,
        page: int = 0,
        page_size: int = 50,
        order_by: str = "created_at",
        order_desc: bool = True,
        filters: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """Construir query paginado con parámetros."""
        offset = page * page_size
        
        query_params = {
            "table": table,
            "columns": columns,
            "limit": page_size,
            "offset": offset,
            "order_by": order_by,
            "order_desc": order_desc,
            "filters": filters or {},
        }
        
        return query_params


# ============================================================
# FETCH EFICIENTE CON CACHÉ
# ============================================================

@st.cache_data(ttl=30, show_spinner=False)
def fetch_pacientes_optimizado(
    empresa_id: str,
    page: int = 0,
    page_size: int = 50,
    solo_activos: bool = True,
    busqueda: str = "",
) -> List[Dict[str, Any]]:
    """
    Fetch optimizado de pacientes con paginación.
    Usa columnas específicas en lugar de SELECT *.
    """
    from core.database import supabase, _supabase_execute_with_retry
    
    if not supabase:
        return []
    
    try:
        # Columnas específicas (no SELECT *)
        columns = QueryOptimizer.get_optimized_columns("pacientes")
        
        query = supabase.table("pacientes").select(columns)
        query = query.eq("empresa_id", empresa_id)
        
        if solo_activos:
            query = query.eq("estado", "Activo")
        
        if busqueda:
            # Búsqueda por nombre o DNI (ILIKE para case-insensitive)
            query = query.or_(f"nombre_completo.ilike.%{busqueda}%,dni.ilike.%{busqueda}%")
        
        # Paginación
        offset = page * page_size
        query = query.order("nombre_completo").range(offset, offset + page_size - 1)
        
        response = _supabase_execute_with_retry(
            "fetch_pacientes_optimizado",
            lambda: query.execute()
        )
        
        return response.data if response else []
        
    except Exception as e:
        st.error(f"Error al cargar pacientes: {e}")
        return []


@st.cache_data(ttl=60, show_spinner=False)
def fetch_evoluciones_paciente(
    paciente_id: str,
    limit: int = 50,
    desde_fecha: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Fetch optimizado de evoluciones de un paciente.
    """
    from core.database import supabase, _supabase_execute_with_retry
    
    if not supabase:
        return []
    
    try:
        # Columnas específicas
        columns = QueryOptimizer.get_optimized_columns("evoluciones", ["texto"])
        
        query = supabase.table("evoluciones").select(columns)
        query = query.eq("paciente_id", paciente_id)
        
        if desde_fecha:
            query = query.gte("fecha_hora", desde_fecha)
        
        query = query.order("fecha_hora", desc=True).limit(limit)
        
        response = _supabase_execute_with_retry(
            "fetch_evoluciones_paciente",
            lambda: query.execute()
        )
        
        return response.data if response else []
        
    except Exception as e:
        st.error(f"Error al cargar evoluciones: {e}")
        return []


# ============================================================
# LAZY LOADING PARA STREAMLIT
# ============================================================

def lazy_data_loader(
    key: str,
    load_fn: Callable[[int, int], List[Dict]],
    page_size: int = 50,
    max_cached_pages: int = 3,
) -> List[Dict]:
    """
    Loader lazy que cachea páginas en session_state.
    
    Args:
        key: Clave única para este dataset
        load_fn: Función (offset, limit) -> datos
        page_size: Tamaño de página
        max_cached_pages: Máximo de páginas a mantener en cache
    
    Returns:
        Lista completa de items cargados
    """
    state_key = f"_lazy_loader_{key}"
    
    if state_key not in st.session_state:
        st.session_state[state_key] = {
            "items": [],
            "current_page": -1,
            "has_more": True,
            "loading": False,
        }
    
    state = st.session_state[state_key]
    
    # Botón "Cargar más"
    if state["has_more"] and not state["loading"]:
        cols = st.columns([1, 4])
        with cols[0]:
            if st.button(f"+ {page_size} más", key=f"lazy_load_{key}"):
                state["loading"] = True
                state["current_page"] += 1
                
                offset = state["current_page"] * page_size
                new_items = load_fn(offset, page_size)
                
                if new_items:
                    state["items"].extend(new_items)
                    state["has_more"] = len(new_items) == page_size
                else:
                    state["has_more"] = False
                
                state["loading"] = False
                st.rerun()
        
        with cols[1]:
            st.caption(f"Mostrando {len(state['items'])} registros")
    
    return state["items"]


# ============================================================
# BATCH OPERATIONS
# ============================================================

def batch_insert(
    table: str,
    records: List[Dict[str, Any]],
    batch_size: int = 100,
) -> Tuple[int, List[Exception]]:
    """
    Insertar registros en batches para evitar timeouts.
    
    Returns:
        Tuple de (insertados_count, errores)
    """
    from core.database import supabase, _supabase_execute_with_retry
    
    if not supabase or not records:
        return 0, []
    
    inserted = 0
    errors = []
    
    for i in range(0, len(records), batch_size):
        batch = records[i:i + batch_size]
        
        try:
            _supabase_execute_with_retry(
                f"batch_insert_{table}",
                lambda: supabase.table(table).insert(batch).execute()
            )
            inserted += len(batch)
            
            # Pequeña pausa entre batches
            time.sleep(0.05)
            
        except Exception as e:
            errors.append(e)
    
    return inserted, errors


# ============================================================
# MONITOREO DE PERFORMANCE DE QUERIES
# ============================================================

class QueryProfiler:
    """Profiler simple para queries SQL."""
    
    def __init__(self):
        self.queries: List[Dict] = []
    
    def profile(self, name: str, fn: Callable[[], Any]) -> Any:
        """Ejecutar función y medir tiempo."""
        start = time.time()
        try:
            result = fn()
            duration = time.time() - start
            self.queries.append({
                "name": name,
                "duration": duration,
                "error": None,
                "timestamp": datetime.now().isoformat(),
            })
            return result
        except Exception as e:
            duration = time.time() - start
            self.queries.append({
                "name": name,
                "duration": duration,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            })
            raise
    
    def get_slow_queries(self, threshold_ms: float = 500) -> List[Dict]:
        """Obtener queries lentas (mayor a threshold en ms)."""
        return [q for q in self.queries if q["duration"] * 1000 > threshold_ms]
    
    def report(self) -> str:
        """Generar reporte de performance."""
        if not self.queries:
            return "Sin queries registradas"
        
        total = sum(q["duration"] for q in self.queries)
        avg = total / len(self.queries)
        slow = len(self.get_slow_queries())
        
        return (
            f"📊 Query Profiler Report:\n"
            f"   Total queries: {len(self.queries)}\n"
            f"   Tiempo total: {total:.2f}s\n"
            f"   Promedio: {avg*1000:.1f}ms\n"
            f"   Lentas (>500ms): {slow}\n"
        )


# Instancia global del profiler
_query_profiler = QueryProfiler()

def get_query_profiler() -> QueryProfiler:
    """Obtener instancia del profiler."""
    return _query_profiler


def profiled_query(name: str, fn: Callable[[], Any]) -> Any:
    """Ejecutar query con profiling automático."""
    return _query_profiler.profile(name, fn)
