"""
Sistema de Gestión de Calidad e Incidentes para Medicare Pro.

Características:
- Registro de incidentes/eventos adversos
- Clasificación por severidad y tipo
- Análisis de causa raíz (RCA)
- Planes de acción correctiva
- Dashboard de indicadores de calidad
- Reportes para acreditación
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, date
from typing import Dict, List, Optional, Any
from enum import Enum, auto
import uuid

import streamlit as st

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType


class IncidentSeverity(Enum):
    """Niveles de severidad de incidente."""
    CRITICAL = "critical"      # Daño grave o muerte
    SERIOUS = "serious"        # Daño significativo
    MODERATE = "moderate"      # Daño leve, casi daño
    MINOR = "minor"            # Sin daño, potencial
    NEAR_MISS = "near_miss"    # Casi ocurre (close call)


class IncidentType(Enum):
    """Tipos de incidentes/eventos adversos."""
    MEDICATION_ERROR = "medication_error"
    FALL = "fall"
    INFECTION = "infection"
    PROCEDURE_ERROR = "procedure_error"
    DIAGNOSIS_ERROR = "diagnosis_error"
    COMMUNICATION_ERROR = "communication_error"
    EQUIPMENT_FAILURE = "equipment_failure"
    DOCUMENTATION_ERROR = "documentation_error"
    PRIVACY_BREACH = "privacy_breach"
    OTHER = "other"


class IncidentStatus(Enum):
    """Estados del incidente."""
    REPORTED = "reported"           # Reportado, sin clasificar
    UNDER_REVIEW = "under_review"   # En revisión
    INVESTIGATING = "investigating" # Investigación activa
    CORRECTIVE_ACTION = "corrective_action"  # Plan de acción
    RESOLVED = "resolved"           # Resuelto
    CLOSED = "closed"               # Cerrado definitivamente


@dataclass
class CorrectiveAction:
    """Acción correctiva para un incidente."""
    id: str
    description: str
    responsible: str
    due_date: Optional[date] = None
    completed_at: Optional[datetime] = None
    completed_by: Optional[str] = None
    status: str = "pending"  # pending, in_progress, completed
    evidence: Optional[str] = None  # Descripción de evidencia de cumplimiento


@dataclass
class QualityIncident:
    """Incidente de calidad/evento adverso."""
    id: str
    reported_at: datetime
    reported_by: str
    reported_by_id: str
    
    # Información básica
    incident_date: date
    incident_time: Optional[str] = None
    location: Optional[str] = None  # Sala, consultorio, etc.
    
    # Clasificación
    incident_type: IncidentType = IncidentType.OTHER
    severity: IncidentSeverity = IncidentSeverity.MINOR
    status: IncidentStatus = IncidentStatus.REPORTED
    
    # Personas involucradas
    patient_id: Optional[str] = None
    patient_name: Optional[str] = None
    involved_staff: List[str] = field(default_factory=list)
    
    # Descripción
    description: str = ""
    immediate_actions: str = ""  # Acciones tomadas inmediatamente
    
    # Análisis
    contributing_factors: List[str] = field(default_factory=list)
    root_cause: Optional[str] = None
    root_cause_category: Optional[str] = None  # Humano, sistémico, proceso, etc.
    
    # Plan de acción
    corrective_actions: List[CorrectiveAction] = field(default_factory=list)
    preventive_actions: str = ""
    
    # Seguimiento
    assigned_to: Optional[str] = None
    review_date: Optional[date] = None
    
    # Resultado
    patient_outcome: Optional[str] = None  # Sin daño, daño leve, moderado, grave, muerte
    financial_impact: Optional[float] = None
    
    # Cierre
    closed_at: Optional[datetime] = None
    closed_by: Optional[str] = None
    lessons_learned: Optional[str] = None
    
    def to_dict(self) -> dict:
        """Convierte a diccionario."""
        return {
            **asdict(self),
            "incident_type": self.incident_type.value,
            "severity": self.severity.value,
            "status": self.status.value
        }


class QualityManagementSystem:
    """
    Sistema de gestión de calidad e incidentes.
    """
    
    # Categorías de causa raíz (para análisis sistemático)
    ROOT_CAUSE_CATEGORIES = [
        "Error humano (fatiga, distracción, falta de conocimiento)",
        "Fallo de comunicación",
        "Proceso inadecuado o ausente",
        "Capacitación insuficiente",
        "Falta de recursos/personal",
        "Equipo tecnológico deficiente",
        "Ambiente físico inadecuado",
        "Cultura organizacional",
        "Políticas/procedimientos claros pero no seguidos",
        "Políticas/procedimientos confusos o inexistentes",
        "Factores externos"
    ]
    
    def __init__(self):
        self._incidents: Dict[str, QualityIncident] = {}
        self._load_incidents()
    
    def _load_incidents(self):
        """Carga incidentes desde session_state."""
        if "quality_incidents" in st.session_state:
            try:
                data = st.session_state["quality_incidents"]
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict):
                            self._incidents[k] = self._dict_to_incident(v)
            except Exception as e:
                log_event("quality", f"Error loading incidents: {e}")
    
    def _save_incidents(self):
        """Guarda incidentes a session_state."""
        data = {k: v.to_dict() for k, v in self._incidents.items()}
        st.session_state["quality_incidents"] = data
    
    def _dict_to_incident(self, data: dict) -> QualityIncident:
        """Convierte dict a QualityIncident."""
        return QualityIncident(
            id=data["id"],
            reported_at=datetime.fromisoformat(data["reported_at"]),
            reported_by=data["reported_by"],
            reported_by_id=data["reported_by_id"],
            incident_date=date.fromisoformat(data["incident_date"]),
            incident_time=data.get("incident_time"),
            location=data.get("location"),
            incident_type=IncidentType(data.get("incident_type", "other")),
            severity=IncidentSeverity(data.get("severity", "minor")),
            status=IncidentStatus(data.get("status", "reported")),
            patient_id=data.get("patient_id"),
            patient_name=data.get("patient_name"),
            involved_staff=data.get("involved_staff", []),
            description=data.get("description", ""),
            immediate_actions=data.get("immediate_actions", ""),
            contributing_factors=data.get("contributing_factors", []),
            root_cause=data.get("root_cause"),
            root_cause_category=data.get("root_cause_category"),
            corrective_actions=[CorrectiveAction(**ca) for ca in data.get("corrective_actions", [])],
            preventive_actions=data.get("preventive_actions", ""),
            assigned_to=data.get("assigned_to"),
            review_date=date.fromisoformat(data["review_date"]) if data.get("review_date") else None,
            patient_outcome=data.get("patient_outcome"),
            financial_impact=data.get("financial_impact"),
            closed_at=datetime.fromisoformat(data["closed_at"]) if data.get("closed_at") else None,
            closed_by=data.get("closed_by"),
            lessons_learned=data.get("lessons_learned")
        )
    
    def report_incident(
        self,
        incident_date: date,
        description: str,
        incident_type: IncidentType,
        severity: IncidentSeverity,
        location: Optional[str] = None,
        patient_id: Optional[str] = None,
        patient_name: Optional[str] = None,
        involved_staff: Optional[List[str]] = None,
        immediate_actions: Optional[str] = None,
        incident_time: Optional[str] = None
    ) -> QualityIncident:
        """Reporta un nuevo incidente."""
        user = st.session_state.get("u_actual", {})
        
        incident = QualityIncident(
            id=str(uuid.uuid4()),
            reported_at=datetime.now(),
            reported_by=user.get("nombre", "Sistema"),
            reported_by_id=user.get("usuario_login", "system"),
            incident_date=incident_date,
            incident_time=incident_time,
            location=location,
            incident_type=incident_type,
            severity=severity,
            status=IncidentStatus.REPORTED,
            patient_id=patient_id,
            patient_name=patient_name,
            involved_staff=involved_staff or [],
            description=description,
            immediate_actions=immediate_actions or ""
        )
        
        self._incidents[incident.id] = incident
        self._save_incidents()
        
        # Alertas según severidad
        if severity in [IncidentSeverity.CRITICAL, IncidentSeverity.SERIOUS]:
            log_event("incident_critical", f"Critical incident reported: {incident.id} - {incident_type.value}")
        
        # Audit log
        audit_log(
            AuditEventType.DATA_EXPORT,
            resource_type="quality_incident",
            resource_id=incident.id,
            action="CREATE",
            description=f"Incident reported: {incident_type.value} - Severity: {severity.value}"
        )
        
        return incident
    
    def update_incident_status(
        self,
        incident_id: str,
        new_status: IncidentStatus,
        assigned_to: Optional[str] = None
    ) -> bool:
        """Actualiza estado del incidente."""
        if incident_id not in self._incidents:
            return False
        
        incident = self._incidents[incident_id]
        incident.status = new_status
        
        if assigned_to:
            incident.assigned_to = assigned_to
        
        if new_status == IncidentStatus.CLOSED:
            user = st.session_state.get("u_actual", {})
            incident.closed_at = datetime.now()
            incident.closed_by = user.get("nombre", "Sistema")
        
        self._save_incidents()
        
        log_event("quality", f"Incident {incident_id} status changed to {new_status.value}")
        return True
    
    def add_corrective_action(
        self,
        incident_id: str,
        description: str,
        responsible: str,
        due_date: Optional[date] = None
    ) -> bool:
        """Agrega acción correctiva al incidente."""
        if incident_id not in self._incidents:
            return False
        
        action = CorrectiveAction(
            id=str(uuid.uuid4()),
            description=description,
            responsible=responsible,
            due_date=due_date
        )
        
        incident = self._incidents[incident_id]
        incident.corrective_actions.append(action)
        
        # Cambiar estado si es necesario
        if incident.status == IncidentStatus.INVESTIGATING:
            incident.status = IncidentStatus.CORRECTIVE_ACTION
        
        self._save_incidents()
        return True
    
    def complete_corrective_action(
        self,
        incident_id: str,
        action_id: str,
        evidence: Optional[str] = None
    ) -> bool:
        """Marca acción correctiva como completada."""
        if incident_id not in self._incidents:
            return False
        
        incident = self._incidents[incident_id]
        user = st.session_state.get("u_actual", {})
        
        for action in incident.corrective_actions:
            if action.id == action_id:
                action.status = "completed"
                action.completed_at = datetime.now()
                action.completed_by = user.get("nombre", "Sistema")
                action.evidence = evidence
                
                self._save_incidents()
                return True
        
        return False
    
    def get_incidents(
        self,
        status: Optional[IncidentStatus] = None,
        severity: Optional[IncidentSeverity] = None,
        incident_type: Optional[IncidentType] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        assigned_to: Optional[str] = None
    ) -> List[QualityIncident]:
        """Obtiene incidentes con filtros."""
        results = []
        
        for incident in self._incidents.values():
            if status and incident.status != status:
                continue
            if severity and incident.severity != severity:
                continue
            if incident_type and incident.incident_type != incident_type:
                continue
            if date_from and incident.incident_date < date_from:
                continue
            if date_to and incident.incident_date > date_to:
                continue
            if assigned_to and incident.assigned_to != assigned_to:
                continue
            
            results.append(incident)
        
        return sorted(results, key=lambda x: x.incident_date, reverse=True)
    
    def get_incident_statistics(self, date_from: date, date_to: date) -> Dict[str, Any]:
        """Estadísticas de incidentes para el período."""
        incidents = self.get_incidents(date_from=date_from, date_to=date_to)
        
        if not incidents:
            return {
                "total": 0,
                "by_severity": {},
                "by_type": {},
                "by_status": {},
                "trend": "stable"
            }
        
        # Agrupar por severidad
        by_severity = {}
        for i in incidents:
            sev = i.severity.value
            by_severity[sev] = by_severity.get(sev, 0) + 1
        
        # Agrupar por tipo
        by_type = {}
        for i in incidents:
            t = i.incident_type.value
            by_type[t] = by_type.get(t, 0) + 1
        
        # Agrupar por status
        by_status = {}
        for i in incidents:
            s = i.status.value
            by_status[s] = by_status.get(s, 0) + 1
        
        return {
            "total": len(incidents),
            "by_severity": by_severity,
            "by_type": by_type,
            "by_status": by_status,
            "critical_count": by_severity.get("critical", 0),
            "serious_count": by_severity.get("serious", 0),
            "open_count": by_status.get("reported", 0) + by_status.get("under_review", 0) + by_status.get("investigating", 0)
        }
    
    def render_quality_dashboard(self):
        """Renderiza dashboard de calidad."""
        st.title("🏥 Gestión de Calidad e Incidentes")
        
        # Tabs
        tabs = st.tabs(["📊 Dashboard", "⚠️ Incidentes", "➕ Reportar Incidente", "📈 Indicadores"])
        
        with tabs[0]:
            self._render_quality_overview()
        
        with tabs[1]:
            self._render_incidents_list()
        
        with tabs[2]:
            self._render_report_incident_form()
        
        with tabs[3]:
            self._render_quality_indicators()
    
    def _render_quality_overview(self):
        """Vista general de calidad."""
        st.header("📊 Estado de Calidad")
        
        # Período de análisis
        col1, col2 = st.columns(2)
        with col1:
            fecha_desde = st.date_input("Desde", value=date.today() - timedelta(days=30))
        with col2:
            fecha_hasta = st.date_input("Hasta", value=date.today())
        
        stats = self.get_incident_statistics(fecha_desde, fecha_hasta)
        
        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Incidentes", stats["total"])
        with col2:
            st.metric("🔴 Críticos", stats.get("critical_count", 0))
        with col3:
            st.metric("🟠 Graves", stats.get("serious_count", 0))
        with col4:
            st.metric("📂 Abiertos", stats.get("open_count", 0))
        
        st.divider()
        
        # Gráficos
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Por Severidad")
            if stats["by_severity"]:
                import pandas as pd
                df = pd.DataFrame([
                    {"Severidad": k, "Cantidad": v}
                    for k, v in stats["by_severity"].items()
                ])
                st.bar_chart(df.set_index("Severidad"))
            else:
                st.info("Sin datos")
        
        with col2:
            st.subheader("Por Tipo")
            if stats["by_type"]:
                import pandas as pd
                df = pd.DataFrame([
                    {"Tipo": k, "Cantidad": v}
                    for k, v in stats["by_type"].items()
                ])
                st.bar_chart(df.set_index("Tipo"))
            else:
                st.info("Sin datos")
    
    def _render_incidents_list(self):
        """Lista de incidentes."""
        st.header("⚠️ Registro de Incidentes")
        
        # Filtros
        col1, col2, col3 = st.columns(3)
        
        with col1:
            status_filter = st.selectbox(
                "Estado",
                options=["Todos"] + [s.value for s in IncidentStatus],
                index=0
            )
        
        with col2:
            severity_filter = st.selectbox(
                "Severidad",
                options=["Todos"] + [s.value for s in IncidentSeverity],
                index=0
            )
        
        with col3:
            type_filter = st.selectbox(
                "Tipo",
                options=["Todos"] + [t.value for t in IncidentType],
                index=0
            )
        
        # Obtener incidentes
        status = IncidentStatus(status_filter) if status_filter != "Todos" else None
        severity = IncidentSeverity(severity_filter) if severity_filter != "Todos" else None
        incident_type = IncidentType(type_filter) if type_filter != "Todos" else None
        
        incidents = self.get_incidents(status=status, severity=severity, incident_type=incident_type)
        
        if not incidents:
            st.info("📭 No hay incidentes que coincidan con los filtros")
        else:
            for incident in incidents:
                severity_colors = {
                    IncidentSeverity.CRITICAL: "🔴",
                    IncidentSeverity.SERIOUS: "🟠",
                    IncidentSeverity.MODERATE: "🟡",
                    IncidentSeverity.MINOR: "🟢",
                    IncidentSeverity.NEAR_MISS: "🔵"
                }
                icon = severity_colors.get(incident.severity, "⚪")
                
                with st.expander(f"{icon} {incident.incident_date} - {incident.incident_type.value} ({incident.status.value})"):
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**Descripción:** {incident.description}")
                        
                        if incident.patient_name:
                            st.markdown(f"**Paciente:** {incident.patient_name}")
                        
                        st.markdown(f"**Ubicación:** {incident.location or 'No especificada'}")
                        st.markdown(f"**Reportado por:** {incident.reported_by} el {incident.reported_at.strftime('%d/%m/%Y %H:%M')}")
                        
                        if incident.immediate_actions:
                            st.markdown(f"**Acciones inmediatas:** {incident.immediate_actions}")
                    
                    with col2:
                        st.markdown(f"**Severidad:** {incident.severity.value}")
                        st.markdown(f"**Estado:** {incident.status.value}")
                        
                        if incident.assigned_to:
                            st.markdown(f"**Asignado a:** {incident.assigned_to}")
                        
                        # Cambiar estado
                        new_status = st.selectbox(
                            "Cambiar estado",
                            options=[s.value for s in IncidentStatus],
                            index=[s.value for s in IncidentStatus].index(incident.status.value),
                            key=f"status_{incident.id}"
                        )
                        
                        if new_status != incident.status.value:
                            if st.button("Actualizar", key=f"upd_{incident.id}"):
                                self.update_incident_status(incident.id, IncidentStatus(new_status))
                                st.rerun()
    
    def _render_report_incident_form(self):
        """Formulario para reportar incidente."""
        st.header("➕ Reportar Nuevo Incidente/Evento Adverso")
        
        st.markdown("""
        <div style="background: rgba(239, 68, 68, 0.1); border-left: 4px solid #ef4444; padding: 15px; margin-bottom: 20px;">
            <p style="margin: 0; color: #fca5a5;">
                <strong>⚠️ Confidencialidad:</strong> Este reporte es confidencial y se utiliza para mejorar la calidad. 
                No se usará para sanciones individuales sino para identificar oportunidades de mejora del sistema.
            </p>
        </div>
        """, unsafe_allow_html=True)
        
        with st.form(key="report_incident_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                incident_date = st.date_input("Fecha del incidente *", value=date.today())
                incident_time = st.time_input("Hora aproximada", value=None)
                location = st.text_input("Ubicación (sala, consultorio, etc.)")
            
            with col2:
                incident_type = st.selectbox(
                    "Tipo de incidente *",
                    options=[t for t in IncidentType]
                )
                
                severity = st.selectbox(
                    "Severidad *",
                    options=[s for s in IncidentSeverity],
                    format_func=lambda x: {
                        IncidentSeverity.CRITICAL: "🔴 Crítico (daño grave/muerte)",
                        IncidentSeverity.SERIOUS: "🟠 Grave (daño significativo)",
                        IncidentSeverity.MODERATE: "🟡 Moderado (daño leve)",
                        IncidentSeverity.MINOR: "🟢 Menor (sin daño)",
                        IncidentSeverity.NEAR_MISS: "🔵 Casi ocurre (close call)"
                    }.get(x, x.value)
                )
            
            # Paciente involucrado (opcional)
            st.subheader("Paciente involucrado (opcional)")
            col1, col2 = st.columns(2)
            with col1:
                patient_id = st.text_input("ID del paciente")
            with col2:
                patient_name = st.text_input("Nombre del paciente")
            
            # Descripción
            st.subheader("Descripción del incidente")
            description = st.text_area(
                "Describa qué ocurrió *",
                placeholder="Describa claramente la secuencia de eventos...",
                height=100
            )
            
            immediate_actions = st.text_area(
                "Acciones tomadas inmediatamente",
                placeholder="¿Qué se hizo en el momento?",
                height=80
            )
            
            involved_staff = st.text_input(
                "Personal involucrado",
                placeholder="Nombres separados por comas"
            )
            
            submitted = st.form_submit_button("📋 Reportar Incidente", use_container_width=True, type="primary")
            
            if submitted:
                if not description:
                    st.error("❌ Debe proporcionar una descripción del incidente")
                else:
                    staff_list = [s.strip() for s in involved_staff.split(",") if s.strip()]
                    
                    time_str = incident_time.strftime("%H:%M") if incident_time else None
                    
                    incident = self.report_incident(
                        incident_date=incident_date,
                        description=description,
                        incident_type=incident_type,
                        severity=severity,
                        location=location,
                        patient_id=patient_id or None,
                        patient_name=patient_name or None,
                        involved_staff=staff_list,
                        immediate_actions=immediate_actions or None,
                        incident_time=time_str
                    )
                    
                    st.success(f"✅ Incidente reportado exitosamente. ID: {incident.id[:8]}")
                    
                    # Si es crítico, mostrar alerta adicional
                    if severity == IncidentSeverity.CRITICAL:
                        st.error("🚨 ALERTA: Incidente crítico reportado. Se notificará a la dirección médica.")
    
    def _render_quality_indicators(self):
        """Indicadores de calidad para acreditación."""
        st.header("📈 Indicadores de Calidad")
        
        st.info("🚧 Módulo de indicadores en desarrollo. Aquí se mostrarán métricas como:")
        
        st.markdown("""
        - **Tasa de incidentes por 1000 atenciones**
        - **Tiempo promedio de resolución de incidentes**
        - **Cumplimiento de acciones correctivas**
        - **Tasa de infecciones nosocomiales**
        - **Eventos adversos prevenibles**
        - **Satisfacción del paciente**
        """)


# Singleton
_quality_system: Optional[QualityManagementSystem] = None


def get_quality_system() -> QualityManagementSystem:
    """Obtiene instancia del sistema de calidad."""
    global _quality_system
    if _quality_system is None:
        _quality_system = QualityManagementSystem()
    return _quality_system
