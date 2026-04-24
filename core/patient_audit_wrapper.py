"""
Wrapper de Auditoría para Operaciones de Pacientes.

Todas las operaciones CRUD en pacientes deben pasar por aquí.
- Registra acciones en audit trail
- Implementa soft delete (no borrado real)
- Valida permisos de usuario
- Sanitiza inputs automáticamente
"""
from typing import Any, Dict, List, Optional, Callable, TypeVar
from datetime import datetime, timezone
from functools import wraps
import streamlit as st
import json

from core.app_logging import log_event
from core.security_middleware import (
    InputSanitizer,
    PatientDataValidator,
    SecurityError,
    sanitize_search_term
)
from core.cache_optimized import cached_query, SessionStateManager
from core.pagination import PageInfo
from core.db_paginated import get_paginated_patients


F = TypeVar("F", bound=Callable[..., Any])


def requires_auth(roles: Optional[List[str]] = None) -> Callable[[F], F]:
    """
    Decorador que verifica autenticación y roles.
    Roles permitidos: 'medico', 'enfermero', 'admin', 'coordinador'
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Verificar sesión activa
            if not st.session_state.get("logeado"):
                raise PermissionError("Usuario no autenticado. Inicie sesión.")
            
            user = st.session_state.get("u_actual", {})
            user_role = user.get("rol", "").lower()
            
            # Verificar roles si se especificaron
            if roles and user_role not in [r.lower() for r in roles]:
                raise PermissionError(
                    f"Rol '{user_role}' no tiene permiso para esta operación. "
                    f"Requerido: {', '.join(roles)}"
                )
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def audit_action(action: str, resource_type: str = "patient") -> Callable[[F], F]:
    """
    Decorador que registra la acción en el audit trail.
    
    Args:
        action: Tipo de acción (CREATE, READ, UPDATE, DELETE)
        resource_type: Tipo de recurso afectado
    """
    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = st.session_state.get("u_actual", {})
            user_id = user.get("username", "unknown")
            user_role = user.get("rol", "unknown")
            empresa = user.get("empresa", "unknown")
            
            start_time = datetime.now(timezone.utc)
            error = None
            result = None
            
            try:
                result = func(*args, **kwargs)
                status = "SUCCESS"
            except Exception as e:
                error = str(e)
                status = "ERROR"
                raise
            finally:
                # Registrar en audit trail
                end_time = datetime.now(timezone.utc)
                duration_ms = (end_time - start_time).total_seconds() * 1000
                
                audit_entry = {
                    "timestamp": start_time.isoformat(),
                    "action": action,
                    "resource_type": resource_type,
                    "user_id": user_id,
                    "user_role": user_role,
                    "empresa": empresa,
                    "function": func.__name__,
                    "status": status,
                    "duration_ms": round(duration_ms, 2),
                    "error": error,
                }
                
                # Log seguro (sin datos sensibles)
                log_event("audit", json.dumps(audit_entry, default=str))
                
                # Guardar en logs_db para persistencia
                _append_to_audit_log(audit_entry)
            
            return result
        
        return wrapper
    return decorator


def _append_to_audit_log(entry: Dict[str, Any]) -> None:
    """Agrega entrada al log de auditoría en session_state."""
    if "auditoria_legal_db" not in st.session_state:
        st.session_state["auditoria_legal_db"] = []
    
    # Limitar tamaño del log en memoria (máximo 1000 entradas)
    logs = st.session_state["auditoria_legal_db"]
    logs.append(entry)
    if len(logs) > 1000:
        st.session_state["auditoria_legal_db"] = logs[-1000:]


class PatientService:
    """
    Servicio de pacientes con auditoría, validación y seguridad integradas.
    Todas las operaciones de pacientes DEBEN usar esta clase.
    """
    
    @staticmethod
    @requires_auth(roles=["medico", "enfermero", "admin", "coordinador"])
    @audit_action(action="READ", resource_type="patient")
    def list_patients(
        page: int = 1,
        page_size: int = 50,
        search: Optional[str] = None,
        tenant_id: Optional[str] = None
    ) -> PageInfo:
        """
        Lista pacientes paginada con caché.
        Requiere rol: médico, enfermero, admin o coordinador.
        """
        # Sanitizar término de búsqueda
        if search:
            search = sanitize_search_term(search)
        
        # Determinar tenant del usuario actual
        if tenant_id is None:
            user = st.session_state.get("u_actual", {})
            tenant_id = user.get("empresa")
        
        return get_paginated_patients(
            page=page,
            page_size=page_size,
            search=search,
            tenant_id=tenant_id
        )
    
    @staticmethod
    @requires_auth(roles=["medico", "enfermero", "admin"])
    @audit_action(action="READ", resource_type="patient")
    def get_patient(patient_id: str, tenant_id: Optional[str] = None) -> Optional[Dict]:
        """
        Obtiene un paciente por ID.
        Requiere rol: médico, enfermero o admin.
        """
        if not patient_id:
            raise ValueError("ID de paciente requerido")
        
        # Validar formato de ID
        patient_id = str(patient_id).strip()
        if len(patient_id) > 100:
            raise SecurityError("ID de paciente demasiado largo")
        
        # Determinar tenant
        if tenant_id is None:
            user = st.session_state.get("u_actual", {})
            tenant_id = user.get("empresa")
        
        try:
            from core._database_supabase import supabase
            if supabase:
                response = supabase.table("pacientes").select("*").eq("id", patient_id)
                if tenant_id:
                    response = response.eq("tenant_id", tenant_id)
                response = response.limit(1).execute()
                
                if response.data and len(response.data) > 0:
                    return response.data[0]
            
            # Fallback a datos locales
            pacientes = st.session_state.get("pacientes_db", [])
            for p in pacientes:
                if p.get("id") == patient_id:
                    return p
            
            return None
            
        except Exception as e:
            log_event("patient_service", f"get_error:{type(e).__name__}")
            raise
    
    @staticmethod
    @requires_auth(roles=["medico", "admin", "coordinador"])
    @audit_action(action="CREATE", resource_type="patient")
    def create_patient(patient_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Crea un nuevo paciente.
        Requiere rol: médico, admin o coordinador.
        """
        # Validar y sanitizar datos
        validator = PatientDataValidator()
        
        # Validar DNI
        if "dni" in patient_data:
            try:
                patient_data["dni"] = validator.validate_dni(patient_data["dni"])
            except ValueError as e:
                raise ValueError(f"DNI inválido: {e}")
        
        # Validar email
        if "email" in patient_data:
            try:
                patient_data["email"] = validator.validate_email(patient_data.get("email"))
            except ValueError as e:
                raise ValueError(f"Email inválido: {e}")
        
        # Validar teléfono
        if "telefono" in patient_data:
            try:
                patient_data["telefono"] = validator.validate_telefono(
                    patient_data.get("telefono")
                )
            except ValueError as e:
                raise ValueError(f"Teléfono inválido: {e}")
        
        # Sanitizar campos de texto
        patient_data = InputSanitizer.sanitize_dict(
            patient_data,
            allow_html_fields=["alergias", "antecedentes", "notas"]
        )
        
        # Agregar metadatos
        patient_data["creado_en"] = datetime.now(timezone.utc).isoformat()
        patient_data["creado_por"] = st.session_state.get("u_actual", {}).get("username")
        patient_data["estado"] = "activo"
        
        # Agregar a session_state
        if "pacientes_db" not in st.session_state:
            st.session_state["pacientes_db"] = []
        
        st.session_state["pacientes_db"].append(patient_data)
        
        return patient_data
    
    @staticmethod
    @requires_auth(roles=["medico", "enfermero", "admin"])
    @audit_action(action="UPDATE", resource_type="patient")
    def update_patient(
        patient_id: str,
        updates: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Actualiza datos de un paciente.
        Requiere rol: médico, enfermero o admin.
        """
        if not patient_id:
            raise ValueError("ID de paciente requerido")
        
        # Obtener paciente actual
        current = PatientService.get_patient(patient_id)
        if not current:
            raise ValueError(f"Paciente no encontrado: {patient_id}")
        
        # Validar campos actualizables
        validator = PatientDataValidator()
        
        if "dni" in updates:
            try:
                updates["dni"] = validator.validate_dni(updates["dni"])
            except ValueError as e:
                raise ValueError(f"DNI inválido: {e}")
        
        if "email" in updates:
            try:
                updates["email"] = validator.validate_email(updates.get("email"))
            except ValueError as e:
                raise ValueError(f"Email inválido: {e}")
        
        # Sanitizar
        updates = InputSanitizer.sanitize_dict(
            updates,
            allow_html_fields=["alergias", "antecedentes", "notas"]
        )
        
        # Agregar metadatos de actualización
        updates["actualizado_en"] = datetime.now(timezone.utc).isoformat()
        updates["actualizado_por"] = st.session_state.get("u_actual", {}).get("username")
        
        # Actualizar en session_state
        pacientes = st.session_state.get("pacientes_db", [])
        for i, p in enumerate(pacientes):
            if p.get("id") == patient_id:
                pacientes[i].update(updates)
                return pacientes[i]
        
        return None
    
    @staticmethod
    @requires_auth(roles=["admin", "coordinador"])
    @audit_action(action="DELETE", resource_type="patient")
    def delete_patient(patient_id: str, permanent: bool = False) -> bool:
        """
        Elimina un paciente (soft delete por defecto).
        Requiere rol: admin o coordinador.
        
        Args:
            patient_id: ID del paciente
            permanent: Si True, borra permanentemente (solo admin)
        """
        if not patient_id:
            raise ValueError("ID de paciente requerido")
        
        user = st.session_state.get("u_actual", {})
        user_role = user.get("rol", "").lower()
        
        # Solo admin puede borrado permanente
        if permanent and user_role != "admin":
            raise PermissionError("Solo administradores pueden eliminar permanentemente")
        
        pacientes = st.session_state.get("pacientes_db", [])
        
        for i, p in enumerate(pacientes):
            if p.get("id") == patient_id:
                if permanent:
                    # Borrado permanente
                    pacientes.pop(i)
                else:
                    # Soft delete - marcar como inactivo
                    pacientes[i]["estado"] = "inactivo"
                    pacientes[i]["eliminado_en"] = datetime.now(timezone.utc).isoformat()
                    pacientes[i]["eliminado_por"] = user.get("username")
                
                return True
        
        return False
    
    @staticmethod
    def get_patient_count(tenant_id: Optional[str] = None) -> int:
        """Retorna cantidad de pacientes activos."""
        if tenant_id is None:
            user = st.session_state.get("u_actual", {})
            tenant_id = user.get("empresa")
        
        pacientes = st.session_state.get("pacientes_db", [])
        return len([p for p in pacientes if p.get("estado") != "inactivo"])


# Funciones de conveniencia para uso directo
def buscar_pacientes(
    termino: str,
    page: int = 1,
    page_size: int = 50
) -> PageInfo:
    """Busca pacientes por nombre o DNI."""
    return PatientService.list_patients(
        page=page,
        page_size=page_size,
        search=termino
    )


def obtener_paciente(patient_id: str) -> Optional[Dict]:
    """Obtiene un paciente por ID."""
    return PatientService.get_patient(patient_id)


def crear_paciente(datos: Dict[str, Any]) -> Dict[str, Any]:
    """Crea un nuevo paciente."""
    return PatientService.create_patient(datos)


def actualizar_paciente(patient_id: str, datos: Dict[str, Any]) -> Optional[Dict]:
    """Actualiza datos de un paciente."""
    return PatientService.update_patient(patient_id, datos)


def eliminar_paciente(patient_id: str, permanente: bool = False) -> bool:
    """Elimina un paciente (soft delete por defecto)."""
    return PatientService.delete_patient(patient_id, permanente)
