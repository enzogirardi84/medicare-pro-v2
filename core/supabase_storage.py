"""
Sistema robusto de guardado en Supabase
- Guarda directamente en la nube
- Manejo de errores con retry
- No ocupa RAM (no guarda todo en session_state)
- Lazy loading para datos históricos
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional, Callable
from functools import wraps

import streamlit as st
from core.app_logging import log_event


class SupabaseStorage:
    """Sistema de almacenamiento en Supabase con manejo robusto de errores."""
    
    def __init__(self, max_retries: int = 3, retry_delay: float = 0.5):
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._supabase = None
        
    def _get_supabase(self):
        """Obtiene cliente Supabase con lazy loading."""
        if self._supabase is None:
            try:
                from core.database import supabase
                self._supabase = supabase
            except Exception as e:
                log_event("supabase_storage", f"Error conectando: {e}")
                return None
        return self._supabase
    
    def guardar_signos_vitales(
        self,
        paciente_id: str,
        usuario_id: str,
        tension_arterial: str,
        frecuencia_cardiaca: int,
        frecuencia_respiratoria: int,
        temperatura: float,
        saturacion_oxigeno: int,
        glucemia: str,
        observaciones: str = ""
    ) -> tuple[bool, Optional[str]]:
        """
        Guarda signos vitales en Supabase con retry.
        
        Returns:
            (exito, error_message)
        """
        supabase = self._get_supabase()
        if not supabase:
            return False, "No hay conexion a Supabase"
        
        data = {
            "paciente_id": paciente_id,
            "usuario_id": usuario_id,
            "tension_arterial": tension_arterial,
            "frecuencia_cardiaca": frecuencia_cardiaca,
            "frecuencia_respiratoria": frecuencia_respiratoria,
            "temperatura": temperatura,
            "saturacion_oxigeno": saturacion_oxigeno,
            "glucemia": glucemia if glucemia else None,
            "observaciones": observaciones if observaciones else None
        }
        
        # Retry logic
        for attempt in range(self.max_retries):
            try:
                response = supabase.table("signos_vitales").insert(data).execute()
                
                # Verificar que se insertó
                if hasattr(response, 'data') and response.data:
                    log_event("signos_vitales", f"Guardado OK - Paciente: {paciente_id}")
                    return True, None
                else:
                    raise Exception("No se confirmo la insercion")
                    
            except Exception as e:
                error_msg = str(e)
                log_event("signos_vitales", f"Intento {attempt+1} fallo: {error_msg}")
                
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay * (attempt + 1))  # Exponential backoff
                else:
                    return False, f"Error despues de {self.max_retries} intentos: {error_msg}"
        
        return False, "Error desconocido"
    
    def obtener_signos_vitales(
        self,
        paciente_id: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """
        Obtiene signos vitales de un paciente (lazy loading).
        No carga todo en RAM, solo los necesarios.
        """
        supabase = self._get_supabase()
        if not supabase:
            return []
        
        try:
            response = (
                supabase.table("signos_vitales")
                .select("*")
                .eq("paciente_id", paciente_id)
                .order("fecha_registro", desc=True)
                .limit(limit)
                .offset(offset)
                .execute()
            )
            
            return response.data if hasattr(response, 'data') else []
            
        except Exception as e:
            log_event("signos_vitales", f"Error leyendo: {e}")
            return []
    
    def contar_signos_vitales(self, paciente_id: str) -> int:
        """Cuenta signos vitales sin cargar todos los datos."""
        supabase = self._get_supabase()
        if not supabase:
            return 0
        
        try:
            response = (
                supabase.table("signos_vitales")
                .select("count", count="exact")
                .eq("paciente_id", paciente_id)
                .execute()
            )
            return response.count if hasattr(response, 'count') else 0
        except Exception:
            return 0


# Instancia global
_storage = None

def get_supabase_storage() -> SupabaseStorage:
    """Obtiene instancia unica de SupabaseStorage."""
    global _storage
    if _storage is None:
        _storage = SupabaseStorage()
    return _storage


def guardar_signos_vitales_seguro(
    paciente_id: str,
    tension_arterial: str,
    frecuencia_cardiaca: int,
    frecuencia_respiratoria: int,
    temperatura: float,
    saturacion_oxigeno: int,
    glucemia: str,
    observaciones: str = ""
) -> tuple[bool, str]:
    """
    Funcion de ayuda para guardar signos vitales con manejo de errores.
    
    Returns:
        (exito, mensaje)
    """
    storage = get_supabase_storage()
    
    # Obtener usuario actual
    usuario_id = None
    if "user" in st.session_state:
        user = st.session_state["user"]
        if isinstance(user, dict):
            usuario_id = user.get("id") or user.get("email")
    
    exito, error = storage.guardar_signos_vitales(
        paciente_id=paciente_id,
        usuario_id=usuario_id or "sistema",
        tension_arterial=tension_arterial,
        frecuencia_cardiaca=frecuencia_cardiaca,
        frecuencia_respiratoria=frecuencia_respiratoria,
        temperatura=temperatura,
        saturacion_oxigeno=saturacion_oxigeno,
        glucemia=glucemia,
        observaciones=observaciones
    )
    
    if exito:
        return True, "Signos vitales guardados correctamente en la nube"
    else:
        return False, f"Error al guardar: {error}"


def obtener_signos_vitales_paciente(
    paciente_id: str,
    pagina: int = 1,
    por_pagina: int = 20
) -> List[Dict]:
    """
    Obtiene signos vitales paginados (no ocupa RAM).
    
    Args:
        pagina: Numero de pagina (1-based)
        por_pagina: Cuantos registros por pagina
    """
    storage = get_supabase_storage()
    offset = (pagina - 1) * por_pagina
    
    return storage.obtener_signos_vitales(
        paciente_id=paciente_id,
        limit=por_pagina,
        offset=offset
    )
