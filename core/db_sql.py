import time
from typing import Any, Dict, List, Optional
import streamlit as st

from core.app_logging import log_event

# Reutilizamos la inicialización del cliente de Supabase
try:
    from core.database import supabase, _supabase_execute_with_retry
except ImportError:
    supabase = None
    
    def _supabase_execute_with_retry(op_name: str, fn, attempts: int = 3, base_delay: float = 0.35):
        # Fallback simple si falla la importación
        for _ in range(attempts):
            try:
                return fn()
            except Exception:
                time.sleep(base_delay)
        return fn()


def check_supabase_connection() -> bool:
    """Verifica si el cliente de Supabase está inicializado."""
    return supabase is not None


# ==========================================
# GESTIÓN DE PACIENTES
# ==========================================

def get_pacientes_by_empresa(empresa_id: str, busqueda: str = "", incluir_altas: bool = False) -> List[Dict[str, Any]]:
    """Obtiene la lista de pacientes de una empresa, con paginación/búsqueda directa en SQL."""
    if not check_supabase_connection():
        return []
        
    query = supabase.table("pacientes").select("*").eq("empresa_id", empresa_id)
    
    if not incluir_altas:
        query = query.eq("estado", "Activo")
        
    if busqueda:
        # Búsqueda por nombre o DNI
        busqueda_limpia = busqueda.strip()
        query = query.or_(f"nombre_completo.ilike.%{busqueda_limpia}%,dni.ilike.%{busqueda_limpia}%")
        
    # Límite para no saturar memoria (protección anticolapso a nivel SQL)
    query = query.order("updated_at", desc=True).limit(100)
    
    try:
        response = _supabase_execute_with_retry("get_pacientes", lambda: query.execute())
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_pacientes:{type(e).__name__}")
        return []


def get_paciente_by_id(paciente_id: str) -> Optional[Dict[str, Any]]:
    """Obtiene los detalles completos de un paciente específico."""
    if not check_supabase_connection():
        return None
        
    try:
        response = _supabase_execute_with_retry(
            "get_paciente_id", 
            lambda: supabase.table("pacientes").select("*").eq("id", paciente_id).limit(1).execute()
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_get_paciente_id:{type(e).__name__}")
        return None


def upsert_paciente(datos_paciente: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta o actualiza un paciente. Maneja la concurrencia a nivel de base de datos."""
    if not check_supabase_connection():
        return None
        
    try:
        # Si tiene ID, actualizamos el updated_at
        if "id" in datos_paciente:
            from core.utils import ahora
            datos_paciente["updated_at"] = ahora().isoformat()
            
        response = _supabase_execute_with_retry(
            "upsert_paciente", 
            lambda: supabase.table("pacientes").upsert(datos_paciente).execute()
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_upsert_paciente:{type(e).__name__}")
        return None


# ==========================================
# GESTIÓN DE EVOLUCIONES
# ==========================================

def get_evoluciones_by_paciente(paciente_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    """Obtiene el historial de evoluciones de un paciente, ordenado por fecha."""
    if not check_supabase_connection():
        return []
        
    try:
        response = _supabase_execute_with_retry(
            "get_evoluciones", 
            lambda: supabase.table("evoluciones")
                .select("*, usuarios(nombre, matricula)")
                .eq("paciente_id", paciente_id)
                .order("fecha_registro", desc=True)
                .limit(limit)
                .execute()
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_evoluciones:{type(e).__name__}")
        return []


def insert_evolucion(datos_evolucion: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta una nueva evolución de forma atómica."""
    if not check_supabase_connection():
        return None
        
    try:
        response = _supabase_execute_with_retry(
            "insert_evolucion", 
            lambda: supabase.table("evoluciones").insert(datos_evolucion).execute()
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_evolucion:{type(e).__name__}")
        return None


# ==========================================
# GESTIÓN DE RECETAS / INDICACIONES
# ==========================================

def get_indicaciones_activas(paciente_id: str) -> List[Dict[str, Any]]:
    """Obtiene las indicaciones médicas activas para un paciente."""
    if not check_supabase_connection():
        return []
        
    try:
        response = _supabase_execute_with_retry(
            "get_indicaciones", 
            lambda: supabase.table("indicaciones")
                .select("*")
                .eq("paciente_id", paciente_id)
                .eq("estado", "Activa")
                .order("fecha_indicacion", desc=True)
                .execute()
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_indicaciones:{type(e).__name__}")
        return []


def insert_indicacion(datos_indicacion: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta una nueva indicación médica."""
    if not check_supabase_connection():
        return None
        
    try:
        response = _supabase_execute_with_retry(
            "insert_indicacion", 
            lambda: supabase.table("indicaciones").insert(datos_indicacion).execute()
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_indicacion:{type(e).__name__}")
        return None


def update_estado_indicacion(indicacion_id: str, nuevo_estado: str) -> bool:
    """Suspende o modifica el estado de una indicación."""
    if not check_supabase_connection():
        return False
        
    try:
        _supabase_execute_with_retry(
            "update_indicacion", 
            lambda: supabase.table("indicaciones")
                .update({"estado": nuevo_estado})
                .eq("id", indicacion_id)
                .execute()
        )
        return True
    except Exception as e:
        log_event("db_sql", f"error_update_indicacion:{type(e).__name__}")
        return False


# ==========================================
# GESTIÓN DE ESTUDIOS MÉDICOS
# ==========================================

def get_estudios_by_paciente(paciente_id: str) -> List[Dict[str, Any]]:
    """Obtiene los estudios médicos de un paciente."""
    if not check_supabase_connection():
        return []
        
    try:
        response = _supabase_execute_with_retry(
            "get_estudios", 
            lambda: supabase.table("estudios")
                .select("*")
                .eq("paciente_id", paciente_id)
                .order("fecha_realizacion", desc=True)
                .execute()
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_estudios:{type(e).__name__}")
        return []

def insert_estudio(datos_estudio: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta un nuevo estudio médico."""
    if not check_supabase_connection():
        return None
        
    try:
        response = _supabase_execute_with_retry(
            "insert_estudio", 
            lambda: supabase.table("estudios").insert(datos_estudio).execute()
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_estudio:{type(e).__name__}")
        return None

def delete_estudio(estudio_id: str) -> bool:
    """Elimina un estudio médico."""
    if not check_supabase_connection():
        return False
        
    try:
        _supabase_execute_with_retry(
            "delete_estudio", 
            lambda: supabase.table("estudios").delete().eq("id", estudio_id).execute()
        )
        return True
    except Exception as e:
        log_event("db_sql", f"error_delete_estudio:{type(e).__name__}")
        return False

# ==========================================
# SIGNOS VITALES
# ==========================================

def get_signos_vitales(paciente_id: str, limit: int = 50) -> List[Dict[str, Any]]:
    if not check_supabase_connection():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_vitales", 
            lambda: supabase.table("signos_vitales")
                .select("*, usuarios(nombre)")
                .eq("paciente_id", paciente_id)
                .order("fecha_registro", desc=True)
                .limit(limit)
                .execute()
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_vitales:{type(e).__name__}")
        return []

def insert_signo_vital(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not check_supabase_connection():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_vitales", 
            lambda: supabase.table("signos_vitales").insert(datos).execute()
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_vitales:{type(e).__name__}")
        return None

# ==========================================
# CUIDADOS DE ENFERMERÍA
# ==========================================

def get_cuidados_enfermeria(paciente_id: str, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
    if not check_supabase_connection():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_cuidados", 
            lambda: supabase.table("cuidados_enfermeria")
                .select("*, usuarios(nombre)")
                .eq("paciente_id", paciente_id)
                .gte("fecha_registro", fecha_inicio)
                .lte("fecha_registro", fecha_fin)
                .order("fecha_registro", desc=False)
                .execute()
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_cuidados:{type(e).__name__}")
        return []

def insert_cuidado_enfermeria(datos: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not check_supabase_connection():
        return None
    try:
        response = _supabase_execute_with_retry(
            "insert_cuidado", 
            lambda: supabase.table("cuidados_enfermeria").insert(datos).execute()
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_cuidado:{type(e).__name__}")
        return None

# ==========================================
# AUDITORÍA LEGAL
# ==========================================

def insert_auditoria(datos: Dict[str, Any]) -> None:
    """Inserta un log de auditoría de forma asíncrona/silenciosa."""
    if not check_supabase_connection():
        return
    try:
        _supabase_execute_with_retry(
            "insert_auditoria", 
            lambda: supabase.table("auditoria_legal").insert(datos).execute()
        )
    except Exception as e:
        log_event("db_sql", f"error_insert_auditoria:{type(e).__name__}")

def get_auditoria_by_empresa(empresa_id: str, limit: int = 1000) -> List[Dict[str, Any]]:
    if not check_supabase_connection():
        return []
    try:
        response = _supabase_execute_with_retry(
            "get_auditoria", 
            lambda: supabase.table("auditoria_legal")
                .select("*, usuarios(nombre), pacientes(nombre_completo)")
                .eq("empresa_id", empresa_id)
                .order("fecha_evento", desc=True)
                .limit(limit)
                .execute()
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_auditoria:{type(e).__name__}")
        return []

def get_turnos_by_empresa(empresa_id: str, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
    """Obtiene los turnos de una empresa en un rango de fechas."""
    if not check_supabase_connection():
        return []
        
    try:
        response = _supabase_execute_with_retry(
            "get_turnos", 
            lambda: supabase.table("turnos")
                .select("*, pacientes(nombre_completo, dni), usuarios(nombre)")
                .eq("empresa_id", empresa_id)
                .gte("fecha_hora_programada", fecha_inicio)
                .lte("fecha_hora_programada", fecha_fin)
                .order("fecha_hora_programada", desc=False)
                .execute()
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_turnos:{type(e).__name__}")
        return []

def insert_turno(datos_turno: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Inserta un nuevo turno en la agenda."""
    if not check_supabase_connection():
        return None
        
    try:
        response = _supabase_execute_with_retry(
            "insert_turno", 
            lambda: supabase.table("turnos").insert(datos_turno).execute()
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_turno:{type(e).__name__}")
        return None

def update_estado_turno(turno_id: str, nuevo_estado: str) -> bool:
    """Actualiza el estado de un turno (Realizado, Cancelado, etc)."""
    if not check_supabase_connection():
        return False
        
    try:
        _supabase_execute_with_retry(
            "update_turno", 
            lambda: supabase.table("turnos")
                .update({"estado": nuevo_estado})
                .eq("id", turno_id)
                .execute()
        )
        return True
    except Exception as e:
        log_event("db_sql", f"error_update_turno:{type(e).__name__}")
        return False

def get_administraciones_dia(paciente_id: str, fecha_inicio: str, fecha_fin: str) -> List[Dict[str, Any]]:
    """Obtiene los registros de administración (MAR) para un rango de fechas."""
    if not check_supabase_connection():
        return []
        
    try:
        response = _supabase_execute_with_retry(
            "get_administraciones", 
            lambda: supabase.table("administracion_med")
                .select("*, indicaciones(medicamento, via_administracion, frecuencia), usuarios(nombre)")
                .eq("paciente_id", paciente_id)
                .gte("fecha_registro", fecha_inicio)
                .lte("fecha_registro", fecha_fin)
                .execute()
        )
        return response.data if response and response.data else []
    except Exception as e:
        log_event("db_sql", f"error_get_administraciones:{type(e).__name__}")
        return []


def insert_administracion(datos_admin: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Registra que una dosis fue dada o no dada (atómico)."""
    if not check_supabase_connection():
        return None
        
    try:
        response = _supabase_execute_with_retry(
            "insert_administracion", 
            lambda: supabase.table("administracion_med").insert(datos_admin).execute()
        )
        return response.data[0] if response and response.data else None
    except Exception as e:
        log_event("db_sql", f"error_insert_administracion:{type(e).__name__}")
        return None
