"""
Sistema de Búsqueda Global Inteligente para MediCare.
Búsqueda con autocompletado, filtros rápidos y resultados destacados.
"""
import re
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass
from datetime import datetime
import html

import streamlit as st


@dataclass
class SearchResult:
    """Resultado de búsqueda estructurado."""
    id: str
    title: str
    subtitle: Optional[str] = None
    badge: Optional[str] = None
    badge_type: str = "info"  # critical, warning, success, info, neutral, alergia, urgencia
    metadata: Dict[str, Any] = None
    score: float = 0.0  # Relevancia (0-1)
    
    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class SmartSearchEngine:
    """
    Motor de búsqueda inteligente con scoring de relevancia.
    """
    
    def __init__(self):
        self.search_history: List[str] = []
        self.max_history = 10
    
    def search(
        self,
        query: str,
        items: List[Dict[str, Any]],
        searchable_fields: List[str] = None,
        filters: Dict[str, Any] = None,
        limit: int = 50,
    ) -> List[SearchResult]:
        """
        Buscar en una lista de items con scoring inteligente.
        
        Args:
            query: Término de búsqueda
            items: Lista de diccionarios a buscar
            searchable_fields: Campos a buscar (default: todos)
            filters: Filtros adicionales {campo: valor}
            limit: Máximo de resultados
        
        Returns:
            Lista de SearchResult ordenados por relevancia
        """
        if not query or len(query.strip()) < 2:
            return []
        
        query_lower = query.lower().strip()
        query_words = query_lower.split()
        results = []
        
        for item in items:
            # Aplicar filtros primero
            if filters and not self._matches_filters(item, filters):
                continue
            
            # Calcular score de relevancia
            score = self._calculate_score(item, query_lower, query_words, searchable_fields)
            
            if score > 0:
                result = self._item_to_result(item, score)
                results.append(result)
        
        # Ordenar por score descendente
        results.sort(key=lambda x: x.score, reverse=True)
        
        # Guardar en historial
        self._add_to_history(query)
        
        return results[:limit]
    
    def _calculate_score(
        self,
        item: Dict[str, Any],
        query_lower: str,
        query_words: List[str],
        searchable_fields: Optional[List[str]]
    ) -> float:
        """Calcular score de relevancia (0-1)."""
        score = 0.0
        
        # Determinar campos a buscar
        fields = searchable_fields or list(item.keys())
        
        for field in fields:
            value = str(item.get(field, "")).lower()
            if not value:
                continue
            
            # Match exacto (máximo puntaje)
            if query_lower == value:
                score += 1.0
            # Match al inicio (alto puntaje)
            elif value.startswith(query_lower):
                score += 0.8
            # Match de palabra completa (buen puntaje)
            elif f" {query_lower} " in f" {value} " or value.endswith(f" {query_lower}"):
                score += 0.6
            # Match parcial
            elif query_lower in value:
                score += 0.4
            # Match de palabras individuales
            else:
                word_matches = sum(1 for word in query_words if word in value)
                score += (word_matches / len(query_words)) * 0.3
        
        # Bonus por campos específicos
        nombre = str(item.get("nombre_completo", "")).lower()
        dni = str(item.get("dni", "")).lower()
        
        if query_lower in nombre:
            score += 0.2
        if query_lower == dni:
            score += 0.3
        
        return min(score, 1.0)  # Cap at 1.0
    
    def _matches_filters(self, item: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Verificar si un item cumple con los filtros."""
        for field, value in filters.items():
            item_value = str(item.get(field, "")).lower()
            filter_value = str(value).lower()
            
            if filter_value not in item_value:
                return False
        return True
    
    def _item_to_result(self, item: Dict[str, Any], score: float) -> SearchResult:
        """Convertir item a SearchResult."""
        # Determinar estado para badge
        estado = item.get("estado", "Activo")
        badge_type = self._estado_to_badge_type(estado)
        
        # Construir metadata útil
        metadata = {
            "dni": item.get("dni", ""),
            "obra_social": item.get("obra_social", ""),
            "telefono": item.get("telefono", ""),
            "email": item.get("email", ""),
            "fecha_nacimiento": item.get("fecha_nacimiento", ""),
            "edad": item.get("edad", ""),
            "sexo": item.get("sexo", ""),
        }
        
        return SearchResult(
            id=str(item.get("id", "")),
            title=item.get("nombre_completo", "Sin nombre"),
            subtitle=f"DNI: {item.get('dni', 'N/A')}",
            badge=estado,
            badge_type=badge_type,
            metadata=metadata,
            score=score,
        )
    
    def _estado_to_badge_type(self, estado: str) -> str:
        """Convertir estado a tipo de badge."""
        estado_lower = estado.lower()
        mapping = {
            "activo": "success",
            "internado": "info",
            "alta": "neutral",
            "egresado": "neutral",
            "crítico": "critical",
            "critico": "critical",
            "urgente": "urgencia",
            "pendiente": "warning",
        }
        return mapping.get(estado_lower, "info")
    
    def _add_to_history(self, query: str):
        """Agregar búsqueda al historial."""
        if query in self.search_history:
            self.search_history.remove(query)
        self.search_history.insert(0, query)
        self.search_history = self.search_history[:self.max_history]
    
    def get_suggestions(self, partial: str) -> List[str]:
        """Obtener sugerencias basadas en historial."""
        partial_lower = partial.lower()
        return [
            q for q in self.search_history
            if partial_lower in q.lower() and q.lower() != partial_lower
        ][:5]


# ============================================================
# COMPONENTES UI PARA BÚSQUEDA
# ============================================================

def render_smart_search_bar(
    key: str = "smart_search",
    placeholder: str = "Buscar paciente por nombre, DNI o obra social...",
    autofocus: bool = False,
) -> str:
    """
    Renderizar barra de búsqueda inteligente con estilos mejorados.
    
    Returns:
        Query ingresado por el usuario
    """
    # CSS para la barra de búsqueda
    st.markdown("""
    <style>
    .mc-search-container {
        position: relative;
        margin-bottom: 1rem;
    }
    
    .mc-search-input-wrapper {
        position: relative;
        display: flex;
        align-items: center;
    }
    
    .mc-search-icon {
        position: absolute;
        left: 1rem;
        color: #64748b;
        font-size: 1.1rem;
        z-index: 10;
        pointer-events: none;
    }
    
    .mc-search-input {
        width: 100%;
        padding: 0.875rem 1rem 0.875rem 2.75rem;
        border: 2px solid rgba(148, 163, 184, 0.2);
        border-radius: 12px;
        background: rgba(15, 23, 42, 0.6);
        color: #f1f5f9;
        font-size: 1rem;
        transition: all 0.25s ease;
        backdrop-filter: blur(8px);
    }
    
    .mc-search-input:focus {
        outline: none;
        border-color: #3b82f6;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
        background: rgba(15, 23, 42, 0.8);
    }
    
    .mc-search-input::placeholder {
        color: #64748b;
    }
    
    .mc-search-badges {
        display: flex;
        gap: 0.5rem;
        margin-top: 0.75rem;
        flex-wrap: wrap;
    }
    
    .mc-search-badge {
        padding: 0.375rem 0.875rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 600;
        cursor: pointer;
        transition: all 0.2s ease;
        border: 1px solid transparent;
        text-transform: uppercase;
        letter-spacing: 0.025em;
    }
    
    .mc-search-badge:hover {
        transform: translateY(-1px);
    }
    
    .mc-search-badge.active {
        background: rgba(59, 130, 246, 0.2);
        color: #3b82f6;
        border-color: rgba(59, 130, 246, 0.4);
    }
    
    .mc-search-badge.inactive {
        background: rgba(30, 41, 59, 0.5);
        color: #64748b;
        border-color: rgba(148, 163, 184, 0.2);
    }
    
    .mc-search-results-count {
        font-size: 0.875rem;
        color: #64748b;
        margin-top: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Contenedor visual
    st.markdown('<div class="mc-search-container">', unsafe_allow_html=True)
    
    # Input de búsqueda con icono
    col1, col2 = st.columns([20, 1])
    with col1:
        query = st.text_input(
            "",
            placeholder=placeholder,
            key=f"{key}_input",
            label_visibility="collapsed",
        )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    return query


def render_search_filters(
    key: str = "search_filters",
    show_estados: bool = True,
    show_obras_sociales: bool = True,
    obras_sociales_list: List[str] = None,
) -> Dict[str, Any]:
    """
    Renderizar filtros rápidos como badges clickeables.
    
    Returns:
        Dict con filtros activos
    """
    filters = {}
    
    if show_estados:
        st.markdown("<div style='margin-bottom:0.5rem;color:#64748b;font-size:0.8rem;'>Estado:</div>", 
                     unsafe_allow_html=True)
        
        estado_cols = st.columns(4)
        estados = [
            ("Todos", None, "neutral"),
            ("Activos", "Activo", "success"),
            ("Internados", "Internado", "info"),
            ("De Alta", "Alta", "neutral"),
        ]
        
        estado_seleccionado = st.session_state.get(f"{key}_estado", "Todos")
        
        for i, (label, valor, tipo) in enumerate(estados):
            with estado_cols[i]:
                is_active = estado_seleccionado == label
                badge_class = "mc-badge-" + (tipo if is_active else "neutral")
                opacity = "1" if is_active else "0.6"
                
                if st.button(
                    label,
                    key=f"{key}_estado_{i}",
                    use_container_width=True,
                    type="secondary" if not is_active else "primary",
                ):
                    st.session_state[f"{key}_estado"] = label
                    filters["estado"] = valor
                    st.rerun()
        
        # Recuperar filtro guardado
        if f"{key}_estado" in st.session_state:
            selected = st.session_state[f"{key}_estado"]
            for label, valor, _ in estados:
                if label == selected and valor:
                    filters["estado"] = valor
    
    return filters


def render_search_result_card(
    result: SearchResult,
    on_click: Optional[Callable] = None,
    key_suffix: str = "",
) -> bool:
    """
    Renderizar una card de resultado de búsqueda.
    
    Returns:
        True si fue clickeada
    """
    # Badge CSS según tipo
    badge_styles = {
        "critical": "background:rgba(239,68,68,0.15);color:#ef4444;border-color:rgba(239,68,68,0.3);",
        "warning": "background:rgba(245,158,11,0.15);color:#f59e0b;border-color:rgba(245,158,11,0.3);",
        "success": "background:rgba(34,197,94,0.15);color:#22c55e;border-color:rgba(34,197,94,0.3);",
        "info": "background:rgba(59,130,246,0.15);color:#3b82f6;border-color:rgba(59,130,246,0.3);",
        "neutral": "background:rgba(148,163,184,0.15);color:#94a3b8;border-color:rgba(148,163,184,0.3);",
        "alergia": "background:rgba(236,72,153,0.15);color:#ec4899;border-color:rgba(236,72,153,0.3);",
        "urgencia": "background:linear-gradient(135deg,rgba(239,68,68,0.15),rgba(245,158,11,0.15));color:#f97316;border-color:rgba(245,158,11,0.3);",
    }
    
    badge_style = badge_styles.get(result.badge_type, badge_styles["info"])
    badge_html = f"""
    <span style="display:inline-flex;align-items:center;gap:0.375rem;padding:0.25rem 0.625rem;
                 border-radius:9999px;font-size:0.7rem;font-weight:600;letter-spacing:0.025em;
                 text-transform:uppercase;border:1px solid transparent;{badge_style}">
        {html.escape(result.badge) if result.badge else ''}
    </span>
    """ if result.badge else ""
    
    # Metadata secundaria
    meta_items = []
    if result.metadata.get("obra_social"):
        meta_items.append(f"🏥 {html.escape(str(result.metadata['obra_social']))}")
    if result.metadata.get("telefono"):
        meta_items.append(f"📞 {html.escape(str(result.metadata['telefono']))}")
    if result.metadata.get("edad"):
        meta_items.append(f"🎂 {html.escape(str(result.metadata['edad']))} años")
    
    meta_html = " · ".join(meta_items) if meta_items else ""
    
    # Card HTML
    card_html = f"""
    <div style="
        background: linear-gradient(135deg, rgba(30,41,59,0.6) 0%, rgba(15,23,42,0.8) 100%);
        border: 1px solid rgba(148,163,184,0.1);
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 0.75rem;
        cursor: pointer;
        transition: all 0.25s ease;
        position: relative;
        overflow: hidden;
    " onmouseover="this.style.transform='translateY(-2px)';this.style.borderColor='rgba(148,163,184,0.2)';this.style.boxShadow='0 8px 30px rgba(2,6,23,0.25)';"
       onmouseout="this.style.transform='translateY(0)';this.style.borderColor='rgba(148,163,184,0.1)';this.style.boxShadow='none';"
    >
        <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.5rem;">
            <div>
                <h4 style="margin:0;font-size:1rem;font-weight:600;color:#f8fafc;">
                    {html.escape(result.title)}
                </h4>
                <p style="margin:0.25rem 0 0 0;color:#64748b;font-size:0.85rem;">
                    {html.escape(result.subtitle) if result.subtitle else ''}
                </p>
            </div>
            <div>{badge_html}</div>
        </div>
        <div style="display:flex;justify-content:space-between;align-items:center;">
            <div style="font-size:0.8rem;color:#94a3b8;">{meta_html}</div>
            <div style="font-size:0.75rem;color:#475569;background:rgba(30,41,59,0.8);
                        padding:0.25rem 0.5rem;border-radius:6px;">
                {result.score:.0%} match
            </div>
        </div>
        <div style="position:absolute;bottom:0;left:0;right:0;height:3px;
                    background:linear-gradient(90deg,#3b82f6,#22c55e);
                    opacity:0;transition:opacity 0.3s ease;"
             onmouseover="this.style.opacity='1';"
             onmouseout="this.style.opacity='0';">
        </div>
    </div>
    """
    
    clicked = st.button(
        f"Seleccionar: {result.title}",
        key=f"result_{result.id}_{key_suffix}",
        use_container_width=True,
        type="secondary",
    )
    
    st.markdown(card_html, unsafe_allow_html=True)
    
    return clicked


def render_search_results(
    results: List[SearchResult],
    on_select: Optional[Callable[[SearchResult], None]] = None,
    empty_message: str = "No se encontraron resultados",
    key: str = "search_results",
):
    """
    Renderizar lista de resultados de búsqueda.
    """
    if not results:
        st.info(empty_message)
        return
    
    # Contador de resultados
    st.markdown(
        f"<div style='font-size:0.875rem;color:#64748b;margin-bottom:1rem;'>"
        f"📊 {len(results)} resultado{'s' if len(results) > 1 else ''} encontrado{'s' if len(results) > 1 else ''}"
        f"</div>",
        unsafe_allow_html=True
    )
    
    # Resultados
    for i, result in enumerate(results):
        clicked = render_search_result_card(result, on_select, f"{key}_{i}")
        if clicked and on_select:
            on_select(result)
            st.rerun()


# ============================================================
# FUNCIÓN PRINCIPAL: BÚSQUEDA INTEGRADA
# ============================================================

def smart_search_pacientes(
    pacientes_data: List[Dict[str, Any]],
    key: str = "smart_search_main",
) -> Optional[SearchResult]:
    """
    Componente completo de búsqueda inteligente de pacientes.
    
    Returns:
        SearchResult seleccionado o None
    """
    st.markdown("## 🔍 Buscador Inteligente de Pacientes")
    
    # Barra de búsqueda
    query = render_smart_search_bar(
        key=key,
        placeholder="Nombre completo, DNI, obra social o teléfono...",
    )
    
    # Filtros rápidos
    filters = render_search_filters(key=key)
    
    # Realizar búsqueda
    selected_paciente = None
    
    if query and len(query) >= 2:
        engine = SmartSearchEngine()
        results = engine.search(
            query=query,
            items=pacientes_data,
            searchable_fields=["nombre_completo", "dni", "obra_social", "telefono", "email"],
            filters=filters if filters else None,
            limit=20,
        )
        
        if results:
            st.markdown("---")
            
            # Mostrar resultados
            for i, result in enumerate(results):
                clicked = render_search_result_card(result, key_suffix=f"{key}_{i}")
                
                if clicked:
                    selected_paciente = result
                    # Guardar selección en session_state
                    st.session_state[f"{key}_selected"] = result.id
                    st.toast(f"✅ Paciente seleccionado: {result.title}")
                    st.rerun()
    
    elif query and len(query) < 2:
        st.caption("💡 Escribe al menos 2 caracteres para buscar")
    
    else:
        # Mostrar pacientes recientes o destacados
        st.markdown("### ⭐ Pacientes Recientes")
        recientes = pacientes_data[:5]  # Últimos 5
        
        for i, paciente in enumerate(recientes):
            result = SearchResult(
                id=str(paciente.get("id", "")),
                title=paciente.get("nombre_completo", "Sin nombre"),
                subtitle=f"DNI: {paciente.get('dni', 'N/A')}",
                badge=paciente.get("estado", "Activo"),
                badge_type="success" if paciente.get("estado") == "Activo" else "info",
                metadata={"obra_social": paciente.get("obra_social", "")},
            )
            
            clicked = render_search_result_card(result, key_suffix=f"recent_{i}")
            if clicked:
                selected_paciente = result
                st.session_state[f"{key}_selected"] = result.id
                st.rerun()
    
    return selected_paciente


# ============================================================
# BÚSQUEDA EN SIDEBAR (reemplazo mejorado)
# ============================================================

def render_sidebar_smart_search(
    pacientes_data: List[Dict[str, Any]],
    on_paciente_selected: Optional[Callable[[str], None]] = None,
) -> Optional[str]:
    """
    Versión compacta del buscador para el sidebar.
    
    Returns:
        ID del paciente seleccionado
    """
    st.markdown("""
    <style>
    .mc-sidebar-search {
        margin-bottom: 1rem;
    }
    .mc-sidebar-search input {
        background: rgba(15, 23, 42, 0.6) !important;
        border: 1px solid rgba(148, 163, 184, 0.2) !important;
        border-radius: 8px !important;
        color: #f1f5f9 !important;
        padding: 0.625rem 0.875rem !important;
    }
    .mc-sidebar-search input:focus {
        border-color: #3b82f6 !important;
        box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15) !important;
    }
    </style>
    """, unsafe_allow_html=True)
    
    st.markdown('<div class="mc-sidebar-search">', unsafe_allow_html=True)
    
    query = st.text_input(
        "🔍 Buscar",
        placeholder="Nombre o DNI...",
        key="sidebar_smart_search",
        label_visibility="collapsed",
    )
    
    st.markdown('</div>', unsafe_allow_html=True)
    
    selected_id = None
    
    if query and len(query) >= 2:
        engine = SmartSearchEngine()
        results = engine.search(
            query=query,
            items=pacientes_data,
            searchable_fields=["nombre_completo", "dni"],
            limit=10,
        )
        
        if results:
            # Mostrar como selectbox mejorado
            options = {r.id: f"{r.title} ({r.metadata.get('dni', 'N/A')})" for r in results}
            
            selected = st.selectbox(
                "Resultados",
                options=list(options.keys()),
                format_func=lambda x: options.get(x, x),
                key="sidebar_search_results",
                label_visibility="collapsed",
            )
            
            if selected:
                selected_id = selected
                if on_paciente_selected:
                    on_paciente_selected(selected_id)
    
    return selected_id
