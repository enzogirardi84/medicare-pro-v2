"""
Sistema de Permisos RBAC (Role-Based Access Control) Avanzado.

Modelo: RBAC con atributos (ABAC) para Healthcare.

Jerarquía:
- Permisos (Permissions) → Acciones específicas
- Roles (Roles) → Colección de permisos
- Usuarios (Users) → Asignación de roles
- Ámbitos (Scopes) → Limitación por contexto (paciente, clínica, etc.)
- Atributos (Attributes) → Condiciones dinámicas (horario, ubicación, etc.)

Permisos clínicos:
- patient:read, patient:create, patient:update, patient:delete
- evolution:read, evolution:create, evolution:sign
- prescription:write, prescription:cancel
- lab:read, lab:order
- admin:user_manage, admin:config
- report:view, report:export

Scopes:
- own_patient: Solo pacientes propios/asignados
- department: Solo pacientes del departamento
- clinic: Todos los pacientes de la clínica
- all: Acceso global (solo admin)

Atributos dinámicos:
- business_hours: Solo en horario laboral
- emergency_override: Permiso en emergencias
- two_factor_verified: Requiere 2FA
- location_verified: Desde ubicación autorizada
"""
import json
from typing import Dict, Any, List, Optional, Set, Callable
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, time
from enum import Enum, auto
from functools import wraps

import streamlit as st

from core.app_logging import log_event


class Permission(Enum):
    """Permisos atómicos del sistema."""
    # Pacientes
    PATIENT_READ = "patient:read"
    PATIENT_CREATE = "patient:create"
    PATIENT_UPDATE = "patient:update"
    PATIENT_DELETE = "patient:delete"
    PATIENT_EXPORT = "patient:export"
    
    # Historia clínica
    EVOLUTION_READ = "evolution:read"
    EVOLUTION_CREATE = "evolution:create"
    EVOLUTION_UPDATE = "evolution:update"
    EVOLUTION_SIGN = "evolution:sign"
    
    # Prescripciones
    PRESCRIPTION_WRITE = "prescription:write"
    PRESCRIPTION_CANCEL = "prescription:cancel"
    PRESCRIPTION_READ = "prescription:read"
    
    # Laboratorio
    LAB_ORDER = "lab:order"
    LAB_READ = "lab:read"
    LAB_CRITICAL_ALERT = "lab:critical_alert"
    
    # Imágenes
    IMAGE_ORDER = "image:order"
    IMAGE_READ = "image:read"
    
    # Turnos
    APPOINTMENT_READ = "appointment:read"
    APPOINTMENT_CREATE = "appointment:create"
    APPOINTMENT_CANCEL = "appointment:cancel"
    APPOINTMENT_RESCHEDULE = "appointment:reschedule"
    
    # Administración
    USER_MANAGE = "admin:user_manage"
    ROLE_MANAGE = "admin:role_manage"
    CONFIG_SYSTEM = "admin:config_system"
    AUDIT_VIEW = "admin:audit_view"
    
    # Reportes
    REPORT_VIEW = "report:view"
    REPORT_EXPORT = "report:export"
    
    # Facturación
    BILLING_CREATE = "billing:create"
    BILLING_MODIFY = "billing:modify"
    BILLING_DELETE = "billing:delete"
    
    # Dispositivos IoT
    IOT_PAIR = "iot:pair"
    IOT_READ = "iot:read"
    
    # Consentimientos
    CONSENT_READ = "consent:read"
    CONSENT_MODIFY = "consent:modify"


class ScopeType(Enum):
    """Tipos de ámbito/scope."""
    OWN_PATIENTS = "own_patients"      # Solo pacientes asignados/propios
    DEPARTMENT = "department"          # Departamento
    CLINIC = "clinic"                  # Clínica completa
    ALL = "all"                        # Global


@dataclass
class AttributeCondition:
    """Condición basada en atributos."""
    attribute_name: str
    operator: str  # eq, ne, gt, lt, in, contains
    value: Any
    description: str


@dataclass
class Role:
    """Rol con permisos y scopes."""
    role_id: str
    name: str
    description: str
    permissions: Set[str]
    scope: str  # ScopeType.value
    allowed_departments: List[str] = field(default_factory=list)
    attribute_conditions: List[AttributeCondition] = field(default_factory=list)
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "role_id": self.role_id,
            "name": self.name,
            "description": self.description,
            "permissions": list(self.permissions),
            "scope": self.scope,
            "allowed_departartments": self.allowed_departments,
            "is_active": self.is_active,
            "created_at": self.created_at
        }


@dataclass
class UserRoleAssignment:
    """Asignación de rol a usuario."""
    user_id: str
    role_id: str
    assigned_by: str
    assigned_at: str
    valid_from: str
    valid_until: Optional[str]  # None = indefinido
    is_active: bool = True
    custom_attributes: Dict[str, Any] = field(default_factory=dict)


class RBACManager:
    """
    Gestor de control de acceso basado en roles.
    
    Uso:
        rbac = RBACManager()
        
        # Verificar permiso
        if rbac.check_permission(user_id, Permission.PATIENT_READ, patient_id="123"):
            # Mostrar datos del paciente
        
        # Decorador en funciones
        @require_permission(Permission.EVOLUTION_CREATE)
        def create_evolution(...):
            ...
    """
    
    # Roles predefinidos del sistema
    DEFAULT_ROLES = {
        "medico": Role(
            role_id="medico",
            name="Médico",
            description="Acceso clínico completo a pacientes",
            permissions={
                Permission.PATIENT_READ.value,
                Permission.PATIENT_CREATE.value,
                Permission.PATIENT_UPDATE.value,
                Permission.EVOLUTION_READ.value,
                Permission.EVOLUTION_CREATE.value,
                Permission.EVOLUTION_UPDATE.value,
                Permission.EVOLUTION_SIGN.value,
                Permission.PRESCRIPTION_WRITE.value,
                Permission.PRESCRIPTION_CANCEL.value,
                Permission.LAB_ORDER.value,
                Permission.LAB_READ.value,
                Permission.LAB_CRITICAL_ALERT.value,
                Permission.IMAGE_ORDER.value,
                Permission.IMAGE_READ.value,
                Permission.APPOINTMENT_READ.value,
                Permission.APPOINTMENT_CREATE.value,
                Permission.APPOINTMENT_CANCEL.value,
                Permission.APPOINTMENT_RESCHEDULE.value,
                Permission.REPORT_VIEW.value,
                Permission.CONSENT_READ.value,
                Permission.IOT_READ.value,
            },
            scope=ScopeType.OWN_PATIENTS.value
        ),
        "enfermero": Role(
            role_id="enfermero",
            name="Enfermero",
            description="Acceso a signos vitales y administración",
            permissions={
                Permission.PATIENT_READ.value,
                Permission.EVOLUTION_READ.value,
                Permission.LAB_READ.value,
                Permission.APPOINTMENT_READ.value,
                Permission.APPOINTMENT_CREATE.value,
                Permission.IOT_PAIR.value,
                Permission.IOT_READ.value,
                Permission.CONSENT_READ.value,
            },
            scope=ScopeType.DEPARTMENT.value
        ),
        "admin": Role(
            role_id="admin",
            name="Administrador",
            description="Acceso administrativo completo",
            permissions={
                Permission.USER_MANAGE.value,
                Permission.ROLE_MANAGE.value,
                Permission.CONFIG_SYSTEM.value,
                Permission.AUDIT_VIEW.value,
                Permission.REPORT_VIEW.value,
                Permission.REPORT_EXPORT.value,
            },
            scope=ScopeType.ALL.value
        ),
        "recepcion": Role(
            role_id="recepcion",
            name="Recepción",
            description="Gestión de turnos y datos básicos",
            permissions={
                Permission.PATIENT_READ.value,
                Permission.PATIENT_CREATE.value,
                Permission.PATIENT_UPDATE.value,
                Permission.APPOINTMENT_READ.value,
                Permission.APPOINTMENT_CREATE.value,
                Permission.APPOINTMENT_CANCEL.value,
                Permission.APPOINTMENT_RESCHEDULE.value,
                Permission.BILLING_CREATE.value,
                Permission.BILLING_MODIFY.value,
            },
            scope=ScopeType.CLINIC.value
        ),
        "laboratorio": Role(
            role_id="laboratorio",
            name="Técnico de Laboratorio",
            description="Acceso a órdenes y resultados de laboratorio",
            permissions={
                Permission.LAB_READ.value,
                Permission.LAB_ORDER.value,
                Permission.PATIENT_READ.value,
                Permission.LAB_CRITICAL_ALERT.value,
            },
            scope=ScopeType.DEPARTMENT.value
        ),
        "paciente": Role(
            role_id="paciente",
            name="Paciente",
            description="Acceso a propia información",
            permissions={
                Permission.PATIENT_READ.value,
                Permission.EVOLUTION_READ.value,
                Permission.LAB_READ.value,
                Permission.PRESCRIPTION_READ.value,
                Permission.APPOINTMENT_READ.value,
                Permission.APPOINTMENT_CREATE.value,
                Permission.CONSENT_READ.value,
            },
            scope=ScopeType.OWN_PATIENTS.value  # Solo su propia info
        ),
    }
    
    def __init__(self):
        self._roles: Dict[str, Role] = {}
        self._user_assignments: Dict[str, List[UserRoleAssignment]] = {}
        self._user_patient_assignments: Dict[str, Set[str]] = {}  # user_id -> {patient_ids}
        self._init_default_roles()
        self._load_assignments()
    
    def _init_default_roles(self) -> None:
        """Inicializa roles por defecto."""
        for role in self.DEFAULT_ROLES.values():
            self._roles[role.role_id] = role
    
    def _load_assignments(self) -> None:
        """Carga asignaciones desde storage."""
        if "rbac_assignments" in st.session_state:
            self._user_assignments = st.session_state["rbac_assignments"]
        if "rbac_user_patients" in st.session_state:
            self._user_patient_assignments = st.session_state["rbac_user_patients"]
    
    def _save_assignments(self) -> None:
        """Guarda asignaciones en storage."""
        st.session_state["rbac_assignments"] = self._user_assignments
        st.session_state["rbac_user_patients"] = self._user_patient_assignments
    
    def assign_role_to_user(
        self,
        user_id: str,
        role_id: str,
        assigned_by: str,
        valid_until: Optional[str] = None,
        custom_attributes: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Asigna un rol a un usuario.
        
        Args:
            user_id: ID del usuario
            role_id: ID del rol
            assigned_by: Quién realiza la asignación
            valid_until: Fecha de expiración (opcional)
            custom_attributes: Atributos personalizados
        
        Returns:
            True si exitoso
        """
        if role_id not in self._roles:
            raise ValueError(f"Rol no existe: {role_id}")
        
        assignment = UserRoleAssignment(
            user_id=user_id,
            role_id=role_id,
            assigned_by=assigned_by,
            assigned_at=datetime.now(timezone.utc).isoformat(),
            valid_from=datetime.now(timezone.utc).isoformat(),
            valid_until=valid_until,
            custom_attributes=custom_attributes or {}
        )
        
        if user_id not in self._user_assignments:
            self._user_assignments[user_id] = []
        
        # Desactivar asignaciones previas del mismo rol
        for existing in self._user_assignments[user_id]:
            if existing.role_id == role_id:
                existing.is_active = False
        
        self._user_assignments[user_id].append(assignment)
        self._save_assignments()
        
        log_event("rbac", f"role_assigned:{role_id}:to:{user_id}:by:{assigned_by}")
        
        return True
    
    def revoke_role(self, user_id: str, role_id: str, revoked_by: str) -> bool:
        """Revoca un rol de un usuario."""
        if user_id in self._user_assignments:
            for assignment in self._user_assignments[user_id]:
                if assignment.role_id == role_id and assignment.is_active:
                    assignment.is_active = False
                    self._save_assignments()
                    log_event("rbac", f"role_revoked:{role_id}:from:{user_id}:by:{revoked_by}")
                    return True
        
        return False
    
    def assign_patient_to_user(
        self,
        user_id: str,
        patient_id: str,
        assigned_by: str
    ) -> bool:
        """
        Asigna un paciente específico a un usuario (para scope own_patients).
        
        Args:
            user_id: Usuario al que se asigna el paciente
            patient_id: ID del paciente
            assigned_by: Quién realiza la asignación
        """
        if user_id not in self._user_patient_assignments:
            self._user_patient_assignments[user_id] = set()
        
        self._user_patient_assignments[user_id].add(patient_id)
        self._save_assignments()
        
        log_event("rbac", f"patient_assigned:{patient_id}:to:{user_id}:by:{assigned_by}")
        
        return True
    
    def check_permission(
        self,
        user_id: str,
        permission: Permission,
        context: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Verifica si un usuario tiene un permiso específico.
        
        Args:
            user_id: ID del usuario
            permission: Permiso a verificar
            context: Contexto adicional (patient_id, department, etc.)
        
        Returns:
            True si tiene permiso
        """
        context = context or {}
        
        # Obtener roles activos del usuario
        assignments = self._user_assignments.get(user_id, [])
        active_roles = [
            a for a in assignments
            if a.is_active and (not a.valid_until or datetime.fromisoformat(a.valid_until) > datetime.now(timezone.utc))
        ]
        
        for assignment in active_roles:
            role = self._roles.get(assignment.role_id)
            
            if not role or not role.is_active:
                continue
            
            # Verificar si el rol tiene el permiso
            if permission.value not in role.permissions:
                continue
            
            # Verificar scope
            if not self._check_scope(role, assignment, context):
                continue
            
            # Verificar atributos dinámicos
            if not self._check_attributes(role, assignment, context):
                continue
            
            # Todas las verificaciones pasaron
            return True
        
        return False
    
    def _check_scope(
        self,
        role: Role,
        assignment: UserRoleAssignment,
        context: Dict[str, Any]
    ) -> bool:
        """Verifica si el contexto cumple con el scope del rol."""
        patient_id = context.get("patient_id")
        department = context.get("department")
        clinic_id = context.get("clinic_id")
        
        if role.scope == ScopeType.ALL.value:
            return True
        
        elif role.scope == ScopeType.CLINIC.value:
            # Verificar que el paciente esté en la clínica
            return True  # Simplificado
        
        elif role.scope == ScopeType.DEPARTMENT.value:
            # Verificar que el paciente esté en el departamento del usuario
            if department and department in role.allowed_departments:
                return True
            return False
        
        elif role.scope == ScopeType.OWN_PATIENTS.value:
            # Verificar que el paciente esté asignado al usuario
            if patient_id:
                user_patients = self._user_patient_assignments.get(assignment.user_id, set())
                if patient_id in user_patients:
                    return True
            return False
        
        return False
    
    def _check_attributes(
        self,
        role: Role,
        assignment: UserRoleAssignment,
        context: Dict[str, Any]
    ) -> bool:
        """Verifica condiciones basadas en atributos."""
        # Verificar business_hours si está configurado
        if "business_hours_only" in role.attribute_conditions:
            now = datetime.now(timezone.utc)
            if not (time(8, 0) <= now.time() <= time(18, 0)):
                return False
        
        # Verificar atributos personalizados de la asignación
        if "requires_2fa" in assignment.custom_attributes:
            if not context.get("two_factor_verified", False):
                return False
        
        if "location_restricted" in assignment.custom_attributes:
            allowed_ips = assignment.custom_attributes.get("allowed_ips", [])
            current_ip = context.get("client_ip", "")
            if current_ip not in allowed_ips:
                return False
        
        return True
    
    def get_user_permissions(self, user_id: str) -> Set[str]:
        """Obtiene todos los permisos de un usuario (consolidado)."""
        permissions = set()
        
        assignments = self._user_assignments.get(user_id, [])
        active_assignments = [
            a for a in assignments
            if a.is_active and (not a.valid_until or datetime.fromisoformat(a.valid_until) > datetime.now(timezone.utc))
        ]
        
        for assignment in active_assignments:
            role = self._roles.get(assignment.role_id)
            if role and role.is_active:
                permissions.update(role.permissions)
        
        return permissions
    
    def get_user_roles(self, user_id: str) -> List[Role]:
        """Obtiene roles activos de un usuario."""
        assignments = self._user_assignments.get(user_id, [])
        active_roles = []
        
        for assignment in assignments:
            if assignment.is_active:
                role = self._roles.get(assignment.role_id)
                if role and role.is_active:
                    active_roles.append(role)
        
        return active_roles
    
    def create_custom_role(
        self,
        name: str,
        description: str,
        permissions: Set[str],
        scope: str,
        created_by: str
    ) -> Role:
        """Crea un rol personalizado."""
        role_id = f"custom-{name.lower().replace(' ', '-')}"
        
        role = Role(
            role_id=role_id,
            name=name,
            description=description,
            permissions=permissions,
            scope=scope,
            created_at=datetime.now(timezone.utc).isoformat()
        )
        
        self._roles[role_id] = role
        
        log_event("rbac", f"role_created:{role_id}:by:{created_by}")
        
        return role
    
    def get_all_roles(self) -> List[Role]:
        """Obtiene todos los roles."""
        return list(self._roles.values())
    
    def get_role_details(self, role_id: str) -> Optional[Role]:
        """Obtiene detalles de un rol."""
        return self._roles.get(role_id)
    
    def render_rbac_manager(self) -> None:
        """Renderiza UI de gestión RBAC en Streamlit."""
        st.header("🔐 Control de Acceso (RBAC)")
        
        tab1, tab2, tab3 = st.tabs(["Roles", "Asignaciones", "Permisos de Usuario"])
        
        with tab1:
            st.subheader("Roles del Sistema")
            
            roles = self.get_all_roles()
            
            for role in roles:
                with st.expander(f"{role.name} ({role.role_id})"):
                    st.write(f"**Descripción:** {role.description}")
                    st.write(f"**Scope:** {role.scope}")
                    st.write(f"**Permisos ({len(role.permissions)}):**")
                    
                    # Mostrar permisos agrupados
                    perms_by_category = {}
                    for perm in sorted(role.permissions):
                        category = perm.split(":")[0]
                        if category not in perms_by_category:
                            perms_by_category[category] = []
                        perms_by_category[category].append(perm.split(":")[1])
                    
                    for cat, actions in perms_by_category.items():
                        st.caption(f"• {cat.title()}: {', '.join(actions)}")
        
        with tab2:
            st.subheader("Asignar Rol a Usuario")
            
            user_id = st.text_input("ID de Usuario")
            role_options = {r.role_id: r.name for r in roles}
            selected_role = st.selectbox("Rol", options=list(role_options.keys()), format_func=lambda x: role_options[x])
            
            if st.button("Asignar Rol"):
                current_user = st.session_state.get("u_actual", {}).get("username", "system")
                if self.assign_role_to_user(user_id, selected_role, current_user):
                    st.success(f"Rol {role_options[selected_role]} asignado a {user_id}")
                else:
                    st.error("Error al asignar rol")
            
            # Asignar paciente a médico
            st.subheader("Asignar Paciente a Médico")
            doctor_id = st.text_input("ID del Médico")
            patient_id = st.text_input("ID del Paciente a asignar")
            
            if st.button("Asignar Paciente"):
                current_user = st.session_state.get("u_actual", {}).get("username", "system")
                if self.assign_patient_to_user(doctor_id, patient_id, current_user):
                    st.success(f"Paciente {patient_id} asignado a médico {doctor_id}")
        
        with tab3:
            st.subheader("Verificar Permisos de Usuario")
            
            check_user = st.text_input("Usuario a verificar")
            
            if st.button("Verificar"):
                permissions = self.get_user_permissions(check_user)
                roles = self.get_user_roles(check_user)
                
                st.write(f"**Roles:** {', '.join([r.name for r in roles])}")
                st.write(f"**Total permisos:** {len(permissions)}")
                
                with st.expander("Ver permisos detallados"):
                    for perm in sorted(permissions):
                        st.write(f"• {perm}")


# Instancia global
_rbac_manager = None

def get_rbac_manager() -> RBACManager:
    """Retorna instancia singleton."""
    global _rbac_manager
    if _rbac_manager is None:
        _rbac_manager = RBACManager()
    return _rbac_manager


def require_permission(permission: Permission):
    """Decorador para requerir permiso en funciones."""
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            user = st.session_state.get("u_actual", {})
            user_id = user.get("username")
            
            if not user_id:
                raise PermissionError("Usuario no autenticado")
            
            rbac = get_rbac_manager()
            
            if not rbac.check_permission(user_id, permission):
                raise PermissionError(f"Permiso requerido: {permission.value}")
            
            return func(*args, **kwargs)
        
        return wrapper
    return decorator


def check_user_permission(
    user_id: str,
    permission: Permission,
    patient_id: Optional[str] = None
) -> bool:
    """Helper para verificar permiso de usuario."""
    rbac = get_rbac_manager()
    context = {}
    if patient_id:
        context["patient_id"] = patient_id
    
    return rbac.check_permission(user_id, permission, context)


def assign_role(
    user_id: str,
    role_id: str,
    assigned_by: str
) -> bool:
    """Helper para asignar rol."""
    return get_rbac_manager().assign_role_to_user(user_id, role_id, assigned_by)
