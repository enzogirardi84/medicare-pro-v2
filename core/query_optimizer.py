"""
Optimizador de consultas para grandes datasets.

- Índices en memoria para búsquedas O(1)
- Búsqueda binaria para listas ordenadas
- Filtro Bloom para membership testing
- Compresión de datos grandes
"""

from __future__ import annotations

import hashlib
import math
import pickle
import zlib
from bisect import bisect_left, bisect_right
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Generic, List, Optional, Set, Tuple, TypeVar

import streamlit as st

T = TypeVar('T')


class BloomFilter:
    """
    Filtro Bloom para membership testing eficiente.
    
    Usa poca memoria para determinar si un elemento "quizás" está en un set.
    Falso positivo: posible | Falso negativo: imposible
    """

    def __init__(self, capacity: int, false_positive_rate: float = 0.01):
        self.capacity = capacity
        self.fp_rate = false_positive_rate
        
        # Calcular tamaño óptimo
        self.size = self._optimal_size(capacity, false_positive_rate)
        self.hash_count = self._optimal_hash_count(self.size, capacity)
        
        # Bits (usamos bytearray para eficiencia)
        self.bit_array = bytearray(self.size // 8 + 1)
        self._count = 0

    def _optimal_size(self, n: int, p: float) -> int:
        """Calcula tamaño óptimo del bit array."""
        return int(-n * math.log(p) / (math.log(2) ** 2))

    def _optimal_hash_count(self, m: int, n: int) -> int:
        """Calcula número óptimo de funciones hash."""
        return max(1, int((m / n) * math.log(2)))

    def _hashes(self, item: str) -> List[int]:
        """Genera múltiples hashes para un item."""
        # Usar dos hashes independientes y combinar (Kirsch-Mitzenmacher)
        h1 = hashlib.md5(item.encode()).hexdigest()
        h2 = hashlib.sha256(item.encode()).hexdigest()
        
        int1 = int(h1[:16], 16)
        int2 = int(h2[:16], 16)
        
        return [
            ((int1 + i * int2) % self.size)
            for i in range(self.hash_count)
        ]

    def add(self, item: str):
        """Agrega un elemento al filtro."""
        for pos in self._hashes(item):
            byte_idx = pos // 8
            bit_idx = pos % 8
            self.bit_array[byte_idx] |= (1 << bit_idx)
        self._count += 1

    def __contains__(self, item: str) -> bool:
        """Verifica si un elemento quizás está en el filtro."""
        for pos in self._hashes(item):
            byte_idx = pos // 8
            bit_idx = pos % 8
            if not (self.bit_array[byte_idx] & (1 << bit_idx)):
                return False
        return True

    def __len__(self) -> int:
        return self._count


@dataclass
class IndexEntry:
    """Entrada de índice para búsqueda rápida."""
    key: str
    value: Any
    positions: List[int] = field(default_factory=list)


class InMemoryIndex:
    """
    Índice en memoria para búsquedas O(1).
    
    Crea índices hash sobre campos frecuentemente consultados.
    """

    def __init__(self, field: str, unique: bool = False):
        self.field = field
        self.unique = unique
        self._index: Dict[str, List[int]] = {}
        self._bloom: Optional[BloomFilter] = None
        self._total_items = 0

    def build(self, items: List[T], key_extractor: Callable[[T], Any]):
        """Construye el índice sobre una lista de items."""
        self._index.clear()
        self._total_items = len(items)
        
        # Crear Bloom filter para membership testing rápido
        if self._total_items > 1000:
            self._bloom = BloomFilter(self._total_items)
        
        for pos, item in enumerate(items):
            key = str(key_extractor(item))
            
            if self._bloom is not None:
                self._bloom.add(key)
            
            if key not in self._index:
                self._index[key] = []
            
            if self.unique and self._index[key]:
                raise ValueError(f"Duplicado en índice único: {key}")
            
            self._index[key].append(pos)

    def lookup(self, value: Any) -> List[int]:
        """Busca un valor en el índice. Retorna posiciones."""
        key = str(value)
        
        # Verificar Bloom filter primero (si existe)
        if self._bloom is not None:
            if key not in self._bloom:
                return []  # Definitivamente no está
        
        return self._index.get(key, [])

    def exists(self, value: Any) -> bool:
        """Verifica si un valor existe en el índice."""
        return len(self.lookup(value)) > 0

    def get_stats(self) -> Dict[str, Any]:
        """Estadísticas del índice."""
        return {
            "field": self.field,
            "unique": self.unique,
            "total_keys": len(self._index),
            "total_items": self._total_items,
            "avg_bucket_size": (
                sum(len(v) for v in self._index.values()) / len(self._index)
                if self._index else 0
            ),
            "has_bloom_filter": self._bloom is not None,
        }


class BinarySearchHelper:
    """
    Helper para búsqueda binaria en listas ordenadas.
    """

    @staticmethod
    def find_insertion_point(
        sorted_list: List[T],
        value: Any,
        key: Callable[[T], Any] = lambda x: x,
    ) -> int:
        """Encuentra punto de inserción manteniendo orden."""
        keys = [key(x) for x in sorted_list]
        return bisect_left(keys, value)

    @staticmethod
    def find_range(
        sorted_list: List[T],
        min_val: Any,
        max_val: Any,
        key: Callable[[T], Any] = lambda x: x,
    ) -> List[T]:
        """Encuentra todos los elementos en un rango."""
        keys = [key(x) for x in sorted_list]
        left = bisect_left(keys, min_val)
        right = bisect_right(keys, max_val)
        return sorted_list[left:right]

    @staticmethod
    def find_exact(
        sorted_list: List[T],
        value: Any,
        key: Callable[[T], Any] = lambda x: x,
    ) -> Optional[T]:
        """Busca un elemento exacto."""
        keys = [key(x) for x in sorted_list]
        pos = bisect_left(keys, value)
        if pos < len(sorted_list) and key(sorted_list[pos]) == value:
            return sorted_list[pos]
        return None


class DataCompressor:
    """
    Compresión de datos para session_state.
    
    Reduce uso de memoria para datos grandes.
    """

    @staticmethod
    def compress(data: Any) -> bytes:
        """Comprime datos con zlib."""
        pickled = pickle.dumps(data, protocol=pickle.HIGHEST_PROTOCOL)
        return zlib.compress(pickled)

    @staticmethod
    def decompress(compressed: bytes) -> Any:
        """Descomprime datos."""
        decompressed = zlib.decompress(compressed)
        return pickle.loads(decompressed)

    @staticmethod
    def should_compress(data: Any, threshold_bytes: int = 1024) -> bool:
        """Determina si los datos deberían comprimirse."""
        try:
            size = len(pickle.dumps(data))
            return size > threshold_bytes
        except Exception:
            return False


class QueryOptimizer:
    """
    Optimizador de consultas con múltiples estrategias.
    """

    def __init__(self):
        self._indexes: Dict[str, InMemoryIndex] = {}
        self._sorted_data: Dict[str, List[T]] = {}
        self._compressor = DataCompressor()

    def create_index(
        self,
        name: str,
        items: List[T],
        field: str,
        key_extractor: Callable[[T], Any],
        unique: bool = False,
    ):
        """Crea un índice para búsquedas rápidas."""
        index = InMemoryIndex(field, unique)
        index.build(items, key_extractor)
        self._indexes[name] = index

    def query_by_index(
        self,
        index_name: str,
        value: Any,
        items: List[T],
    ) -> List[T]:
        """Consulta usando un índice."""
        index = self._indexes.get(index_name)
        if index is None:
            # Fallback a búsqueda lineal
            return [item for item in items if str(value) in str(item)]
        
        positions = index.lookup(value)
        return [items[pos] for pos in positions]

    def sort_data(
        self,
        name: str,
        items: List[T],
        key: Callable[[T], Any],
        reverse: bool = False,
    ) -> List[T]:
        """Ordena y cachea datos para búsqueda binaria."""
        sorted_items = sorted(items, key=key, reverse=reverse)
        self._sorted_data[name] = sorted_items
        return sorted_items

    def binary_search(
        self,
        sorted_name: str,
        value: Any,
        key: Callable[[T], Any] = lambda x: x,
    ) -> Optional[T]:
        """Búsqueda binaria en datos ordenados."""
        sorted_list = self._sorted_data.get(sorted_name, [])
        return BinarySearchHelper.find_exact(sorted_list, value, key)

    def range_query(
        self,
        sorted_name: str,
        min_val: Any,
        max_val: Any,
        key: Callable[[T], Any] = lambda x: x,
    ) -> List[T]:
        """Consulta por rango en datos ordenados."""
        sorted_list = self._sorted_data.get(sorted_name, [])
        return BinarySearchHelper.find_range(sorted_list, min_val, max_val, key)

    def store_compressed(self, key: str, data: Any) -> bool:
        """Almacena datos comprimidos en session_state."""
        try:
            if self._compressor.should_compress(data):
                compressed = self._compressor.compress(data)
                st.session_state[f"_compressed_{key}"] = compressed
                return True
            else:
                st.session_state[key] = data
                return False
        except Exception:
            st.session_state[key] = data
            return False

    def retrieve_compressed(self, key: str) -> Any:
        """Recupera datos posiblemente comprimidos."""
        # Intentar comprimido primero
        compressed_key = f"_compressed_{key}"
        if compressed_key in st.session_state:
            try:
                compressed = st.session_state[compressed_key]
                return self._compressor.decompress(compressed)
            except Exception as _exc:
                import logging
                logging.getLogger("query_optimizer").debug(f"fallo_decompress:{type(_exc).__name__}")
        
        # Fallback a normal
        return st.session_state.get(key)

    def get_stats(self) -> Dict[str, Any]:
        """Estadísticas del optimizador."""
        return {
            "indexes": {
                name: idx.get_stats()
                for name, idx in self._indexes.items()
            },
            "sorted_datasets": list(self._sorted_data.keys()),
        }


# Instancia global
_optimizer_instance: Optional[QueryOptimizer] = None


def get_query_optimizer() -> QueryOptimizer:
    """Obtiene instancia global del optimizador."""
    global _optimizer_instance
    if _optimizer_instance is None:
        _optimizer_instance = QueryOptimizer()
    return _optimizer_instance


def create_bloom_filter(capacity: int, fp_rate: float = 0.01) -> BloomFilter:
    """Crea un filtro Bloom."""
    return BloomFilter(capacity, fp_rate)


def compress_large_data(data: Any, threshold_kb: int = 10) -> Tuple[Any, bool]:
    """
    Comprime datos si son grandes.
    
    Returns:
        (data, was_compressed)
    """
    compressor = DataCompressor()
    try:
        pickled = pickle.dumps(data)
        if len(pickled) > threshold_kb * 1024:
            compressed = compressor.compress(data)
            return compressed, True
    except Exception as _exc:
        import logging
        logging.getLogger("query_optimizer").debug(f"fallo_compress:{type(_exc).__name__}")
    return data, False


def decompress_if_needed(data: Any) -> Any:
    """Descomprime datos si están comprimidos."""
    if isinstance(data, bytes):
        try:
            return DataCompressor.decompress(data)
        except Exception as _exc:
            import logging
            logging.getLogger("query_optimizer").debug(f"fallo_decompress_if_needed:{type(_exc).__name__}")
    return data
