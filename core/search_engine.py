"""
Motor de Búsqueda Avanzada para Medicare Pro.

Características:
- Búsqueda full-text en pacientes, evoluciones, diagnósticos
- Filtros avanzados (rango de fechas, médico, diagnóstico)
- Autocomplete/sugerencias
- Búsqueda fuzzy (tolerante a errores tipográficos)
- Indexación incremental
- Ranking de resultados por relevancia
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple, Set
from collections import defaultdict
import streamlit as st

from core.app_logging import log_event
from core.data_validation import get_validator


@dataclass
class SearchResult:
    """Resultado de búsqueda."""
    id: str
    type: str  # paciente, evolucion, receta, etc.
    title: str
    subtitle: str
    highlights: List[str]  # Fragmentos con matches resaltados
    score: float  # Relevancia 0-1
    data: Dict[str, Any]  # Datos completos
    last_modified: Optional[datetime] = None


class SearchIndex:
    """
    Índice de búsqueda en memoria.
    
    Para producción, considerar:
    - Elasticsearch
    - Algolia
    - Meilisearch
    - SQLite FTS
    """
    
    def __init__(self):
        self._index: Dict[str, Dict[str, Set[str]]] = defaultdict(lambda: defaultdict(set))
        self._documents: Dict[str, Dict[str, Any]] = {}
        self._last_updated: Dict[str, datetime] = {}
    
    def add_document(self, doc_id: str, doc_type: str, fields: Dict[str, Any]):
        """
        Agrega documento al índice.
        
        Args:
            doc_id: ID único del documento
            doc_type: Tipo (paciente, evolucion, etc.)
            fields: Campos a indexar {field_name: value}
        """
        key = f"{doc_type}:{doc_id}"
        
        # Guardar documento
        self._documents[key] = {
            "id": doc_id,
            "type": doc_type,
            "fields": fields
        }
        
        # Indexar campos
        for field_name, value in fields.items():
            if value is None:
                continue
            
            # Tokenizar
            tokens = self._tokenize(str(value))
            
            for token in tokens:
                # Indexar en trigramas para búsqueda fuzzy
                trigrams = self._get_trigrams(token)
                for trigram in trigrams:
                    self._index[field_name][trigram].add(key)
                
                # Indexar token completo
                self._index[field_name][token].add(key)
        
        self._last_updated[key] = datetime.now()
        
        log_event("search", f"Indexed document: {key}")
    
    def remove_document(self, doc_id: str, doc_type: str):
        """Elimina documento del índice."""
        key = f"{doc_type}:{doc_id}"
        
        if key in self._documents:
            del self._documents[key]
        
        # Limpiar índice
        for field_index in self._index.values():
            for token_set in field_index.values():
                token_set.discard(key)
        
        if key in self._last_updated:
            del self._last_updated[key]
    
    def _tokenize(self, text: str) -> List[str]:
        """Tokeniza texto para indexación."""
        # Normalizar
        text = text.lower().strip()
        
        # Eliminar acentos
        text = self._remove_accents(text)
        
        # Split en palabras
        tokens = re.findall(r'\b\w+\b', text)
        
        # Filtrar stopwords cortas
        return [t for t in tokens if len(t) >= 2]
    
    def _remove_accents(self, text: str) -> str:
        """Elimina acentos del texto."""
        accents = {
            'á': 'a', 'é': 'e', 'í': 'i', 'ó': 'o', 'ú': 'u',
            'Á': 'A', 'É': 'E', 'Í': 'I', 'Ó': 'O', 'Ú': 'U',
            'ñ': 'n', 'Ñ': 'N'
        }
        for accented, unaccented in accents.items():
            text = text.replace(accented, unaccented)
        return text
    
    def _get_trigrams(self, token: str) -> List[str]:
        """Genera trigramas para búsqueda fuzzy."""
        if len(token) < 3:
            return [token]
        
        return [token[i:i+3] for i in range(len(token) - 2)]
    
    def search(
        self,
        query: str,
        doc_types: Optional[List[str]] = None,
        fields: Optional[List[str]] = None,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20,
        fuzzy: bool = True
    ) -> List[SearchResult]:
        """
        Busca en el índice.
        
        Args:
            query: Términos de búsqueda
            doc_types: Filtrar por tipos (None = todos)
            fields: Buscar solo en estos campos
            filters: Filtros adicionales {field: value}
            limit: Máximo resultados
            fuzzy: Permitir búsqueda aproximada
        
        Returns:
            Lista de resultados ordenados por relevancia
        """
        if not query or not query.strip():
            return []
        
        # Tokenizar query
        query_tokens = self._tokenize(query)
        
        if not query_tokens:
            return []
        
        # Buscar matches
        candidate_scores: Dict[str, float] = defaultdict(float)
        
        search_fields = fields or list(self._index.keys())
        
        for token in query_tokens:
            for field in search_fields:
                if field not in self._index:
                    continue
                
                # Búsqueda exacta
                if token in self._index[field]:
                    for doc_key in self._index[field][token]:
                        candidate_scores[doc_key] += 1.0  # Score base
                
                # Búsqueda fuzzy (trigramas)
                if fuzzy and len(token) >= 3:
                    trigrams = self._get_trigrams(token)
                    for trigram in trigrams:
                        if trigram in self._index[field]:
                            for doc_key in self._index[field][trigram]:
                                candidate_scores[doc_key] += 0.3  # Score menor
        
        # Filtrar por tipo y filtros adicionales
        filtered_results = []
        
        for doc_key, score in candidate_scores.items():
            if doc_key not in self._documents:
                continue
            
            doc = self._documents[doc_key]
            
            # Filtrar por tipo
            if doc_types and doc["type"] not in doc_types:
                continue
            
            # Aplicar filtros adicionales
            if filters:
                match = True
                for filter_field, filter_value in filters.items():
                    if filter_field not in doc["fields"]:
                        match = False
                        break
                    if str(doc["fields"][filter_field]) != str(filter_value):
                        match = False
                        break
                if not match:
                    continue
            
            # Normalizar score
            normalized_score = score / (len(query_tokens) * 1.0)
            
            # Crear resultado
            result = self._create_search_result(doc_key, normalized_score, query_tokens)
            if result:
                filtered_results.append(result)
        
        # Ordenar por score
        filtered_results.sort(key=lambda x: x.score, reverse=True)
        
        return filtered_results[:limit]
    
    def _create_search_result(
        self,
        doc_key: str,
        score: float,
        query_tokens: List[str]
    ) -> Optional[SearchResult]:
        """Crea objeto SearchResult desde documento."""
        if doc_key not in self._documents:
            return None
        
        doc = self._documents[doc_key]
        fields = doc["fields"]
        doc_type = doc["type"]
        doc_id = doc["id"]
        
        # Generar título y subtítulo según tipo
        if doc_type == "paciente":
            title = f"{fields.get('apellido', '')}, {fields.get('nombre', '')}"
            subtitle = f"DNI: {fields.get('dni', 'N/A')} | {fields.get('obra_social', 'Sin OS')}"
        elif doc_type == "evolucion":
            title = f"Evolución - {fields.get('fecha', 'Sin fecha')}"
            subtitle = f"Dr. {fields.get('medico_nombre', 'Desconocido')}"
        elif doc_type == "receta":
            title = f"Receta - {fields.get('fecha', 'Sin fecha')}"
            subtitle = f"Paciente: {fields.get('paciente_nombre', 'Desconocido')}"
        else:
            title = f"{doc_type.title()} - {doc_id[:8]}"
            subtitle = ""
        
        # Generar highlights
        highlights = []
        for field_name, field_value in fields.items():
            if field_value is None:
                continue
            
            field_str = str(field_value).lower()
            for token in query_tokens:
                if token in field_str:
                    # Extraer fragmento con contexto
                    idx = field_str.find(token)
                    start = max(0, idx - 30)
                    end = min(len(field_str), idx + len(token) + 30)
                    highlight = str(field_value)[start:end]
                    if start > 0:
                        highlight = "..." + highlight
                    if end < len(str(field_value)):
                        highlight = highlight + "..."
                    highlights.append(f"{field_name}: {highlight}")
                    break
        
        return SearchResult(
            id=doc_id,
            type=doc_type,
            title=title,
            subtitle=subtitle,
            highlights=highlights[:3],  # Max 3 highlights
            score=score,
            data=fields,
            last_modified=self._last_updated.get(doc_key)
        )
    
    def get_suggestions(self, query: str, limit: int = 5) -> List[str]:
        """
        Sugerencias de autocompletado.
        
        Args:
            query: Query parcial
            limit: Máximo sugerencias
        
        Returns:
            Lista de sugerencias
        """
        if len(query) < 2:
            return []
        
        query = query.lower()
        
        # Buscar tokens que empiecen con query
        suggestions = set()
        
        for field_index in self._index.values():
            for token in field_index.keys():
                if token.startswith(query) and len(token) > len(query):
                    suggestions.add(token)
        
        # Ordenar por frecuencia (approximado por número de documentos)
        sorted_suggestions = sorted(
            suggestions,
            key=lambda s: sum(len(field_index[s]) for field_index in self._index.values() if s in field_index),
            reverse=True
        )
        
        return sorted_suggestions[:limit]
    
    def get_stats(self) -> Dict[str, Any]:
        """Estadísticas del índice."""
        return {
            "total_documents": len(self._documents),
            "indexed_fields": len(self._index),
            "total_tokens": sum(len(tokens) for tokens in self._index.values()),
            "last_updated": max(self._last_updated.values()) if self._last_updated else None
        }


class SearchManager:
    """
    Manager de búsqueda que coordina el índice y las fuentes de datos.
    """
    
    def __init__(self):
        self.index = SearchIndex()
        self.validator = get_validator()
    
    def index_all_data(self):
        """Indexa todos los datos de la aplicación."""
        log_event("search", "Starting full reindex...")
        
        # Indexar pacientes
        pacientes_db = st.session_state.get("pacientes_db", {})
        for dni, paciente in pacientes_db.items():
            self.index.add_document(
                doc_id=paciente.get("id", dni),
                doc_type="paciente",
                fields={
                    "nombre": paciente.get("nombre", ""),
                    "apellido": paciente.get("apellido", ""),
                    "dni": dni,
                    "email": paciente.get("email", ""),
                    "obra_social": paciente.get("obra_social", ""),
                    "alergias": str(paciente.get("alergias", [])),
                    "medicamentos": str(paciente.get("medicamentos_actuales", []))
                }
            )
        
        # Indexar evoluciones
        evoluciones_db = st.session_state.get("evoluciones_db", [])
        for i, evo in enumerate(evoluciones_db):
            self.index.add_document(
                doc_id=evo.get("id", f"ev_{i}"),
                doc_type="evolucion",
                fields={
                    "nota": evo.get("nota", ""),
                    "diagnostico": evo.get("diagnostico", ""),
                    "tratamiento": evo.get("tratamiento", ""),
                    "fecha": evo.get("fecha", ""),
                    "medico_nombre": evo.get("medico_nombre", ""),
                    "paciente_id": evo.get("paciente_id", "")
                }
            )
        
        log_event("search", f"Indexing complete: {len(pacientes_db)} patients, {len(evoluciones_db)} evolutions")
    
    def search_patients(
        self,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 20
    ) -> List[SearchResult]:
        """Búsqueda específica de pacientes."""
        return self.index.search(
            query=query,
            doc_types=["paciente"],
            filters=filters,
            limit=limit
        )
    
    def search_medical_records(
        self,
        query: str,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        limit: int = 20
    ) -> List[SearchResult]:
        """Búsqueda en registros médicos (evoluciones, recetas)."""
        results = self.index.search(
            query=query,
            doc_types=["evolucion", "receta", "estudio"],
            limit=limit * 2  # Buscar más para filtrar después
        )
        
        # Filtrar por fecha si es necesario
        if date_from or date_to:
            filtered = []
            for result in results:
                result_date_str = result.data.get("fecha", "")
                if result_date_str:
                    try:
                        result_date = datetime.strptime(result_date_str[:10], "%d/%m/%Y").date()
                        
                        if date_from and result_date < date_from:
                            continue
                        if date_to and result_date > date_to:
                            continue
                        
                        filtered.append(result)
                    except:
                        filtered.append(result)
                else:
                    filtered.append(result)
            
            results = filtered[:limit]
        
        return results[:limit]
    
    def advanced_search(
        self,
        query: str,
        search_in: List[str],
        date_range: Optional[Tuple[Optional[date], Optional[date]]] = None,
        medico: Optional[str] = None,
        paciente_id: Optional[str] = None,
        limit: int = 20
    ) -> List[SearchResult]:
        """
        Búsqueda avanzada con múltiples filtros.
        
        Args:
            query: Términos de búsqueda
            search_in: Tipos a buscar ["pacientes", "evoluciones", "recetas"]
            date_range: (desde, hasta)
            medico: Filtrar por médico
            paciente_id: Filtrar por paciente
            limit: Máximo resultados
        """
        # Mapear tipos
        type_mapping = {
            "pacientes": "paciente",
            "evoluciones": "evolucion",
            "recetas": "receta"
        }
        
        doc_types = [type_mapping.get(t) for t in search_in if t in type_mapping]
        
        # Construir filtros
        filters = {}
        if medico:
            filters["medico_nombre"] = medico
        if paciente_id:
            filters["paciente_id"] = paciente_id
        
        # Buscar
        results = self.index.search(
            query=query,
            doc_types=doc_types if doc_types else None,
            filters=filters if filters else None,
            limit=limit * 2
        )
        
        # Filtrar por rango de fechas
        if date_range and (date_range[0] or date_range[1]):
            date_from, date_to = date_range
            filtered = []
            
            for result in results:
                result_date_str = result.data.get("fecha", "")
                if result_date_str:
                    try:
                        result_date = datetime.strptime(result_date_str[:10], "%d/%m/%Y").date()
                        
                        if date_from and result_date < date_from:
                            continue
                        if date_to and result_date > date_to:
                            continue
                        
                        filtered.append(result)
                    except:
                        filtered.append(result)
                else:
                    filtered.append(result)
            
            results = filtered
        
        return results[:limit]
    
    def render_search_ui(self):
        """Renderiza interfaz de búsqueda en Streamlit."""
        st.title("🔍 Búsqueda Avanzada")
        
        # Query input
        query = st.text_input(
            "Buscar",
            placeholder="Nombre, DNI, diagnóstico, nota...",
            key="search_query"
        )
        
        # Sugerencias
        if query and len(query) >= 2:
            suggestions = self.index.get_suggestions(query)
            if suggestions:
                st.caption(f"Sugerencias: {', '.join(suggestions[:5])}")
        
        # Filtros
        with st.expander("🔍 Filtros Avanzados"):
            col1, col2, col3 = st.columns(3)
            
            with col1:
                search_in = st.multiselect(
                    "Buscar en",
                    options=["Pacientes", "Evoluciones", "Recetas", "Estudios"],
                    default=["Pacientes", "Evoluciones"]
                )
            
            with col2:
                date_from = st.date_input("Desde", value=None)
                date_to = st.date_input("Hasta", value=None)
            
            with col3:
                st.text_input("Médico (opcional)", key="filter_medico")
                st.checkbox("Búsqueda exacta", value=False)
        
        # Ejecutar búsqueda
        if query:
            with st.spinner("Buscando..."):
                # Convertir filtros
                search_types = [s.lower() for s in search_in]
                
                # Buscar
                if len(query) < 2:
                    st.warning("Ingrese al menos 2 caracteres")
                    results = []
                else:
                    results = self.advanced_search(
                        query=query,
                        search_in=search_types,
                        date_range=(date_from, date_to) if date_from or date_to else None,
                        limit=50
                    )
            
            # Mostrar resultados
            st.subheader(f"Resultados ({len(results)})")
            
            if not results:
                st.info("No se encontraron resultados. Intente con otros términos.")
            else:
                for result in results:
                    with st.container():
                        col1, col2 = st.columns([1, 10])
                        
                        with col1:
                            # Icono según tipo
                            icons = {
                                "paciente": "👤",
                                "evolucion": "📝",
                                "receta": "💊",
                                "estudio": "🔬"
                            }
                            st.markdown(f"### {icons.get(result.type, '📄')}")
                        
                        with col2:
                            st.markdown(f"**{result.title}**")
                            st.caption(f"{result.subtitle} | Score: {result.score:.2f}")
                            
                            # Highlights
                            for highlight in result.highlights:
                                st.markdown(f"_{highlight}_")
                        
                        st.divider()
        
        # Stats del índice
        with st.sidebar:
            st.subheader("📊 Estadísticas de Búsqueda")
            stats = self.index.get_stats()
            st.metric("Documentos indexados", stats["total_documents"])
            st.metric("Campos indexados", stats["indexed_fields"])


# Singleton
_search_manager: Optional[SearchManager] = None


def get_search_manager() -> SearchManager:
    """Obtiene instancia del manager de búsqueda."""
    global _search_manager
    if _search_manager is None:
        _search_manager = SearchManager()
        # Indexar datos existentes
        _search_manager.index_all_data()
    return _search_manager


def quick_search(query: str, limit: int = 10) -> List[SearchResult]:
    """Búsqueda rápida."""
    return get_search_manager().search_patients(query, limit=limit)
