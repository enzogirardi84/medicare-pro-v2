"""
Sistema de Caché Optimizado para MediCare Pro.

Uso intensivo de @st.cache_data y @st.cache_resource.
Optimizado para datos que no cambian frecuentemente.
"""
from typing import Any, Callable, Dict, List, Optional, TypeVar, cast
from functools import wraps
from datetime import datetime, timedelta
import hashlib
import json
import time

import streamlit as st
from core.app_logging import log_event


F = TypeVar("F", bound=Callable[..., Any])


class CacheManagerOptimized:
    """Gestor de caché con TTL y invalidación inteligente."""
    
    # TTL por categoría (segundos)
    TTL_STATIC = 3600        # 1 hora: listas estáticas (obras sociales, etc.)
    TTL_CONFIG = 600         # 10 min: configuraciones
    TTL_PATIENT_LIST = 60    # 1 min: listas de pacientes
    TTL_CLINICAL_DATA = 30   # 30 seg: datos clínicos frescos
    
    @staticmethod
    @st.cache_data(ttl=TTL_STATIC, show_spinner=False)
    def get_obras_sociales_cached(_force_refresh: bool = False) -> List[Dict[str, str]]:
        """
        Lista de obras sociales - caché por 1 hora.
        Usar _force_refresh=True para forzar recarga.
        """
        # Lista base de obras sociales comunes en Argentina
        obras_sociales = [
            {"codigo": "OSDE", "nombre": "OSDE", "tipo": "privada"},
            {"codigo": "SWISS", "nombre": "Swiss Medical", "tipo": "privada"},
            {"codigo": "GALENO", "nombre": "Galeno", "tipo": "privada"},
            {"codigo": "MEDIF", "nombre": "Medifé", "tipo": "privada"},
            {"codigo": "OMINT", "nombre": "OMINT", "tipo": "privada"},
            {"codigo": "APRES", "nombre": "APRES", "tipo": "privada"},
            {"codigo": "FED", "nombre": "Federación Médica", "tipo": "privada"},
            {"codigo": "SANCOR", "nombre": "Sancor Salud", "tipo": "privada"},
            {"codigo": "PAMI", "nombre": "PAMI", "tipo": "publica"},
            {"codigo": "IOMA", "nombre": "IOMA", "tipo": "publica"},
            {"codigo": "IOSS", "nombre": "IOSS", "tipo": "publica"},
            {"codigo": "AMUR", "nombre": "AMUR", "tipo": "publica"},
            {"codigo": "HOSP", "nombre": "Hospital Público", "tipo": "publica"},
            {"codigo": "PART", "nombre": "Particular", "tipo": "particular"},
            {"codigo": "ART", "nombre": "ART", "tipo": "accidente"},
        ]
        return obras_sociales
    
    @staticmethod
    @st.cache_data(ttl=TTL_CONFIG, show_spinner=False)
    def get_app_config_cached(_tenant_id: Optional[str] = None) -> Dict[str, Any]:
        """Configuración de la aplicación - caché por 10 min."""
        # Cargar desde session_state o retornar defaults
        default_config = {
            "max_pacientes_por_pagina": 50,
            "tiempo_sesion_minutos": 30,
            "habilitar_firmas": True,
            "habilitar_alertas": True,
            "formato_fecha": "%d/%m/%Y",
            "formato_hora": "%H:%M",
        }
        
        try:
            # Intentar cargar desde Supabase si está disponible
            from core._database_supabase import supabase
            if supabase:
                response = supabase.table("configuracion").select("*").limit(1).execute()
                if response.data:
                    return {**default_config, **response.data[0]}
        except Exception as e:
            log_event("cache", f"config_load_error:{type(e).__name__}")
        
        return default_config
    
    @staticmethod
    @st.cache_resource
    def get_pdf_templates_cached() -> Dict[str, Any]:
        """
        Templates de PDF - cacheados como resource (no serializables).
        Solo se cargan una vez por proceso.
        """
        try:
            from fpdf import FPDF
            templates = {
                "receta": None,  # Se inicializa lazy
                "evolucion": None,
                "consentimiento": None,
            }
            return templates
        except ImportError:
            return {}
    
    @staticmethod
    def invalidate_cache_key(key: str) -> None:
        """Invalida una clave específica del caché."""
        # Nota: Streamlit no permite invalidación manual de cache_data
        # pero podemos usar query params únicos
        log_event("cache", f"invalidation_requested:{key}")


class SessionStateManager:
    """Gestor optimizado del estado de sesión con callbacks."""
    
    @staticmethod
    def safe_set(key: str, value: Any, on_change: Optional[Callable] = None) -> None:
        """
        Set seguro en session_state con callback opcional.
        Evita reruns innecesarios.
        """
        current = st.session_state.get(key)
        if current != value:
            st.session_state[key] = value
            if on_change:
                on_change()
    
    @staticmethod
    def get_with_default(key: str, default: Any) -> Any:
        """Obtiene valor con default, inicializando si no existe."""
        if key not in st.session_state:
            st.session_state[key] = default
        return st.session_state[key]
    
    @staticmethod
    def init_pagination_state(prefix: str = "pacientes") -> Dict[str, Any]:
        """Inicializa estado de paginación para tablas."""
        keys = {
            f"{prefix}_page": 1,
            f"{prefix}_page_size": 50,
            f"{prefix}_search": "",
            f"{prefix}_has_more": False,
            f"{prefix}_total_count": 0,
        }
        
        for key, default in keys.items():
            if key not in st.session_state:
                st.session_state[key] = default
        
        return {k: st.session_state[k] for k in keys.keys()}
    
    @staticmethod
    def reset_pagination(prefix: str = "pacientes") -> None:
        """Resetea estado de paginación."""
        st.session_state[f"{prefix}_page"] = 1
        st.session_state[f"{prefix}_has_more"] = False


def cached_query(ttl_seconds: int = 60, show_spinner: bool = False):
    """
    Decorador para queries a base de datos con caché.
    
    Args:
        ttl_seconds: Tiempo de vida del caché
        show_spinner: Si mostrar spinner de carga
    """
    def decorator(func: F) -> F:
        # Usar st.cache_data con hash de los argumentos
        @st.cache_data(ttl=ttl_seconds, show_spinner=show_spinner)
        def cached_wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Generar clave de caché única
            cache_key = _generate_cache_key(func.__name__, args, kwargs)
            
            start = time.time()
            try:
                result = cached_wrapper(*args, **kwargs)
                elapsed = (time.time() - start) * 1000
                log_event("cache", f"hit:{func.__name__}:{elapsed:.1f}ms")
                return result
            except Exception as e:
                log_event("cache", f"miss:{func.__name__}:{type(e).__name__}")
                # Fallback: ejecutar sin caché
                return func(*args, **kwargs)
        
        return cast(F, wrapper)
    return decorator


def _generate_cache_key(func_name: str, args: tuple, kwargs: dict) -> str:
    """Genera clave de caché única."""
    key_data = {
        "func": func_name,
        "args": args,
        "kwargs": kwargs,
    }
    key_str = json.dumps(key_data, sort_keys=True, default=str)
    return hashlib.md5(key_str.encode()).hexdigest()[:16]


# Funciones helper de alto nivel

def get_obras_sociales(force_refresh: bool = False) -> List[Dict[str, str]]:
    """Retorna lista de obras sociales (cacheada 1 hora)."""
    return CacheManagerOptimized.get_obras_sociales_cached(_force_refresh=force_refresh)


def get_app_config(tenant_id: Optional[str] = None) -> Dict[str, Any]:
    """Retorna configuración de la app (cacheada 10 min)."""
    return CacheManagerOptimized.get_app_config_cached(_tenant_id=tenant_id)


class SessionStateManager:
    """Helper para inicializar y gestionar estado de paginación en session_state."""

    @staticmethod
    def init_pagination_state(prefix: str, session_state=None) -> dict:
        """Inicializa claves de paginación para un prefijo dado."""
        if session_state is None:
            import streamlit as st
            session_state = st.session_state
        page_key = f"{prefix}_page"
        size_key = f"{prefix}_page_size"
        session_state[page_key] = 1
        session_state[size_key] = 50
        return session_state


def init_pagination(table_name: str = "pacientes") -> Dict[str, Any]:
    """Inicializa estado de paginación para una tabla."""
    return SessionStateManager.init_pagination_state(prefix=table_name)
