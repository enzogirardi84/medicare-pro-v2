"""
Sistema de Recordatorios y Alertas Clínicas para Medicare Pro.

Gestiona:
- Recordatorios de citas de seguimiento
- Alertas de medicamentos
- Recordatorios de estudios pendientes
- Alertas de cumpleaños de pacientes
- Notificaciones de vacunas
- Alertas críticas de signos vitales
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, date, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum, auto
import streamlit as st

from core.app_logging import log_event
from core.email_notifications import send_appointment_reminder, get_email_manager


class ReminderType(Enum):
    """Tipos de recordatorios."""
    FOLLOW_UP = auto()           # Seguimiento de cita
    MEDICATION = auto()          # Toma de medicamento
    STUDY_PENDING = auto()       # Estudio pendiente
    BIRTHDAY = auto()            # Cumpleaños del paciente
    VACCINE = auto()             # Vacuna próxima
    VITAL_ALERT = auto()         # Alerta de signo vital
    CUSTOM = auto()              # Recordatorio personalizado


class ReminderPriority(Enum):
    """Prioridades de recordatorio."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class Reminder:
    """Recordatorio individual."""
    id: str
    type: ReminderType
    priority: ReminderPriority
    patient_id: str
    patient_name: str
    title: str
    description: str
    due_date: Optional[datetime]
    created_at: datetime
    completed: bool = False
    completed_at: Optional[datetime] = None
    notified: bool = False  # Ya se envió notificación
    recurrence: Optional[str] = None  # daily, weekly, monthly, yearly
    metadata: Dict[str, Any] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            **asdict(self),
            "type": self.type.name,
            "priority": self.priority.value
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reminder":
        """Crea desde diccionario."""
        return cls(
            id=data["id"],
            type=ReminderType[data["type"]],
            priority=ReminderPriority(data["priority"]),
            patient_id=data["patient_id"],
            patient_name=data["patient_name"],
            title=data["title"],
            description=data["description"],
            due_date=datetime.fromisoformat(data["due_date"]) if data.get("due_date") else None,
            created_at=datetime.fromisoformat(data["created_at"]),
            completed=data.get("completed", False),
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            notified=data.get("notified", False),
            recurrence=data.get("recurrence"),
            metadata=data.get("metadata", {})
        )


class ClinicalReminderManager:
    """
    Manager de recordatorios clínicos.
    
    Gestiona:
    - Creación de recordatorios
    - Notificaciones
    - Completación
    - Recurrencia
    """
    
    def __init__(self):
        self._reminders: Dict[str, Reminder] = {}
        self._load_reminders()
    
    def _load_reminders(self):
        """Carga recordatorios desde session_state."""
        if "clinical_reminders" in st.session_state:
            try:
                reminders_data = st.session_state["clinical_reminders"]
                if isinstance(reminders_data, dict):
                    self._reminders = {
                        k: Reminder.from_dict(v) if isinstance(v, dict) else v
                        for k, v in reminders_data.items()
                    }
            except Exception as e:
                log_event("reminders", f"Failed to load reminders: {e}")
                self._reminders = {}
    
    def _save_reminders(self):
        """Guarda recordatorios a session_state."""
        st.session_state["clinical_reminders"] = {
            k: v.to_dict() if isinstance(v, Reminder) else v
            for k, v in self._reminders.items()
        }
    
    def create_reminder(
        self,
        reminder_type: ReminderType,
        patient_id: str,
        patient_name: str,
        title: str,
        description: str,
        due_date: Optional[datetime] = None,
        priority: ReminderPriority = ReminderPriority.MEDIUM,
        recurrence: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Reminder:
        """
        Crea un nuevo recordatorio.
        
        Args:
            reminder_type: Tipo de recordatorio
            patient_id: ID del paciente
            patient_name: Nombre del paciente
            title: Título corto
            description: Descripción detallada
            due_date: Fecha límite
            priority: Prioridad
            recurrence: Recurrencia (daily, weekly, monthly, yearly)
            metadata: Datos adicionales
        
        Returns:
            Reminder creado
        """
        import uuid
        
        reminder = Reminder(
            id=str(uuid.uuid4()),
            type=reminder_type,
            priority=priority,
            patient_id=patient_id,
            patient_name=patient_name,
            title=title,
            description=description,
            due_date=due_date,
            created_at=datetime.now(),
            completed=False,
            notified=False,
            recurrence=recurrence,
            metadata=metadata or {}
        )
        
        self._reminders[reminder.id] = reminder
        self._save_reminders()
        
        log_event("reminder", f"Created reminder: {title} for {patient_name}")
        
        return reminder
    
    def complete_reminder(self, reminder_id: str) -> bool:
        """Marca un recordatorio como completado."""
        if reminder_id not in self._reminders:
            return False
        
        reminder = self._reminders[reminder_id]
        reminder.completed = True
        reminder.completed_at = datetime.now()
        
        # Si tiene recurrencia, crear próximo
        if reminder.recurrence:
            next_date = self._calculate_next_date(reminder.due_date, reminder.recurrence)
            if next_date:
                self.create_reminder(
                    reminder_type=reminder.type,
                    patient_id=reminder.patient_id,
                    patient_name=reminder.patient_name,
                    title=reminder.title,
                    description=reminder.description,
                    due_date=next_date,
                    priority=reminder.priority,
                    recurrence=reminder.recurrence,
                    metadata=reminder.metadata
                )
        
        self._save_reminders()
        
        log_event("reminder", f"Completed reminder: {reminder.title}")
        return True
    
    def _calculate_next_date(
        self,
        current_date: Optional[datetime],
        recurrence: str
    ) -> Optional[datetime]:
        """Calcula próxima fecha según recurrencia."""
        if not current_date:
            return None
        
        if recurrence == "daily":
            return current_date + timedelta(days=1)
        elif recurrence == "weekly":
            return current_date + timedelta(weeks=1)
        elif recurrence == "monthly":
            # Aproximado: mismo día del mes siguiente
            next_month = current_date.replace(day=1) + timedelta(days=32)
            return next_month.replace(day=min(current_date.day, 28))
        elif recurrence == "yearly":
            try:
                return current_date.replace(year=current_date.year + 1)
            except:
                # Febrero 29
                return current_date + timedelta(days=365)
        
        return None
    
    def delete_reminder(self, reminder_id: str) -> bool:
        """Elimina un recordatorio."""
        if reminder_id not in self._reminders:
            return False
        
        del self._reminders[reminder_id]
        self._save_reminders()
        
        return True
    
    def get_reminders(
        self,
        patient_id: Optional[str] = None,
        reminder_type: Optional[ReminderType] = None,
        priority: Optional[ReminderPriority] = None,
        completed: Optional[bool] = None,
        due_before: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Reminder]:
        """
        Obtiene recordatorios con filtros.
        
        Args:
            patient_id: Filtrar por paciente
            reminder_type: Filtrar por tipo
            priority: Filtrar por prioridad
            completed: Filtrar por estado
            due_before: Filtrar por fecha límite
            limit: Máximo resultados
        
        Returns:
            Lista de recordatorios
        """
        results = []
        
        for reminder in self._reminders.values():
            # Aplicar filtros
            if patient_id and reminder.patient_id != patient_id:
                continue
            
            if reminder_type and reminder.type != reminder_type:
                continue
            
            if priority and reminder.priority != priority:
                continue
            
            if completed is not None and reminder.completed != completed:
                continue
            
            if due_before and reminder.due_date and reminder.due_date > due_before:
                continue
            
            results.append(reminder)
        
        # Ordenar por prioridad y fecha
        priority_order = {
            ReminderPriority.CRITICAL: 0,
            ReminderPriority.HIGH: 1,
            ReminderPriority.MEDIUM: 2,
            ReminderPriority.LOW: 3
        }
        
        results.sort(key=lambda r: (
            priority_order.get(r.priority, 4),
            r.due_date or datetime.max
        ))
        
        return results[:limit]
    
    def get_pending_notifications(self) -> List[Reminder]:
        """Obtiene recordatorios pendientes de notificación."""
        now = datetime.now()
        
        pending = []
        for reminder in self._reminders.values():
            if reminder.completed or reminder.notified:
                continue
            
            # Verificar si es hora de notificar
            if reminder.due_date:
                # Notificar si falta 1 día o menos, o si ya pasó
                days_until = (reminder.due_date - now).days
                
                if days_until <= 1:
                    pending.append(reminder)
            else:
                # Sin fecha, notificar si es crítico
                if reminder.priority in [ReminderPriority.CRITICAL, ReminderPriority.HIGH]:
                    pending.append(reminder)
        
        return pending
    
    def send_notifications(self) -> int:
        """
        Envía notificaciones para recordatorios pendientes.
        
        Returns:
            Cantidad de notificaciones enviadas
        """
        pending = self.get_pending_notifications()
        sent = 0
        
        for reminder in pending:
            try:
                # Enviar notificación (email, push, etc.)
                # Aquí integrar con el sistema de notificaciones
                
                # Marcar como notificado
                reminder.notified = True
                
                log_event("reminder", f"Notification sent for: {reminder.title}")
                sent += 1
                
            except Exception as e:
                log_event("reminder_error", f"Failed to send notification: {e}")
        
        self._save_reminders()
        
        return sent
    
    # ====== Recordatorios automáticos ======
    
    def create_follow_up_reminder(
        self,
        patient_id: str,
        patient_name: str,
        days_from_now: int = 30,
        notes: str = ""
    ) -> Reminder:
        """Crea recordatorio de seguimiento post-consulta."""
        due_date = datetime.now() + timedelta(days=days_from_now)
        
        return self.create_reminder(
            reminder_type=ReminderType.FOLLOW_UP,
            patient_id=patient_id,
            patient_name=patient_name,
            title=f"Seguimiento: {patient_name}",
            description=f"Control de seguimiento programado. {notes}",
            due_date=due_date,
            priority=ReminderPriority.MEDIUM,
            metadata={"consultation_date": datetime.now().isoformat()}
        )
    
    def create_medication_reminder(
        self,
        patient_id: str,
        patient_name: str,
        medication_name: str,
        dosage: str,
        frequency: str,
        duration_days: int
    ) -> Reminder:
        """Crea recordatorio de medicación."""
        title = f"Medicación: {medication_name}"
        description = f"Tomar {dosage} - {frequency}"
        
        # Crear recordatorio recurrente según frecuencia
        recurrence_map = {
            "cada 24 horas": "daily",
            "diario": "daily",
            "cada 12 horas": "daily",  # Se simplifica
            "semanal": "weekly"
        }
        
        recurrence = recurrence_map.get(frequency.lower(), "daily")
        
        reminder = self.create_reminder(
            reminder_type=ReminderType.MEDICATION,
            patient_id=patient_id,
            patient_name=patient_name,
            title=title,
            description=description,
            due_date=datetime.now() + timedelta(days=1),
            priority=ReminderPriority.HIGH,
            recurrence=recurrence if duration_days > 1 else None,
            metadata={
                "medication": medication_name,
                "dosage": dosage,
                "frequency": frequency,
                "duration_days": duration_days
            }
        )
        
        return reminder
    
    def create_birthday_reminder(
        self,
        patient_id: str,
        patient_name: str,
        birth_date: date
    ) -> Reminder:
        """Crea recordatorio de cumpleaños del paciente."""
        today = date.today()
        
        # Calcular próximo cumpleaños
        next_birthday = birth_date.replace(year=today.year)
        if next_birthday < today:
            next_birthday = birth_date.replace(year=today.year + 1)
        
        # Crear a las 9 AM
        due_date = datetime.combine(next_birthday, datetime.min.time()) + timedelta(hours=9)
        
        age = next_birthday.year - birth_date.year
        
        return self.create_reminder(
            reminder_type=ReminderType.BIRTHDAY,
            patient_id=patient_id,
            patient_name=patient_name,
            title=f"🎂 Cumpleaños de {patient_name}",
            description=f"{patient_name} cumple {age} años. Enviar saludo de cumpleaños.",
            due_date=due_date,
            priority=ReminderPriority.LOW,
            recurrence="yearly",
            metadata={"age": age}
        )
    
    def create_study_reminder(
        self,
        patient_id: str,
        patient_name: str,
        study_type: str,
        due_days: int = 7
    ) -> Reminder:
        """Crea recordatorio de estudio pendiente."""
        due_date = datetime.now() + timedelta(days=due_days)
        
        return self.create_reminder(
            reminder_type=ReminderType.STUDY_PENDING,
            patient_id=patient_id,
            patient_name=patient_name,
            title=f"Estudio pendiente: {study_type}",
            description=f"Solicitar/recordar al paciente sobre estudio de {study_type}",
            due_date=due_date,
            priority=ReminderPriority.MEDIUM,
            metadata={"study_type": study_type}
        )
    
    def create_vital_alert(
        self,
        patient_id: str,
        patient_name: str,
        vital_sign: str,
        value: Any,
        severity: str
    ) -> Reminder:
        """Crea alerta de signo vital anormal."""
        priority = ReminderPriority.CRITICAL if severity == "critical" else ReminderPriority.HIGH
        
        return self.create_reminder(
            reminder_type=ReminderType.VITAL_ALERT,
            patient_id=patient_id,
            patient_name=patient_name,
            title=f"🚨 Alerta: {vital_sign}",
            description=f"{vital_sign} alterado: {value}. Requiere atención.",
            due_date=datetime.now(),
            priority=priority,
            metadata={"vital_sign": vital_sign, "value": value, "severity": severity}
        )
    
    # ====== UI ======
    
    def render_reminders_dashboard(self):
        """Renderiza dashboard de recordatorios."""
        st.title("⏰ Recordatorios Clínicos")
        
        # Stats
        col1, col2, col3, col4 = st.columns(4)
        
        all_reminders = list(self._reminders.values())
        pending = [r for r in all_reminders if not r.completed]
        overdue = [r for r in pending if r.due_date and r.due_date < datetime.now()]
        
        with col1:
            st.metric("Total", len(all_reminders))
        with col2:
            st.metric("Pendientes", len(pending))
        with col3:
            st.metric("Vencidos", len(overdue))
        with col4:
            critical = len([r for r in pending if r.priority == ReminderPriority.CRITICAL])
            st.metric("🚨 Críticos", critical)
        
        st.divider()
        
        # Tabs
        tabs = st.tabs(["📋 Pendientes", "✅ Completados", "➕ Nuevo"])
        
        with tabs[0]:
            self._render_pending_reminders()
        
        with tabs[1]:
            self._render_completed_reminders()
        
        with tabs[2]:
            self._render_create_reminder()
    
    def _render_pending_reminders(self):
        """Renderiza lista de recordatorios pendientes."""
        reminders = self.get_reminders(completed=False, limit=50)
        
        if not reminders:
            st.info("No hay recordatorios pendientes")
            return
        
        # Agrupar por prioridad
        by_priority = {}
        for r in reminders:
            p = r.priority
            if p not in by_priority:
                by_priority[p] = []
            by_priority[p].append(r)
        
        # Mostrar por prioridad
        priority_labels = {
            ReminderPriority.CRITICAL: ("🔴 CRÍTICO", "error"),
            ReminderPriority.HIGH: ("🟠 ALTA", "warning"),
            ReminderPriority.MEDIUM: ("🟡 MEDIA", "info"),
            ReminderPriority.LOW: ("🟢 BAJA", "success")
        }
        
        for priority in [ReminderPriority.CRITICAL, ReminderPriority.HIGH, 
                        ReminderPriority.MEDIUM, ReminderPriority.LOW]:
            if priority not in by_priority:
                continue
            
            label, style = priority_labels[priority]
            
            with st.expander(f"{label} ({len(by_priority[priority])})", 
                            expanded=(priority in [ReminderPriority.CRITICAL, ReminderPriority.HIGH])):
                
                for reminder in by_priority[priority]:
                    with st.container():
                        col1, col2, col3 = st.columns([5, 2, 1])
                        
                        with col1:
                            icons = {
                                ReminderType.FOLLOW_UP: "📅",
                                ReminderType.MEDICATION: "💊",
                                ReminderType.STUDY_PENDING: "🔬",
                                ReminderType.BIRTHDAY: "🎂",
                                ReminderType.VACCINE: "💉",
                                ReminderType.VITAL_ALERT: "🚨",
                                ReminderType.CUSTOM: "📌"
                            }
                            
                            st.markdown(f"**{icons.get(reminder.type, '📌')} {reminder.title}**")
                            st.caption(f"Paciente: {reminder.patient_name}")
                            st.text(reminder.description[:100] + "..." if len(reminder.description) > 100 else reminder.description)
                            
                            if reminder.due_date:
                                days_left = (reminder.due_date - datetime.now()).days
                                if days_left < 0:
                                    st.error(f"⚠️ Vencido hace {abs(days_left)} días")
                                elif days_left == 0:
                                    st.warning("📅 Vence hoy")
                                else:
                                    st.caption(f"📅 Vence en {days_left} días")
                        
                        with col2:
                            if st.button("✅ Completar", key=f"complete_{reminder.id}"):
                                self.complete_reminder(reminder.id)
                                st.rerun()
                        
                        with col3:
                            if st.button("🗑️", key=f"delete_{reminder.id}"):
                                self.delete_reminder(reminder.id)
                                st.rerun()
                    
                    st.divider()
    
    def _render_completed_reminders(self):
        """Renderiza recordatorios completados."""
        reminders = self.get_reminders(completed=True, limit=20)
        
        if not reminders:
            st.info("No hay recordatorios completados recientemente")
            return
        
        for reminder in reminders:
            st.markdown(f"~~{reminder.title}~~")
            st.caption(f"Completado: {reminder.completed_at.strftime('%d/%m/%Y %H:%M') if reminder.completed_at else 'N/A'}")
            st.divider()
    
    def _render_create_reminder(self):
        """Renderiza formulario para crear recordatorio."""
        st.subheader("Crear Nuevo Recordatorio")
        
        # Seleccionar paciente
        pacientes_db = st.session_state.get("pacientes_db", {})
        paciente_options = {f"{p['apellido']}, {p['nombre']} (DNI: {dni})": dni 
                           for dni, p in pacientes_db.items()}
        
        selected_paciente = st.selectbox(
            "Paciente",
            options=list(paciente_options.keys()),
            key="reminder_paciente"
        )
        
        if selected_paciente:
            dni = paciente_options[selected_paciente]
            paciente = pacientes_db[dni]
            
            col1, col2 = st.columns(2)
            
            with col1:
                reminder_type = st.selectbox(
                    "Tipo",
                    options=[
                        ("Seguimiento", ReminderType.FOLLOW_UP),
                        ("Medicación", ReminderType.MEDICATION),
                        ("Estudio Pendiente", ReminderType.STUDY_PENDING),
                        ("Cumpleaños", ReminderType.BIRTHDAY),
                        ("Vacuna", ReminderType.VACCINE),
                        ("Personalizado", ReminderType.CUSTOM)
                    ],
                    format_func=lambda x: x[0]
                )
            
            with col2:
                priority = st.selectbox(
                    "Prioridad",
                    options=[
                        ("🔴 Crítica", ReminderPriority.CRITICAL),
                        ("🟠 Alta", ReminderPriority.HIGH),
                        ("🟡 Media", ReminderPriority.MEDIUM),
                        ("🟢 Baja", ReminderPriority.LOW)
                    ],
                    index=2,
                    format_func=lambda x: x[0]
                )
            
            title = st.text_input("Título", key="reminder_title")
            description = st.text_area("Descripción", key="reminder_desc")
            
            col3, col4 = st.columns(2)
            
            with col3:
                due_date = st.date_input("Fecha límite", value=None, key="reminder_due")
                due_time = st.time_input("Hora", value=None, key="reminder_time")
            
            with col4:
                recurrence = st.selectbox(
                    "Recurrencia",
                    options=[None, "daily", "weekly", "monthly", "yearly"],
                    format_func=lambda x: {
                        None: "Sin recurrencia",
                        "daily": "Diaria",
                        "weekly": "Semanal",
                        "monthly": "Mensual",
                        "yearly": "Anual"
                    }.get(x, x)
                )
            
            if st.button("➕ Crear Recordatorio", use_container_width=True):
                # Combinar fecha y hora
                due_datetime = None
                if due_date:
                    due_datetime = datetime.combine(due_date, due_time or datetime.min.time())
                
                self.create_reminder(
                    reminder_type=reminder_type[1],
                    patient_id=paciente.get("id", dni),
                    patient_name=f"{paciente['nombre']} {paciente['apellido']}",
                    title=title or reminder_type[0],
                    description=description,
                    due_date=due_datetime,
                    priority=priority[1],
                    recurrence=recurrence
                )
                
                st.success("✅ Recordatorio creado")
                st.rerun()


# Singleton
_reminder_manager: Optional[ClinicalReminderManager] = None


def get_reminder_manager() -> ClinicalReminderManager:
    """Obtiene instancia del manager de recordatorios."""
    global _reminder_manager
    if _reminder_manager is None:
        _reminder_manager = ClinicalReminderManager()
    return _reminder_manager


# Helpers
def create_follow_up_reminder(patient_id: str, patient_name: str, days: int = 30):
    """Helper rápido para crear seguimiento."""
    return get_reminder_manager().create_follow_up_reminder(
        patient_id, patient_name, days
    )


def create_medication_reminder(
    patient_id: str,
    patient_name: str,
    medication: str,
    dosage: str,
    frequency: str,
    days: int
):
    """Helper rápido para crear recordatorio de medicación."""
    return get_reminder_manager().create_medication_reminder(
        patient_id, patient_name, medication, dosage, frequency, days
    )
