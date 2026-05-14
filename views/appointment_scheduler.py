"""
Sistema de Agendamiento de Turnos/Citas para Medicare Pro.

Características:
- Calendario interactivo
- Gestión de disponibilidad de médicos
- Recordatorios automáticos
- Lista de espera
- Integración con evoluciones
"""

import streamlit as st
from datetime import datetime, date, timedelta, time
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, asdict
from enum import Enum, auto
from collections import defaultdict

from core.app_logging import log_event
from core.clinical_reminders import get_reminder_manager, ReminderType, ReminderPriority
from core.data_validation import get_validator


class AppointmentStatus(Enum):
    """Estados de un turno."""
    SCHEDULED = "scheduled"      # Agendado
    CONFIRMED = "confirmed"      # Confirmado
    IN_PROGRESS = "in_progress"  # En atención
    COMPLETED = "completed"      # Completado
    CANCELLED = "cancelled"      # Cancelado
    NO_SHOW = "no_show"          # No asistió


class AppointmentType(Enum):
    """Tipos de turno."""
    CONSULTATION = "consulta"
    FOLLOW_UP = "seguimiento"
    PROCEDURE = "procedimiento"
    SURGERY = "cirugia"
    EMERGENCY = "emergencia"


@dataclass
class Appointment:
    """Turno/Cita médica."""
    id: str
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    date: date
    time: time
    duration_minutes: int
    type: AppointmentType
    status: AppointmentStatus
    reason: str
    notes: Optional[str] = None
    created_at: datetime = None
    confirmed_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    reminder_sent: bool = False
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
    
    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "type": self.type.value,
            "status": self.status.value,
            "date": self.date.isoformat(),
            "time": self.time.isoformat()
        }


class AppointmentScheduler:
    """
    Scheduler de turnos médicos.
    """
    
    DEFAULT_SLOT_DURATION = 30  # minutos
    
    def __init__(self):
        self._appointments: Dict[str, Appointment] = {}
        self._doctor_schedule: Dict[str, Dict[date, List[time]]] = defaultdict(lambda: defaultdict(list))
        self._load_data()
    
    def _load_data(self):
        """Carga datos desde session_state."""
        if "appointments" in st.session_state:
            try:
                data = st.session_state["appointments"]
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict):
                            self._appointments[k] = Appointment(
                                id=v["id"],
                                patient_id=v["patient_id"],
                                patient_name=v["patient_name"],
                                doctor_id=v["doctor_id"],
                                doctor_name=v["doctor_name"],
                                date=date.fromisoformat(v["date"]),
                                time=time.fromisoformat(v["time"]),
                                duration_minutes=v["duration_minutes"],
                                type=AppointmentType(v["type"]),
                                status=AppointmentStatus(v["status"]),
                                reason=v["reason"],
                                notes=v.get("notes"),
                                created_at=datetime.fromisoformat(v["created_at"]),
                                confirmed_at=datetime.fromisoformat(v["confirmed_at"]) if v.get("confirmed_at") else None,
                                completed_at=datetime.fromisoformat(v["completed_at"]) if v.get("completed_at") else None,
                                reminder_sent=v.get("reminder_sent", False)
                            )
            except Exception as e:
                log_event("scheduler", f"Error loading appointments: {e}")
    
    def _save_data(self):
        """Guarda datos a session_state."""
        data = {k: v.to_dict() for k, v in self._appointments.items()}
        st.session_state["appointments"] = data
    
    def create_appointment(
        self,
        patient_id: str,
        patient_name: str,
        doctor_id: str,
        doctor_name: str,
        appointment_date: date,
        appointment_time: time,
        reason: str,
        appointment_type: AppointmentType = AppointmentType.CONSULTATION,
        duration: int = 30,
        notes: Optional[str] = None
    ) -> Optional[Appointment]:
        """
        Crea un nuevo turno.
        
        Returns:
            Appointment creado o None si hay conflicto
        """
        import uuid
        
        # Verificar disponibilidad
        if not self.is_slot_available(doctor_id, appointment_date, appointment_time, duration):
            st.error("❌ El horario seleccionado no está disponible")
            return None
        
        appointment = Appointment(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            patient_name=patient_name,
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            date=appointment_date,
            time=appointment_time,
            duration_minutes=duration,
            type=appointment_type,
            status=AppointmentStatus.SCHEDULED,
            reason=reason,
            notes=notes
        )
        
        self._appointments[appointment.id] = appointment
        self._save_data()
        
        # Crear recordatorio
        reminder_mgr = get_reminder_manager()
        appointment_datetime = datetime.combine(appointment_date, appointment_time)
        
        reminder_mgr.create_reminder(
            reminder_type=ReminderType.CUSTOM,
            patient_id=patient_id,
            patient_name=patient_name,
            title=f"Turno: {patient_name} - Dr. {doctor_name}",
            description=f"Razón: {reason}",
            due_date=appointment_datetime - timedelta(hours=24),  # Recordar 24h antes
            priority=ReminderPriority.MEDIUM
        )
        
        log_event("scheduler", f"Appointment created: {patient_name} with {doctor_name} on {appointment_date} {appointment_time}")
        
        st.success("✅ Turno agendado exitosamente")
        return appointment
    
    def is_slot_available(
        self,
        doctor_id: str,
        check_date: date,
        check_time: time,
        duration: int = 30
    ) -> bool:
        """Verifica si un horario está disponible."""
        check_datetime = datetime.combine(check_date, check_time)
        check_end = check_datetime + timedelta(minutes=duration)
        
        for apt in self._appointments.values():
            if apt.doctor_id != doctor_id:
                continue
            if apt.date != check_date:
                continue
            if apt.status in [AppointmentStatus.CANCELLED, AppointmentStatus.NO_SHOW]:
                continue
            
            apt_datetime = datetime.combine(apt.date, apt.time)
            apt_end = apt_datetime + timedelta(minutes=apt.duration_minutes)
            
            # Verificar solapamiento
            if (check_datetime < apt_end and check_end > apt_datetime):
                return False
        
        return True
    
    def get_available_slots(
        self,
        doctor_id: str,
        check_date: date,
        start_time: time = time(9, 0),
        end_time: time = time(18, 0),
        slot_duration: int = 30
    ) -> List[time]:
        """Obtiene horarios disponibles para un médico en una fecha."""
        available = []
        
        current = datetime.combine(check_date, start_time)
        end = datetime.combine(check_date, end_time)
        
        while current < end:
            slot_time = current.time()
            
            if self.is_slot_available(doctor_id, check_date, slot_time, slot_duration):
                available.append(slot_time)
            
            current += timedelta(minutes=slot_duration)
        
        return available
    
    def get_appointments(
        self,
        doctor_id: Optional[str] = None,
        patient_id: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        status: Optional[AppointmentStatus] = None
    ) -> List[Appointment]:
        """Obtiene turnos con filtros."""
        results = []
        
        for apt in self._appointments.values():
            if doctor_id and apt.doctor_id != doctor_id:
                continue
            if patient_id and apt.patient_id != patient_id:
                continue
            if date_from and apt.date < date_from:
                continue
            if date_to and apt.date > date_to:
                continue
            if status and apt.status != status:
                continue
            
            results.append(apt)
        
        return sorted(results, key=lambda x: (x.date, x.time))
    
    def update_status(self, appointment_id: str, new_status: AppointmentStatus) -> bool:
        """Actualiza estado de un turno."""
        if appointment_id not in self._appointments:
            return False
        
        apt = self._appointments[appointment_id]
        apt.status = new_status
        
        if new_status == AppointmentStatus.CONFIRMED:
            apt.confirmed_at = datetime.now()
        elif new_status == AppointmentStatus.COMPLETED:
            apt.completed_at = datetime.now()
        
        self._save_data()
        
        log_event("scheduler", f"Appointment {appointment_id} status changed to {new_status.value}")
        return True
    
    def cancel_appointment(self, appointment_id: str, reason: Optional[str] = None) -> bool:
        """Cancela un turno."""
        if self.update_status(appointment_id, AppointmentStatus.CANCELLED):
            apt = self._appointments[appointment_id]
            if reason:
                apt.notes = f"Cancelado: {reason}"
            self._save_data()
            return True
        return False
    
    def get_daily_schedule(self, doctor_id: str, schedule_date: date) -> List[Appointment]:
        """Obtiene agenda diaria de un médico."""
        return self.get_appointments(
            doctor_id=doctor_id,
            date_from=schedule_date,
            date_to=schedule_date
        )
    
    def get_statistics(self, date_from: date, date_to: date) -> Dict[str, Any]:
        """Estadísticas de turnos."""
        apts = self.get_appointments(date_from=date_from, date_to=date_to)
        
        total = len(apts)
        by_status = defaultdict(int)
        by_doctor = defaultdict(int)
        by_type = defaultdict(int)
        
        for apt in apts:
            by_status[apt.status.value] += 1
            by_doctor[apt.doctor_name] += 1
            by_type[apt.type.value] += 1
        
        return {
            "total": total,
            "by_status": dict(by_status),
            "by_doctor": dict(by_doctor),
            "by_type": dict(by_type),
            "cancelled_rate": (by_status.get("cancelled", 0) / total * 100) if total > 0 else 0,
            "no_show_rate": (by_status.get("no_show", 0) / total * 100) if total > 0 else 0
        }


def render_appointment_scheduler():
    """Renderiza interfaz de agendamiento."""
    st.title("📅 Agendamiento de Turnos")
    
    scheduler = AppointmentScheduler()
    
    # Tabs
    tabs = st.tabs(["📋 Nuevo Turno", "📅 Agenda Diaria", "📊 Estadísticas"])
    
    with tabs[0]:
        render_new_appointment_form(scheduler)
    
    with tabs[1]:
        render_daily_agenda(scheduler)
    
    with tabs[2]:
        render_appointment_stats(scheduler)


def render_new_appointment_form(scheduler: AppointmentScheduler):
    """Formulario para nuevo turno."""
    st.header("📋 Nuevo Turno")
    
    # Obtener datos
    pacientes = st.session_state.get("pacientes_db", {})
    usuarios = st.session_state.get("usuarios_db", {})
    
    # Filtrar médicos
    medicos = {k: v for k, v in usuarios.items() if v.get("rol") in ["medico", "admin"]}
    
    if not pacientes or not medicos:
        st.warning("⚠️ Debe haber pacientes y médicos registrados para agendar turnos.")
        return
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Seleccionar paciente
        paciente_options = {
            f"{p['apellido']}, {p['nombre']} (DNI: {dni})": dni
            for dni, p in pacientes.items()
        }
        
        paciente_selected = st.selectbox(
            "Paciente *",
            options=list(paciente_options.keys()),
            key="apt_paciente"
        )
        
        paciente_dni = paciente_options[paciente_selected]
        paciente = pacientes[paciente_dni]
    
    with col2:
        # Seleccionar médico
        medico_options = {
            f"Dr/Dra. {u.get('nombre', '')} ({k})": k
            for k, u in medicos.items()
        }
        
        medico_selected = st.selectbox(
            "Médico *",
            options=list(medico_options.keys()),
            key="apt_medico"
        )
        
        medico_id = medico_options[medico_selected]
        medico = medicos[medico_id]
    
    col3, col4, col5 = st.columns(3)
    
    with col3:
        fecha = st.date_input("Fecha *", min_value=date.today(), value=date.today())
    
    with col4:
        # Horarios disponibles
        available_slots = scheduler.get_available_slots(
            doctor_id=medico_id,
            check_date=fecha
        )
        
        if available_slots:
            hora = st.selectbox(
                "Hora *",
                options=[h.strftime("%H:%M") for h in available_slots],
                key="apt_hora"
            )
        else:
            st.error("❌ No hay horarios disponibles para esta fecha")
            hora = None
    
    with col5:
        tipo = st.selectbox(
            "Tipo de Turno",
            options=[
                ("Consulta", AppointmentType.CONSULTATION),
                ("Seguimiento", AppointmentType.FOLLOW_UP),
                ("Procedimiento", AppointmentType.PROCEDURE)
            ],
            format_func=lambda x: x[0]
        )
    
    motivo = st.text_area("Motivo de la consulta *")
    
    notas = st.text_area("Notas internas (opcional)")
    
    if st.button("📅 Agendar Turno", width='stretch', type="primary"):
        if not hora:
            st.error("❌ Seleccione un horario disponible")
            return
        
        if not motivo:
            st.error("❌ Ingrese el motivo de la consulta")
            return
        
        # Parsear hora
        hora_parts = hora.split(":")
        appointment_time = time(int(hora_parts[0]), int(hora_parts[1]))
        
        scheduler.create_appointment(
            patient_id=paciente.get("id", paciente_dni),
            patient_name=f"{paciente['nombre']} {paciente['apellido']}",
            doctor_id=medico_id,
            doctor_name=medico.get("nombre", medico_id),
            appointment_date=fecha,
            appointment_time=appointment_time,
            reason=motivo,
            appointment_type=tipo[1],
            notes=notas
        )
        
        st.rerun()


def render_daily_agenda(scheduler: AppointmentScheduler):
    """Renderiza agenda diaria."""
    st.header("📅 Agenda Diaria")
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        fecha = st.date_input("Fecha", value=date.today(), key="agenda_fecha")
        
        # Filtrar por médico
        usuarios = st.session_state.get("usuarios_db", {})
        medicos = {k: v for k, v in usuarios.items() if v.get("rol") in ["medico", "admin"]}
        
        medico_filtro = st.selectbox(
            "Filtrar por médico",
            options=["Todos"] + [f"Dr/Dra. {u.get('nombre', '')}" for u in medicos.values()],
            key="agenda_medico"
        )
    
    with col2:
        # Obtener turnos del día
        if medico_filtro == "Todos":
            turnos = scheduler.get_appointments(date_from=fecha, date_to=fecha)
        else:
            # Buscar ID del médico
            medico_id = None
            for k, v in medicos.items():
                if f"Dr/Dra. {v.get('nombre', '')}" == medico_filtro:
                    medico_id = k
                    break
            turnos = scheduler.get_appointments(doctor_id=medico_id, date_from=fecha, date_to=fecha)
        
        if not turnos:
            st.info("📭 No hay turnos agendados para esta fecha")
        else:
            # Mostrar turnos
            status_colors = {
                AppointmentStatus.SCHEDULED: "🔵",
                AppointmentStatus.CONFIRMED: "✅",
                AppointmentStatus.IN_PROGRESS: "🟡",
                AppointmentStatus.COMPLETED: "✔️",
                AppointmentStatus.CANCELLED: "❌",
                AppointmentStatus.NO_SHOW: "⚠️"
            }
            
            for turno in turnos:
                with st.container():
                    col_a, col_b, col_c = st.columns([1, 4, 2])
                    
                    with col_a:
                        st.markdown(f"### {turno.time.strftime('%H:%M')}")
                        st.caption(f"{turno.duration_minutes} min")
                    
                    with col_b:
                        icon = status_colors.get(turno.status, "⚪")
                        st.markdown(f"**{icon} {turno.patient_name}**")
                        st.caption(f"Dr. {turno.doctor_name} | {turno.reason[:50]}...")
                    
                    with col_c:
                        if turno.status == AppointmentStatus.SCHEDULED:
                            if st.button("✅ Confirmar", key=f"conf_{turno.id}"):
                                scheduler.update_status(turno.id, AppointmentStatus.CONFIRMED)
                                st.rerun()
                        
                        if turno.status in [AppointmentStatus.SCHEDULED, AppointmentStatus.CONFIRMED]:
                            if st.button("❌ Cancelar", key=f"canc_{turno.id}"):
                                motivo_cancel = st.text_input("Motivo", key=f"mot_{turno.id}")
                                if st.button("Confirmar Cancelación", key=f"cf_{turno.id}"):
                                    scheduler.cancel_appointment(turno.id, motivo_cancel)
                                    st.rerun()
                    
                    st.divider()


def render_appointment_stats(scheduler: AppointmentScheduler):
    """Estadísticas de turnos."""
    st.header("📊 Estadísticas de Turnos")
    
    col1, col2 = st.columns(2)
    
    with col1:
        fecha_desde = st.date_input("Desde", value=date.today() - timedelta(days=30))
    
    with col2:
        fecha_hasta = st.date_input("Hasta", value=date.today())
    
    stats = scheduler.get_statistics(fecha_desde, fecha_hasta)
    
    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Turnos", stats["total"])
    
    with col2:
        completados = stats["by_status"].get("completed", 0)
        st.metric("Completados", completados)
    
    with col3:
        st.metric("Tasa Cancelación", f"{stats['cancelled_rate']:.1f}%")
    
    with col4:
        st.metric("No Asistió", f"{stats['no_show_rate']:.1f}%")
    
    # Desglose
    if stats["by_doctor"]:
        st.subheader("Por Médico")
        data = [{"Médico": k, "Turnos": v} for k, v in sorted(stats["by_doctor"].items(), key=lambda x: x[1], reverse=True)]
        df = pd.DataFrame(data)
        st.bar_chart(df.set_index("Médico"))


# Helper para obtener scheduler
def get_scheduler() -> AppointmentScheduler:
    """Obtiene instancia del scheduler."""
    return AppointmentScheduler()
