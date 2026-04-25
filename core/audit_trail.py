"""
Sistema de Auditoría Inmutable (Audit Trail) para Medicare Pro.

Características:
- Logs append-only, inmutables y firmados
- Cumplimiento LGPD/GDPR para datos de pacientes
- Detección de tampering (modificación)
- Exportación para compliance
- Retención automática
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set
from enum import Enum, auto

import streamlit as st


class AuditEventType(Enum):
    """Tipos de eventos auditables."""
    # Autenticación
    LOGIN_SUCCESS = auto()
    LOGIN_FAILURE = auto()
    LOGOUT = auto()
    PASSWORD_CHANGE = auto()
    PASSWORD_RESET = auto()
    
    # Autorización
    PERMISSION_DENIED = auto()
    ROLE_CHANGE = auto()
    
    # Datos de pacientes (PHI - Protected Health Information)
    PATIENT_CREATE = auto()
    PATIENT_READ = auto()
    PATIENT_UPDATE = auto()
    PATIENT_DELETE = auto()
    
    # Datos clínicos
    EVOLUCION_CREATE = auto()
    EVOLUCION_READ = auto()
    EVOLUCION_UPDATE = auto()
    EVOLUCION_DELETE = auto()
    
    VITALES_CREATE = auto()
    VITALES_READ = auto()
    
    RECETA_CREATE = auto()
    RECETA_READ = auto()
    
    ESTUDIO_CREATE = auto()
    ESTUDIO_READ = auto()
    
    # Exportación/Respaldo
    DATA_EXPORT = auto()
    DATA_BACKUP = auto()
    DATA_RESTORE = auto()
    
    # Administración
    USER_CREATE = auto()
    USER_UPDATE = auto()
    USER_DELETE = auto()
    
    CONFIG_CHANGE = auto()
    
    # Seguridad
    SECURITY_ALERT = auto()
    SUSPICIOUS_ACTIVITY = auto()
    RATE_LIMIT_HIT = auto()


@dataclass(frozen=True)
class AuditEntry:
    """
    Entrada de auditoría inmutable.
    
    frozen=True hace que sea inmutable después de creación.
    """
    # Identificación
    id: str  # UUID único
    timestamp: str  # ISO 8601 UTC
    
    # Evento
    event_type: str  # AuditEventType.name
    event_category: str  # auth | clinical | admin | security
    
    # Actor
    user_id: str
    user_role: str
    user_empresa: str
    session_id: str
    ip_address: Optional[str]
    user_agent: Optional[str]
    
    # Recurso afectado
    resource_type: str  # patient | evolucion | user | config
    resource_id: str
    
    # Detalles (SIN datos sensibles de paciente)
    action: str  # CREATE | READ | UPDATE | DELETE
    description: str  # Descripción legible
    metadata: Dict[str, Any]  # Datos adicionales NO sensibles
    
    # Firma digital (integridad)
    previous_hash: str  # Hash de entrada anterior (cadena)
    entry_hash: str  # Hash de esta entrada
    signature: str  # HMAC de toda la entrada


class AuditTrail:
    """
    Sistema de auditoría inmutable con firma digital.
    
    Implementa una cadena de hashes donde cada entrada
    referencia el hash de la anterior, detectando cualquier
    modificación.
    """
    
    def __init__(self, secret_key: Optional[str] = None):
        self._secret = secret_key or os.getenv("AUDIT_SECRET_KEY")
        if not self._secret:
            raise ValueError(
                "ERROR CRÍTICO: 'AUDIT_SECRET_KEY' no está configurada en el entorno. "
                "Esta clave es obligatoria para la firma digital de registros de auditoría. "
                "Configúrala como variable de entorno antes de iniciar la aplicación."
            )
        self._entries: List[AuditEntry] = []
        self._last_hash = "0" * 64  # Genesis hash
    
    def _compute_hash(self, entry_data: Dict) -> str:
        """Computa SHA-256 hash de los datos de entrada."""
        # Ordenar keys para determinismo
        canonical = json.dumps(entry_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(canonical.encode()).hexdigest()
    
    def _sign_entry(self, entry_hash: str, previous_hash: str) -> str:
        """Firma la entrada con HMAC-SHA256."""
        message = f"{previous_hash}:{entry_hash}"
        return hmac.new(
            self._secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
    
    def _verify_entry(self, entry: AuditEntry) -> bool:
        """Verifica la integridad de una entrada."""
        # Recalcular hash
        entry_dict = asdict(entry)
        # Remover campos de firma para verificación
        data_for_hash = {k: v for k, v in entry_dict.items() 
                        if k not in ['entry_hash', 'signature', 'previous_hash']}
        
        computed_hash = self._compute_hash(data_for_hash)
        computed_signature = self._sign_entry(computed_hash, entry.previous_hash)
        
        return (
            computed_hash == entry.entry_hash and
            computed_signature == entry.signature
        )
    
    def log(
        self,
        event_type: AuditEventType,
        user_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
        description: str,
        metadata: Optional[Dict] = None,
        session_state: Optional[Dict] = None
    ) -> AuditEntry:
        """
        Registra un evento en el audit trail.
        
        Args:
            event_type: Tipo de evento auditado
            user_id: ID del usuario que realizó la acción
            resource_type: Tipo de recurso afectado
            resource_id: ID del recurso
            action: Tipo de acción (CREATE, READ, UPDATE, DELETE)
            description: Descripción legible del evento
            metadata: Datos adicionales (sin PII/PHI)
            session_state: Estado de sesión de Streamlit
        """
        import uuid
        
        # Obtener contexto de sesión si está disponible
        session_id = ""
        user_role = ""
        user_empresa = ""
        ip_address = None
        user_agent = None
        
        if session_state:
            session_id = session_state.get('session_id', '')
            u_actual = session_state.get('u_actual', {})
            if u_actual:
                user_role = u_actual.get('rol', '')
                user_empresa = u_actual.get('empresa', '')
        
        # Crear datos de entrada (sin campos de firma)
        entry_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc).isoformat()
        
        entry_data = {
            "id": entry_id,
            "timestamp": timestamp,
            "event_type": event_type.name,
            "event_category": self._get_category(event_type),
            "user_id": user_id,
            "user_role": user_role,
            "user_empresa": user_empresa,
            "session_id": session_id,
            "ip_address": ip_address,
            "user_agent": user_agent,
            "resource_type": resource_type,
            "resource_id": resource_id,
            "action": action,
            "description": description,
            "metadata": metadata or {}
        }
        
        # Computar hash y firma
        entry_hash = self._compute_hash(entry_data)
        signature = self._sign_entry(entry_hash, self._last_hash)
        
        # Crear entrada completa
        entry = AuditEntry(
            **entry_data,
            previous_hash=self._last_hash,
            entry_hash=entry_hash,
            signature=signature
        )
        
        # Actualizar cadena
        self._entries.append(entry)
        self._last_hash = entry_hash
        
        # Persistir inmediatamente
        self._persist_entry(entry)
        
        return entry
    
    def _get_category(self, event_type: AuditEventType) -> str:
        """Obtiene categoría del evento."""
        auth_events = {AuditEventType.LOGIN_SUCCESS, AuditEventType.LOGIN_FAILURE, 
                      AuditEventType.LOGOUT, AuditEventType.PASSWORD_CHANGE}
        clinical_events = {AuditEventType.EVOLUCION_CREATE, AuditEventType.EVOLUCION_READ,
                          AuditEventType.VITALES_CREATE, AuditEventType.RECETA_CREATE}
        
        if event_type in auth_events:
            return "auth"
        elif event_type in clinical_events:
            return "clinical"
        elif event_type.name.startswith("USER_") or event_type.name.startswith("CONFIG_"):
            return "admin"
        elif event_type.name.startswith("SECURITY_") or event_type.name.startswith("SUSPICIOUS_"):
            return "security"
        else:
            return "other"
    
    def _persist_entry(self, entry: AuditEntry):
        """Persiste entrada a storage inmutable."""
        # Guardar en session_state de Streamlit
        if 'audit_trail' not in st.session_state:
            st.session_state['audit_trail'] = []
        
        # Convertir a dict para almacenamiento
        entry_dict = asdict(entry)
        st.session_state['audit_trail'].append(entry_dict)
        
        # TODO: Persistir a Supabase/SQL con permisos append-only
    
    def verify_chain(self) -> bool:
        """
        Verifica la integridad de toda la cadena de auditoría.
        
        Retorna True si la cadena es válida, False si se detectó tampering.
        """
        for i, entry in enumerate(self._entries):
            # Verificar entrada individual
            if not self._verify_entry(entry):
                return False
            
            # Verificar enlace de cadena
            if i > 0:
                if entry.previous_hash != self._entries[i-1].entry_hash:
                    return False
        
        return True
    
    def query(
        self,
        event_type: Optional[AuditEventType] = None,
        user_id: Optional[str] = None,
        resource_type: Optional[str] = None,
        start_time: Optional[str] = None,
        end_time: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Consulta entradas de auditoría con filtros."""
        results = list(self._entries)
        
        if event_type:
            results = [e for e in results if e.event_type == event_type.name]
        
        if user_id:
            results = [e for e in results if e.user_id == user_id]
        
        if resource_type:
            results = [e for e in results if e.resource_type == resource_type]
        
        if start_time:
            start_dt = datetime.fromisoformat(start_time)
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            results = [e for e in results if datetime.fromisoformat(e.timestamp).replace(tzinfo=None) >= start_dt.replace(tzinfo=None)]
        
        if end_time:
            end_dt = datetime.fromisoformat(end_time)
            if end_dt.tzinfo is None:
                end_dt = end_dt.replace(tzinfo=timezone.utc)
            results = [e for e in results if datetime.fromisoformat(e.timestamp).replace(tzinfo=None) <= end_dt.replace(tzinfo=None)]
        
        return results[-limit:]
    
    def export_for_compliance(
        self,
        start_date: str,
        end_date: str,
        format: str = "json"
    ) -> str:
        """
        Exporta logs para auditoría de compliance.
        
        Formato LGPD/GDPR compliant - sin datos personales innecesarios.
        """
        entries = self.query(start_time=start_date, end_time=end_date, limit=10000)
        
        if format == "json":
            data = [asdict(e) for e in entries]
            return json.dumps(data, indent=2, ensure_ascii=False)
        elif format == "csv":
            # CSV simple
            lines = ["id,timestamp,event_type,user_id,resource_type,action,description"]
            for e in entries:
                lines.append(f"{e.id},{e.timestamp},{e.event_type},{e.user_id},{e.resource_type},{e.action},{e.description}")
            return "\n".join(lines)
        else:
            raise ValueError(f"Formato no soportado: {format}")


# Singleton global
_audit_trail_instance: Optional[AuditTrail] = None


def get_audit_trail() -> AuditTrail:
    """Obtiene instancia global del audit trail."""
    global _audit_trail_instance
    if _audit_trail_instance is None:
        _audit_trail_instance = AuditTrail()
    return _audit_trail_instance


def audit_log(
    event_type: AuditEventType,
    resource_type: str,
    resource_id: str,
    action: str,
    description: str,
    metadata: Optional[Dict] = None
):
    """
    Helper para registrar eventos de auditoría.
    
    Uso:
        audit_log(
            AuditEventType.EVOLUCION_CREATE,
            resource_type="evolucion",
            resource_id="ev-123",
            action="CREATE",
            description="Nueva evolución creada",
            metadata={"medico": "Dr. García"}
        )
    """
    trail = get_audit_trail()
    
    # Obtener user_id de session_state
    user_id = "anonymous"
    if st.session_state.get('logeado') and st.session_state.get('u_actual'):
        user_id = st.session_state['u_actual'].get('usuario_login', 'unknown')
    
    trail.log(
        event_type=event_type,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        action=action,
        description=description,
        metadata=metadata,
        session_state=st.session_state.to_dict() if hasattr(st.session_state, 'to_dict') else {}
    )


class DataRetentionPolicy:
    """
    Política de retención de datos según LGPD/GDPR.
    """
    
    # Períodos de retención por tipo de dato (en días)
    RETENTION_PERIODS = {
        "clinical_data": 365 * 10,  # 10 años para datos clínicos
        "audit_logs": 365 * 7,       # 7 años para logs de auditoría
        "session_logs": 90,          # 90 días para logs de sesión
        "backup_logs": 365,          # 1 año para logs de backup
    }
    
    @classmethod
    def should_delete(cls, data_type: str, created_at: datetime) -> bool:
        """Determina si datos deben ser eliminados según política."""
        retention_days = cls.RETENTION_PERIODS.get(data_type, 365)
        cutoff_date = datetime.now(timezone.utc) - timedelta(days=retention_days)
        return created_at < cutoff_date
    
    @classmethod
    def get_retention_days(cls, data_type: str) -> int:
        """Retorna días de retención para tipo de dato."""
        return cls.RETENTION_PERIODS.get(data_type, 365)
    
    @classmethod
    def anonymize_patient_data(cls, patient_data: Dict) -> Dict:
        """
        Anonimiza datos de paciente para análisis.
        
        Remueve identificadores directos pero preserva
        datos demográficos agregados.
        """
        sensitive_fields = ['dni', 'nombre', 'apellido', 'email', 'telefono', 'direccion']
        
        anonymized = {}
        for key, value in patient_data.items():
            if key not in sensitive_fields:
                anonymized[key] = value
            else:
                anonymized[key] = "[REDACTED]"
        
        return anonymized


def check_gdpr_compliance(patient_consents: Dict) -> Dict[str, bool]:
    """
    Verifica cumplimiento GDPR/LGPD para un paciente.
    
    Retorna dict con status de consentimientos requeridos.
    """
    required_consents = [
        "data_processing",      # Tratamiento de datos
        "medical_records",      # Historia clínica
        "data_sharing",          # Compartir con terceros
        "marketing",             # Marketing (opcional)
    ]
    
    return {
        consent: patient_consents.get(consent, False)
        for consent in required_consents
    }
