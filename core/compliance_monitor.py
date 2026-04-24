"""
Sistema de Compliance y Auditoría Automatizada.

Cumplimiento normativo:
- HIPAA (Health Insurance Portability and Accountability Act) - USA
- GDPR (General Data Protection Regulation) - Europa
- LGPD (Lei Geral de Proteção de Dados) - Brasil
- Ley 25.506 (Firma Digital) - Argentina
- Resoluciones del Ministerio de Salud - Argentina

Controles automatizados:
- Acceso a PHI (Protected Health Information)
- Retención de datos médicos
- Consentimientos informados vigentes
- Auditoría de modificaciones
- Backups y recuperación
- Acceso de usuarios inactivos
- Violaciones de seguridad

Alertas de compliance:
- Acceso sin autorización detectado
- PHI exportado sin encriptación
- Usuario inactivo con acceso
- Consentimiento vencido
- Backup fallido > 24h
- Audit logs incompletos
"""
import json
from typing import Dict, Any, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from collections import defaultdict
import hashlib

import streamlit as st

from core.app_logging import log_event
from core.audit_trail import AuditEventType, AuditEntry
from core.realtime_notifications import send_critical_alert, NotificationPriority


class ComplianceStandard(Enum):
    """Estándares de compliance soportados."""
    HIPAA = "hipaa"           # USA
    GDPR = "gdpr"             # Europa
    LGPD = "lgpd"             # Brasil
    LEY_25506 = "ley_25506"   # Argentina firma digital
    RES_MINSAL = "res_minsal" # Argentina ministerio salud


class ComplianceStatus(Enum):
    """Estado de cumplimiento."""
    COMPLIANT = "compliant"      # ✅ Cumple
    WARNING = "warning"          # ⚠️ Atención requerida
    VIOLATION = "violation"      # ❌ Violación detectada
    NOT_APPLICABLE = "na"        # ➖ No aplica


class ComplianceControl(Enum):
    """Controles de compliance."""
    # Acceso
    ACCESS_CONTROL = auto()
    ROLE_BASED_ACCESS = auto()
    MINIMUM_NECESSARY = auto()
    
    # Seguridad
    ENCRYPTION_AT_REST = auto()
    ENCRYPTION_IN_TRANSIT = auto()
    AUDIT_LOGGING = auto()
    
    # Integridad
    DATA_INTEGRITY = auto()
    BACKUP_VERIFICATION = auto()
    DISASTER_RECOVERY = auto()
    
    # Consentimiento
    INFORMED_CONSENT = auto()
    DATA_RETENTION = auto()
    RIGHT_TO_BE_FORGOTTEN = auto()
    
    # Operacional
    USER_ACCESS_REVIEW = auto()
    INCIDENT_RESPONSE = auto()
    BUSINESS_ASSOCIATE_AGREEMENTS = auto()


@dataclass
class ComplianceViolation:
    """Violación de compliance detectada."""
    id: str
    standard: str
    control: str
    severity: str  # critical, high, medium, low
    description: str
    detected_at: str
    affected_resource: str
    remediation_required: bool
    remediation_deadline: Optional[str]
    resolved: bool = False
    resolved_at: Optional[str] = None
    resolved_by: Optional[str] = None
    notes: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ComplianceReport:
    """Reporte de compliance."""
    generated_at: str
    period_start: str
    period_end: str
    overall_status: str
    standards: Dict[str, Dict[str, Any]]
    violations: List[ComplianceViolation]
    summary: Dict[str, int]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "generated_at": self.generated_at,
            "period_start": self.period_start,
            "period_end": self.period_end,
            "overall_status": self.overall_status,
            "standards": self.standards,
            "violations": [v.to_dict() for v in self.violations],
            "summary": self.summary
        }


class ComplianceMonitor:
    """
    Monitor de compliance automatizado.
    
    Ejecuta controles periódicos y detecta violaciones de:
    - HIPAA (acceso a PHI, encriptación, audit logs)
    - GDPR/LGPD (consentimientos, derecho al olvido)
    - Ley 25.506 (firmas digitales válidas)
    
    Uso:
        monitor = ComplianceMonitor()
        
        # Ejecutar auditoría completa
        report = monitor.run_compliance_audit()
        
        # Verificar controles específicos
        violations = monitor.check_access_controls()
        
        # Reporte de HIPAA
        hipaa_status = monitor.check_hipaa_compliance()
    """
    
    # Requerimientos por estándar
    HIPAA_REQUIREMENTS = [
        ("Administrative Safeguards", "Asignación de responsabilidades de seguridad"),
        ("Administrative Safeguards", "Procedimientos de acceso a PHI"),
        ("Physical Safeguards", "Control de acceso físico a instalaciones"),
        ("Physical Safeguards", "Protección de dispositivos de trabajo"),
        ("Technical Safeguards", "Control de acceso único de usuario"),
        ("Technical Safeguards", "Encriptación de PHI en reposo y tránsito"),
        ("Technical Safeguards", "Auditoría de accesos a PHI"),
        ("Technical Safeguards", "Integridad de datos (checksums/firmas)"),
        ("Organizational", "Acuerdos con Business Associates"),
    ]
    
    GDPR_REQUIREMENTS = [
        ("Data Processing", "Base legal para procesamiento"),
        ("Data Processing", "Consentimiento explícito del paciente"),
        ("Data Rights", "Derecho de acceso a datos personales"),
        ("Data Rights", "Derecho de rectificación"),
        ("Data Rights", "Derecho al olvido (eliminación)"),
        ("Data Rights", "Derecho a la portabilidad"),
        ("Security", "Protección por diseño y por defecto"),
        ("Security", "Notificación de brechas en 72 horas"),
        ("Documentation", "Registro de actividades de procesamiento"),
    ]
    
    DATA_RETENTION_YEARS = {
        "evoluciones": 10,
        "recetas": 5,
        "consentimientos": 10,
        "imagenes": 7,
        "labs": 10,
        "audit_logs": 7
    }
    
    def __init__(self):
        self._violations: List[ComplianceViolation] = []
        self._last_audit: Optional[ComplianceReport] = None
        self._active_standards: Set[ComplianceStandard] = {
            ComplianceStandard.HIPAA,
            ComplianceStandard.GDPR,
            ComplianceStandard.LEY_25506,
            ComplianceStandard.RES_MINSAL
        }
    
    def run_compliance_audit(
        self,
        period_days: int = 30
    ) -> ComplianceReport:
        """
        Ejecuta auditoría completa de compliance.
        
        Args:
            period_days: Período de auditoría en días
        
        Returns:
            ComplianceReport con hallazgos
        """
        end = datetime.now(timezone.utc)
        start = end - timedelta(days=period_days)
        
        violations = []
        
        # Ejecutar todos los checks
        violations.extend(self._check_access_controls(start, end))
        violations.extend(self._check_encryption_compliance(start, end))
        violations.extend(self._check_audit_log_integrity(start, end))
        violations.extend(self._check_informed_consents(start, end))
        violations.extend(self._check_data_retention(start, end))
        violations.extend(self._check_user_access_review(start, end))
        violations.extend(self._check_backup_compliance(start, end))
        violations.extend(self._check_digital_signatures(start, end))
        
        # Determinar estado general
        critical_count = len([v for v in violations if v.severity == "critical"])
        high_count = len([v for v in violations if v.severity == "high"])
        
        if critical_count > 0:
            overall_status = ComplianceStatus.VIOLATION.value
        elif high_count > 0:
            overall_status = ComplianceStatus.WARNING.value
        else:
            overall_status = ComplianceStatus.COMPLIANT.value
        
        # Generar reporte por estándar
        standards_report = {}
        for standard in self._active_standards:
            std_violations = [v for v in violations if v.standard == standard.value]
            standards_report[standard.value] = {
                "status": ComplianceStatus.COMPLIANT.value if not std_violations else ComplianceStatus.VIOLATION.value,
                "violations_count": len(std_violations),
                "critical_violations": len([v for v in std_violations if v.severity == "critical"]),
                "last_review": datetime.now(timezone.utc).isoformat()
            }
        
        report = ComplianceReport(
            generated_at=datetime.now(timezone.utc).isoformat(),
            period_start=start.isoformat(),
            period_end=end.isoformat(),
            overall_status=overall_status,
            standards=standards_report,
            violations=violations,
            summary={
                "total_violations": len(violations),
                "critical": critical_count,
                "high": high_count,
                "medium": len([v for v in violations if v.severity == "medium"]),
                "low": len([v for v in violations if v.severity == "low"])
            }
        )
        
        self._last_audit = report
        self._violations = violations
        
        # Notificar violaciones críticas
        self._notify_critical_violations(violations)
        
        log_event("compliance", f"audit_completed:{len(violations)}_violations:{overall_status}")
        
        return report
    
    def _check_access_controls(
        self,
        start: datetime,
        end: datetime
    ) -> List[ComplianceViolation]:
        """Verifica controles de acceso."""
        violations = []
        
        # Verificar usuarios inactivos con acceso
        inactive_users_with_access = self._get_inactive_users_with_access()
        for user in inactive_users_with_access:
            violations.append(ComplianceViolation(
                id=f"viol-access-{hash(user['id']) % 10000}",
                standard=ComplianceStandard.HIPAA.value,
                control="Administrative Safeguards",
                severity="high",
                description=f"Usuario inactivo '{user['username']}' tiene acceso al sistema",
                detected_at=datetime.now(timezone.utc).isoformat(),
                affected_resource=f"user:{user['id']}",
                remediation_required=True,
                remediation_deadline=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            ))
        
        # Verificar accesos fuera de horario
        after_hours_access = self._get_after_hours_access(start, end)
        if len(after_hours_access) > 10:  # Umbral arbitrario
            violations.append(ComplianceViolation(
                id=f"viol-hours-{hash(str(start)) % 10000}",
                standard=ComplianceStandard.HIPAA.value,
                control="Administrative Safeguards",
                severity="medium",
                description=f"{len(after_hours_access)} accesos fuera de horario laboral detectados",
                detected_at=datetime.now(timezone.utc).isoformat(),
                affected_resource="system",
                remediation_required=False,
                remediation_deadline=None
            ))
        
        return violations
    
    def _get_inactive_users_with_access(self) -> List[Dict[str, Any]]:
        """Obtiene usuarios inactivos con acceso al sistema."""
        # En producción: consultar base de datos
        # Simulación
        return []
    
    def _get_after_hours_access(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        """Obtiene accesos fuera de horario (22:00 - 06:00)."""
        return []
    
    def _check_encryption_compliance(
        self,
        start: datetime,
        end: datetime
    ) -> List[ComplianceViolation]:
        """Verifica cumplimiento de encriptación."""
        violations = []
        
        # Verificar PHI sin encriptar
        unencrypted_phi = self._detect_unencrypted_phi()
        if unencrypted_phi:
            violations.append(ComplianceViolation(
                id=f"viol-enc-{hash(str(unencrypted_phi)) % 10000}",
                standard=ComplianceStandard.HIPAA.value,
                control="Technical Safeguards",
                severity="critical",
                description=f"{len(unencrypted_phi)} registros de PHI encontrados sin encriptación",
                detected_at=datetime.now(timezone.utc).isoformat(),
                affected_resource="phi_records",
                remediation_required=True,
                remediation_deadline=(datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
            ))
        
        return violations
    
    def _detect_unencrypted_phi(self) -> List[str]:
        """Detecta PHI almacenado sin encriptación."""
        # Verificar campos sensibles en session_state
        unencrypted = []
        
        phi_fields = ["dni", "email", "telefono", "diagnostico"]
        
        for field in phi_fields:
            if field in st.session_state:
                value = st.session_state[field]
                # Verificar si está encriptado (formato JSON con ciphertext)
                if isinstance(value, str) and not value.startswith('{'):
                    unencrypted.append(field)
        
        return unencrypted
    
    def _check_audit_log_integrity(
        self,
        start: datetime,
        end: datetime
    ) -> List[ComplianceViolation]:
        """Verifica integridad de logs de auditoría."""
        violations = []
        
        # Verificar gaps en audit logs
        logs = st.session_state.get("auditoria_legal_db", [])
        
        if len(logs) < 10:  # Muy pocos logs para el período
            violations.append(ComplianceViolation(
                id=f"viol-audit-{hash(str(start)) % 10000}",
                standard=ComplianceStandard.HIPAA.value,
                control="Technical Safeguards",
                severity="high",
                description="Audit logs incompletos o faltantes para el período evaluado",
                detected_at=datetime.now(timezone.utc).isoformat(),
                affected_resource="audit_logs",
                remediation_required=True,
                remediation_deadline=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            ))
        
        return violations
    
    def _check_informed_consents(
        self,
        start: datetime,
        end: datetime
    ) -> List[ComplianceViolation]:
        """Verifica consentimientos informados vigentes."""
        violations = []
        
        # Verificar pacientes sin consentimiento vigente
        pacientes = st.session_state.get("pacientes_db", [])
        
        for paciente in pacientes:
            if not paciente.get("consentimiento_vigente"):
                violations.append(ComplianceViolation(
                    id=f"viol-consent-{hash(paciente.get('id', '')) % 10000}",
                    standard=ComplianceStandard.GDPR.value,
                    control="Informed Consent",
                    severity="high",
                    description=f"Paciente {paciente.get('nombre', 'ID')} sin consentimiento informado vigente",
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    affected_resource=f"patient:{paciente.get('id')}",
                    remediation_required=True,
                    remediation_deadline=(datetime.now(timezone.utc) + timedelta(days=7)).isoformat()
                ))
        
        return violations
    
    def _check_data_retention(
        self,
        start: datetime,
        end: datetime
    ) -> List[ComplianceViolation]:
        """Verifica políticas de retención de datos."""
        violations = []
        
        # Verificar datos que deberían haberse eliminado
        now = datetime.now(timezone.utc)
        
        for data_type, retention_years in self.DATA_RETENTION_YEARS.items():
            cutoff = now - timedelta(days=retention_years * 365)
            
            # En producción: consultar datos más antiguos que cutoff
            # Simulación
            pass
        
        return violations
    
    def _check_user_access_review(
        self,
        start: datetime,
        end: datetime
    ) -> List[ComplianceViolation]:
        """Verifica revisión periódica de accesos."""
        violations = []
        
        # Verificar si se hizo revisión de accesos en el período
        # En producción: buscar eventos de revisión de accesos
        
        return violations
    
    def _check_backup_compliance(
        self,
        start: datetime,
        end: datetime
    ) -> List[ComplianceViolation]:
        """Verifica cumplimiento de backups."""
        violations = []
        
        # Verificar último backup exitoso
        from core.backup_automated import get_backup_manager
        
        manager = get_backup_manager()
        latest = manager.get_latest_successful_backup()
        
        if latest:
            backup_time = datetime.fromisoformat(latest.timestamp)
            hours_since_backup = (datetime.now(timezone.utc) - backup_time).total_seconds() / 3600
            
            if hours_since_backup > 24:
                violations.append(ComplianceViolation(
                    id=f"viol-backup-{hash(latest.id) % 10000}",
                    standard=ComplianceStandard.HIPAA.value,
                    control="Administrative Safeguards",
                    severity="high",
                    description=f"Último backup hace {hours_since_backup:.1f} horas (límite: 24h)",
                    detected_at=datetime.now(timezone.utc).isoformat(),
                    affected_resource="backup_system",
                    remediation_required=True,
                    remediation_deadline=(datetime.now(timezone.utc) + timedelta(hours=4)).isoformat()
                ))
        else:
            violations.append(ComplianceViolation(
                id="viol-backup-none",
                standard=ComplianceStandard.HIPAA.value,
                control="Administrative Safeguards",
                severity="critical",
                description="No se encontraron backups exitosos",
                detected_at=datetime.now(timezone.utc).isoformat(),
                affected_resource="backup_system",
                remediation_required=True,
                remediation_deadline=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
            ))
        
        return violations
    
    def _check_digital_signatures(
        self,
        start: datetime,
        end: datetime
    ) -> List[ComplianceViolation]:
        """Verifica validez de firmas digitales."""
        violations = []
        
        # Verificar documentos firmados con firma inválida
        from core.digital_signature import get_signature_manager
        
        manager = get_signature_manager()
        signed_docs = manager.get_signed_documents()
        
        invalid_docs = [doc for doc in signed_docs if doc.verification_status != "valid"]
        
        for doc in invalid_docs:
            violations.append(ComplianceViolation(
                id=f"viol-sig-{hash(doc.document_id) % 10000}",
                standard=ComplianceStandard.LEY_25506.value,
                control="Firma Digital",
                severity="high",
                description=f"Documento {doc.document_type} con firma inválida o corrupta",
                detected_at=datetime.now(timezone.utc).isoformat(),
                affected_resource=f"document:{doc.document_id}",
                remediation_required=True,
                remediation_deadline=(datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
            ))
        
        return violations
    
    def _notify_critical_violations(self, violations: List[ComplianceViolation]) -> None:
        """Notifica violaciones críticas."""
        critical = [v for v in violations if v.severity == "critical"]
        
        if critical:
            message = f"🚨 {len(critical)} VIOLACIONES CRÍTICAS DE COMPLIANCE detectadas:\n\n"
            for v in critical:
                message += f"• {v.description}\n"
            
            send_critical_alert(
                title="VIOLACIONES DE COMPLIANCE",
                message=message,
                recipient=None  # Broadcast
            )
    
    def get_compliance_status(self) -> Dict[str, Any]:
        """Retorna estado actual de compliance."""
        if not self._last_audit:
            return {"status": "unknown", "message": "No audit run yet"}
        
        return {
            "last_audit": self._last_audit.generated_at,
            "overall_status": self._last_audit.overall_status,
            "violations_count": len(self._violations),
            "critical_violations": len([v for v in self._violations if v.severity == "critical"]),
            "standards": list(self._active_standards)
        }
    
    def resolve_violation(
        self,
        violation_id: str,
        resolved_by: str,
        notes: Optional[str] = None
    ) -> bool:
        """Marca una violación como resuelta."""
        for v in self._violations:
            if v.id == violation_id and not v.resolved:
                v.resolved = True
                v.resolved_at = datetime.now(timezone.utc).isoformat()
                v.resolved_by = resolved_by
                v.notes = notes
                
                log_event("compliance", f"violation_resolved:{violation_id}:by:{resolved_by}")
                return True
        
        return False
    
    def render_compliance_dashboard(self) -> None:
        """Renderiza dashboard de compliance en Streamlit."""
        st.header("⚖️ Compliance y Auditoría")
        
        # Ejecutar auditoría
        if st.button("🔄 Ejecutar Auditoría de Compliance"):
            with st.spinner("Auditando..."):
                report = self.run_compliance_audit()
            
            # Mostrar resultado
            if report.overall_status == ComplianceStatus.COMPLIANT.value:
                st.success("✅ Sistema COMPLIANT")
            elif report.overall_status == ComplianceStatus.WARNING.value:
                st.warning("⚠️ Se detectaron advertencias")
            else:
                st.error("❌ VIOLACIONES detectadas")
            
            # Resumen
            cols = st.columns(4)
            cols[0].metric("Total Violaciones", report.summary["total_violations"])
            cols[1].metric("Críticas", report.summary["critical"], delta_color="inverse")
            cols[2].metric("Altas", report.summary["high"], delta_color="inverse")
            cols[3].metric("Medias", report.summary["medium"])
            
            # Por estándar
            st.subheader("Estado por Estándar")
            for std, data in report.standards.items():
                status_icon = "✅" if data["status"] == "compliant" else "❌"
                st.write(f"{status_icon} **{std.upper()}**: {data['violations_count']} violaciones")
            
            # Detalle de violaciones
            if report.violations:
                st.subheader("Violaciones Detectadas")
                for v in report.violations:
                    severity_color = "🔴" if v.severity == "critical" else "🟠" if v.severity == "high" else "🟡"
                    
                    with st.expander(f"{severity_color} {v.control}: {v.description[:80]}..."):
                        st.write(f"**Estándar:** {v.standard}")
                        st.write(f"**Severidad:** {v.severity}")
                        st.write(f"**Recurso:** {v.affected_resource}")
                        st.write(f**Detectado:** {v.detected_at[:16]}")
                        
                        if v.remediation_required:
                            st.error(f"⏰ Resolución requerida antes de: {v.remediation_deadline[:16]}")
                            
                            if st.button("Marcar como Resuelto", key=f"resolve_{v.id}"):
                                user = st.session_state.get("u_actual", {}).get("username", "system")
                                if self.resolve_violation(v.id, user, "Resuelto desde dashboard"):
                                    st.success("Violación marcada como resuelta")
        
        # Estado actual
        st.subheader("Estado Actual")
        status = self.get_compliance_status()
        st.json(status)


# Instancia global
_compliance_monitor = None

def get_compliance_monitor() -> ComplianceMonitor:
    """Retorna instancia singleton."""
    global _compliance_monitor
    if _compliance_monitor is None:
        _compliance_monitor = ComplianceMonitor()
    return _compliance_monitor


def run_compliance_check() -> ComplianceReport:
    """Ejecuta verificación de compliance."""
    return get_compliance_monitor().run_compliance_audit()


def check_hipaa_compliance() -> Dict[str, Any]:
    """Verifica cumplimiento HIPAA específico."""
    monitor = get_compliance_monitor()
    report = monitor.run_compliance_audit(period_days=7)
    
    hipaa_data = report.standards.get(ComplianceStandard.HIPAA.value, {})
    return hipaa_data
