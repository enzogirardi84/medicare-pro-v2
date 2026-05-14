"""
Sistema de Telemedicina y Consultas Virtuales para Medicare Pro.

Características:
- Programación de consultas virtuales
- Sala de espera digital
- Notas de consulta virtual
- Integración con video (WebRTC placeholder)
- Historial de consultas virtuales
- Prescripción digital durante consulta
"""

from __future__ import annotations

import streamlit as st
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import uuid

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType
from core.appointment_scheduler import get_scheduler, AppointmentType, AppointmentStatus


class TelemedicineStatus(Enum):
    """Estados de una consulta virtual."""
    SCHEDULED = "scheduled"      # Agendada
    WAITING_ROOM = "waiting"     # En sala de espera
    IN_PROGRESS = "in_progress"  # En consulta
    COMPLETED = "completed"      # Finalizada
    CANCELLED = "cancelled"      # Cancelada
    NO_SHOW = "no_show"          # Paciente no ingresó


@dataclass
class VirtualConsultation:
    """Consulta virtual/telemedicina."""
    id: str
    appointment_id: str  # ID del turno asociado
    patient_id: str
    patient_name: str
    doctor_id: str
    doctor_name: str
    
    scheduled_time: datetime
    duration_minutes: int = 30
    
    status: TelemedicineStatus = TelemedicineStatus.SCHEDULED
    
    # Sala de espera
    patient_joined_at: Optional[datetime] = None
    doctor_joined_at: Optional[datetime] = None
    
    # Consulta
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    
    # Datos clínicos
    chat_history: List[Dict[str, Any]] = None
    clinical_notes: Optional[str] = None
    diagnosis: Optional[str] = None
    prescription: Optional[List[Dict]] = None
    
    # Técnico
    video_room_url: Optional[str] = None
    video_provider: str = "webrtc"  # webrtc, zoom, meet, etc.
    
    def __post_init__(self):
        if self.chat_history is None:
            self.chat_history = []


class TelemedicineManager:
    """
    Manager de consultas virtuales.
    
    Gestiona:
    - Programación de consultas virtuales
    - Salas de espera digitales
    - Integración con sistemas de video
    - Historial clínico de consultas
    """
    
    def __init__(self):
        self._consultations: Dict[str, VirtualConsultation] = {}
        self._load_consultations()
    
    def _load_consultations(self):
        """Carga consultas desde session_state."""
        if "telemedicine_consultations" in st.session_state:
            try:
                data = st.session_state["telemedicine_consultations"]
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict):
                            self._consultations[k] = self._dict_to_consultation(v)
            except Exception as e:
                log_event("telemedicine", f"Error loading consultations: {e}")
    
    def _save_consultations(self):
        """Guarda consultas a session_state."""
        data = {k: asdict(v) for k, v in self._consultations.items()}
        # Convertir enums a strings
        for v in data.values():
            v["status"] = v["status"].value if isinstance(v["status"], TelemedicineStatus) else v["status"]
        st.session_state["telemedicine_consultations"] = data
    
    def _dict_to_consultation(self, data: dict) -> VirtualConsultation:
        """Convierte dict a VirtualConsultation."""
        return VirtualConsultation(
            id=data["id"],
            appointment_id=data["appointment_id"],
            patient_id=data["patient_id"],
            patient_name=data["patient_name"],
            doctor_id=data["doctor_id"],
            doctor_name=data["doctor_name"],
            scheduled_time=datetime.fromisoformat(data["scheduled_time"]),
            duration_minutes=data.get("duration_minutes", 30),
            status=TelemedicineStatus(data.get("status", "scheduled")),
            patient_joined_at=datetime.fromisoformat(data["patient_joined_at"]) if data.get("patient_joined_at") else None,
            doctor_joined_at=datetime.fromisoformat(data["doctor_joined_at"]) if data.get("doctor_joined_at") else None,
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            chat_history=data.get("chat_history", []),
            clinical_notes=data.get("clinical_notes"),
            diagnosis=data.get("diagnosis"),
            prescription=data.get("prescription"),
            video_room_url=data.get("video_room_url"),
            video_provider=data.get("video_provider", "webrtc")
        )
    
    def schedule_virtual_consultation(
        self,
        patient_id: str,
        patient_name: str,
        doctor_id: str,
        doctor_name: str,
        scheduled_time: datetime,
        duration_minutes: int = 30
    ) -> Optional[VirtualConsultation]:
        """Agenda una nueva consulta virtual."""
        
        # Crear turno en el scheduler
        scheduler = get_scheduler()
        from core.appointment_scheduler import Appointment
        
        appointment = scheduler.create_appointment(
            patient_id=patient_id,
            patient_name=patient_name,
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            appointment_date=scheduled_time.date(),
            appointment_time=scheduled_time.time(),
            reason="Consulta Virtual",
            appointment_type=AppointmentType.CONSULTATION,
            duration=duration_minutes
        )
        
        if not appointment:
            return None
        
        # Crear consulta virtual
        consultation = VirtualConsultation(
            id=str(uuid.uuid4()),
            appointment_id=appointment.id,
            patient_id=patient_id,
            patient_name=patient_name,
            doctor_id=doctor_id,
            doctor_name=doctor_name,
            scheduled_time=scheduled_time,
            duration_minutes=duration_minutes,
            status=TelemedicineStatus.SCHEDULED,
            video_room_url=self._generate_video_room_url()
        )
        
        self._consultations[consultation.id] = consultation
        self._save_consultations()
        
        # Audit log
        audit_log(
            AuditEventType.DATA_EXPORT,
            resource_type="telemedicine",
            resource_id=consultation.id,
            action="CREATE",
            description=f"Virtual consultation scheduled: {patient_name} with Dr. {doctor_name}"
        )
        
        log_event("telemedicine", f"Consultation scheduled: {consultation.id}")
        
        return consultation
    
    def _generate_video_room_url(self) -> str:
        """Genera URL única para sala de video."""
        # En producción: integrar con Twilio, Daily.co, o Zoom
        room_id = str(uuid.uuid4())[:12]
        return f"https://meet.medicare.local/room/{room_id}"
    
    def patient_join_waiting_room(self, consultation_id: str) -> bool:
        """Paciente ingresa a sala de espera."""
        if consultation_id not in self._consultations:
            return False
        
        consultation = self._consultations[consultation_id]
        consultation.patient_joined_at = datetime.now()
        consultation.status = TelemedicineStatus.WAITING_ROOM
        
        self._save_consultations()
        
        # Notificar al médico (en producción: push notification)
        log_event("telemedicine", f"Patient {consultation.patient_name} joined waiting room")
        
        return True
    
    def doctor_join_consultation(self, consultation_id: str) -> bool:
        """Médico inicia la consulta."""
        if consultation_id not in self._consultations:
            return False
        
        consultation = self._consultations[consultation_id]
        consultation.doctor_joined_at = datetime.now()
        consultation.started_at = datetime.now()
        consultation.status = TelemedicineStatus.IN_PROGRESS
        
        self._save_consultations()
        
        # Actualizar turno en scheduler
        scheduler = get_scheduler()
        scheduler.update_status(consultation.appointment_id, AppointmentStatus.IN_PROGRESS)
        
        return True
    
    def end_consultation(
        self,
        consultation_id: str,
        clinical_notes: Optional[str] = None,
        diagnosis: Optional[str] = None,
        prescription: Optional[List[Dict]] = None
    ) -> bool:
        """Finaliza la consulta virtual."""
        if consultation_id not in self._consultations:
            return False
        
        consultation = self._consultations[consultation_id]
        consultation.ended_at = datetime.now()
        consultation.status = TelemedicineStatus.COMPLETED
        consultation.clinical_notes = clinical_notes
        consultation.diagnosis = diagnosis
        consultation.prescription = prescription
        
        self._save_consultations()
        
        # Actualizar turno
        scheduler = get_scheduler()
        scheduler.update_status(consultation.appointment_id, AppointmentStatus.COMPLETED)
        
        # Crear evolución automáticamente
        self._create_evolution_from_consultation(consultation)
        
        log_event("telemedicine", f"Consultation completed: {consultation_id}")
        
        return True
    
    def _on_send_message(self, consultation_id: str, input_key: str):
        """Callback: enviar mensaje de chat."""
        message = st.session_state.get(input_key, "")
        if message:
            try:
                self.add_chat_message(consultation_id, "doctor", message)
            except Exception as e:
                log_event("telemedicine", f"Error al enviar mensaje: {e}")
                st.error("No se pudo enviar el mensaje.")

    def _create_evolution_from_consultation(self, consultation: VirtualConsultation):
        """Crea registro de evolución desde consulta virtual."""
        evolucion = {
            "id": str(uuid.uuid4()),
            "paciente_id": consultation.patient_id,
            "paciente_nombre": consultation.patient_name,
            "medico_id": consultation.doctor_id,
            "medico_nombre": consultation.doctor_name,
            "fecha": datetime.now().strftime("%d/%m/%Y"),
            "hora": datetime.now().strftime("%H:%M"),
            "nota": f"[CONSULTA VIRTUAL]\n\n{consultation.clinical_notes or 'Sin notas'}",
            "diagnostico": consultation.diagnosis,
            "tipo": "virtual"
        }
        
        # Agregar a evoluciones_db
        evoluciones_db = st.session_state.get("evoluciones_db", [])
        evoluciones_db.append(evolucion)
        st.session_state["evoluciones_db"] = evoluciones_db
    
    def add_chat_message(self, consultation_id: str, sender: str, message: str) -> bool:
        """Agrega mensaje al chat de la consulta."""
        if consultation_id not in self._consultations:
            return False
        
        consultation = self._consultations[consultation_id]
        consultation.chat_history.append({
            "timestamp": datetime.now().isoformat(),
            "sender": sender,
            "message": message
        })
        
        self._save_consultations()
        return True
    
    def get_consultation(self, consultation_id: str) -> Optional[VirtualConsultation]:
        """Obtiene consulta por ID."""
        return self._consultations.get(consultation_id)
    
    def get_patient_consultations(self, patient_id: str) -> List[VirtualConsultation]:
        """Obtiene historial de consultas virtuales del paciente."""
        return [
            c for c in self._consultations.values()
            if c.patient_id == patient_id
        ]
    
    def get_doctor_consultations(self, doctor_id: str, date_filter: Optional[datetime] = None) -> List[VirtualConsultation]:
        """Obtiene consultas virtuales del médico."""
        consultations = [c for c in self._consultations.values() if c.doctor_id == doctor_id]
        
        if date_filter:
            consultations = [
                c for c in consultations
                if c.scheduled_time.date() == date_filter.date()
            ]
        
        return sorted(consultations, key=lambda x: x.scheduled_time)
    
    def get_waiting_room(self, doctor_id: Optional[str] = None) -> List[VirtualConsultation]:
        """Obtiene pacientes en sala de espera."""
        waiting = [
            c for c in self._consultations.values()
            if c.status == TelemedicineStatus.WAITING_ROOM
        ]
        
        if doctor_id:
            waiting = [c for c in waiting if c.doctor_id == doctor_id]
        
        return sorted(waiting, key=lambda x: x.patient_joined_at or datetime.min)
    
    def render_telemedicine_dashboard(self):
        """Renderiza dashboard de telemedicina."""
        st.title("🖥️ Telemedicina - Consultas Virtuales")
        
        user = st.session_state.get("u_actual", {})
        user_role = user.get("rol", "")
        user_id = user.get("usuario_login", "")
        
        # Tabs según rol
        if user_role in ["medico", "admin", "superadmin"]:
            tabs = st.tabs(["📅 Mis Consultas", "⏳ Sala de Espera", "➕ Nueva Consulta", "📊 Historial"])
        else:
            tabs = st.tabs(["📅 Mis Turnos Virtuales", "📊 Historial"])
        
        with tabs[0]:
            if user_role in ["medico", "admin", "superadmin"]:
                self._render_doctor_consultations(user_id)
            else:
                self._render_patient_virtual_appointments(user.get("id", ""))
        
        if user_role in ["medico", "admin", "superadmin"]:
            with tabs[1]:
                self._render_waiting_room(user_id)
            
            with tabs[2]:
                self._render_schedule_virtual_consultation()
        
        with tabs[-1]:
            self._render_consultation_history()
    
    def _on_start_consultation(self, consultation_id: str):
        """Callback: iniciar consulta desde lista."""
        try:
            self.doctor_join_consultation(consultation_id)
        except Exception as e:
            log_event("telemedicine", f"Error al iniciar consulta {consultation_id}: {e}")
            st.error("No se pudo iniciar la consulta.")

    def _render_doctor_consultations(self, doctor_id: str):
        """Renderiza consultas del médico."""
        st.header("📅 Mis Consultas Virtuales de Hoy")

        consultations = self.get_doctor_consultations(doctor_id, datetime.now())

        if not consultations:
            st.info("📭 No tiene consultas virtuales programadas para hoy")
        else:
            for consultation in consultations:
                with st.container():
                    col1, col2, col3 = st.columns([2, 3, 2])

                    with col1:
                        st.markdown(f"**{consultation.scheduled_time.strftime('%H:%M')}**")
                        st.caption(f"{consultation.duration_minutes} min")

                    with col2:
                        status_icons = {
                            TelemedicineStatus.SCHEDULED: "🔵",
                            TelemedicineStatus.WAITING_ROOM: "⏳",
                            TelemedicineStatus.IN_PROGRESS: "🟢",
                            TelemedicineStatus.COMPLETED: "✅"
                        }
                        icon = status_icons.get(consultation.status, "⚪")

                        st.markdown(f"**{icon} {consultation.patient_name}**")
                        st.caption(f"Estado: {consultation.status.value}")

                        if consultation.patient_joined_at:
                            st.caption(f"🟢 En sala de espera desde {consultation.patient_joined_at.strftime('%H:%M')}")

                    with col3:
                        if consultation.status == TelemedicineStatus.WAITING_ROOM:
                            st.button("▶️ Iniciar Consulta", key=f"start_{consultation.id}", width='stretch', on_click=self._on_start_consultation, args=(consultation.id,))

                        elif consultation.status == TelemedicineStatus.IN_PROGRESS:
                            if st.button("🚪 Ingresar a Sala", key=f"join_{consultation.id}", width='stretch', type="primary"):
                                self._render_virtual_room(consultation)

                        elif consultation.status == TelemedicineStatus.SCHEDULED:
                            st.caption("Esperando paciente...")

                st.divider()
    
    def _on_attend(self, consultation_id: str):
        """Callback: atender paciente en sala de espera."""
        try:
            self.doctor_join_consultation(consultation_id)
        except Exception as e:
            log_event("telemedicine", f"Error al atender consulta {consultation_id}: {e}")
            st.error("No se pudo atender al paciente.")

    def _render_waiting_room(self, doctor_id: str):
        """Renderiza sala de espera digital."""
        st.header("⏳ Sala de Espera Digital")

        waiting = self.get_waiting_room(doctor_id)

        if not waiting:
            st.info("📭 No hay pacientes en sala de espera")

            # Simulación de sala vacía
            st.markdown(
                '<div class="mc-waiting-empty"><h3>🪑 Sala de Espera Vacía</h3><p>Los pacientes aparecerán aquí cuando se conecten a sus consultas virtuales</p></div>',
                unsafe_allow_html=True,
            )
        else:
            st.success(f"🟢 {len(waiting)} paciente(s) esperando")

            for consultation in waiting:
                with st.container():
                    col1, col2 = st.columns([3, 1])

                    with col1:
                        st.markdown(f"**👤 {consultation.patient_name}**")
                        st.caption(f"Consulta: {consultation.scheduled_time.strftime('%H:%M')}")
                        st.caption(f"Esperando desde: {consultation.patient_joined_at.strftime('%H:%M:%S')}")

                        wait_time = datetime.now() - consultation.patient_joined_at
                        st.caption(f"⏱️ Tiempo de espera: {int(wait_time.total_seconds() / 60)} minutos")

                    with col2:
                        st.button("▶️ Atender", key=f"attend_{consultation.id}", width='stretch', type="primary", on_click=self._on_attend, args=(consultation.id,))

                st.divider()
    
    def _render_virtual_room(self, consultation: VirtualConsultation):
        """Renderiza sala de consulta virtual."""
        st.title(f"🖥️ Consulta Virtual - {consultation.patient_name}")
        
        # Layout de videollamada simulado
        col_video, col_chat = st.columns([2, 1])
        
        with col_video:
            st.subheader("📹 Video")

            # Placeholder de video
            st.markdown(
                '<div class="mc-video-placeholder"><div class="mc-video-placeholder-inner"><h2>👤</h2><p>Video del Paciente</p><p style="font-size: 12px;">Integración WebRTC/Daily.co</p></div></div>',
                unsafe_allow_html=True,
            )

            # Controles
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.button("🎤 Mic", width='stretch')
            with col2:
                st.button("📹 Video", width='stretch')
            with col3:
                st.button("💻 Compartir", width='stretch')
            with col4:
                if st.button("🔴 Finalizar", width='stretch', type="primary"):
                    self._render_end_consultation_form(consultation)

        with col_chat:
            st.subheader("💬 Chat")

            # Historial de chat
            chat_container = st.container()
            with chat_container:
                for msg in consultation.chat_history:
                    sender = "🧑‍⚕️" if msg["sender"] == "doctor" else "👤"
                    st.markdown(f"**{sender} {msg['sender']}**: {msg['message']}")

            # Input de mensaje
            st.text_input("Mensaje", key=f"chat_{consultation.id}")
            st.button("Enviar", key=f"send_{consultation.id}", on_click=self._on_send_message, args=(consultation.id, f"chat_{consultation.id}"))
    
    def _render_end_consultation_form(self, consultation: VirtualConsultation):
        """Formulario para finalizar consulta."""
        st.subheader("📝 Finalizar Consulta")
        
        with st.form(key=f"end_form_{consultation.id}"):
            notas = st.text_area("Notas Clínicas", height=150)
            diagnostico = st.text_input("Diagnóstico")
            
            st.subheader("💊 Prescripción")
            
            # Formulario simple de prescripción
            col1, col2, col3 = st.columns(3)
            with col1:
                medicamento = st.text_input("Medicamento")
            with col2:
                dosis = st.text_input("Dosis")
            with col3:
                frecuencia = st.text_input("Frecuencia")
            
            submit = st.form_submit_button("✅ Finalizar y Guardar", width='stretch', type="primary")
            
            if submit:
                prescription = []
                if medicamento:
                    prescription.append({
                        "nombre": medicamento,
                        "dosis": dosis,
                        "frecuencia": frecuencia
                    })
                
                self.end_consultation(
                    consultation_id=consultation.id,
                    clinical_notes=notas,
                    diagnosis=diagnostico,
                    prescription=prescription if prescription else None
                )

                st.success("✅ Consulta finalizada y guardada")
    
    def _render_schedule_virtual_consultation(self):
        """Formulario para agendar consulta virtual."""
        st.header("➕ Nueva Consulta Virtual")
        
        # Obtener datos
        pacientes = st.session_state.get("pacientes_db", {})
        usuarios = st.session_state.get("usuarios_db", {})
        medicos = {k: v for k, v in usuarios.items() if v.get("rol") in ["medico", "admin"]}
        
        if not pacientes or not medicos:
            st.warning("⚠️ Deben existir pacientes y médicos registrados")
            return
        
        col1, col2 = st.columns(2)
        
        with col1:
            paciente_options = {f"{p['apellido']}, {p['nombre']}": dni for dni, p in pacientes.items()}
            paciente_selected = st.selectbox("Paciente", options=list(paciente_options.keys()))
            paciente_dni = paciente_options[paciente_selected]
            paciente = pacientes[paciente_dni]
        
        with col2:
            medico_options = {f"Dr. {u.get('nombre', '')}": k for k, u in medicos.items()}
            medico_selected = st.selectbox("Médico", options=list(medico_options.keys()))
            medico_id = medico_options[medico_selected]
            medico = medicos[medico_id]
        
        col3, col4 = st.columns(2)
        
        with col3:
            fecha = st.date_input("Fecha", min_value=datetime.now().date())
        
        with col4:
            hora = st.time_input("Hora", value=datetime.now().time())
        
        duracion = st.slider("Duración (minutos)", 15, 60, 30, step=15)
        
        if st.button("📅 Agendar Consulta Virtual", width='stretch', type="primary"):
            scheduled_time = datetime.combine(fecha, hora)
            
            consultation = self.schedule_virtual_consultation(
                patient_id=paciente.get("id", paciente_dni),
                patient_name=f"{paciente['nombre']} {paciente['apellido']}",
                doctor_id=medico_id,
                doctor_name=medico.get("nombre", medico_id),
                scheduled_time=scheduled_time,
                duration_minutes=duracion
            )
            
            if consultation:
                st.success(f"✅ Consulta virtual agendada")
                st.info(f"🔗 Link de acceso: {consultation.video_room_url}")
    
    def _render_patient_virtual_appointments(self, patient_id: str):
        """Renderiza turnos virtuales del paciente."""
        st.header("📅 Mis Consultas Virtuales")
        
        consultations = self.get_patient_consultations(patient_id)
        
        if not consultations:
            st.info("📭 No tiene consultas virtuales programadas")
        else:
            for consultation in consultations:
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        st.markdown(f"**👨‍⚕️ Dr. {consultation.doctor_name}**")
                        st.caption(f"📅 {consultation.scheduled_time.strftime('%d/%m/%Y %H:%M')}")
                        st.caption(f"⏱️ Duración: {consultation.duration_minutes} minutos")
                        
                        if consultation.status == TelemedicineStatus.SCHEDULED:
                            st.info("⏳ Esperando inicio de la consulta")
                        elif consultation.status == TelemedicineStatus.IN_PROGRESS:
                            st.success("🟢 Consulta en progreso")
                    
                    with col2:
                        if consultation.status == TelemedicineStatus.SCHEDULED:
                            st.button("🚪 Ingresar a Sala", key=f"patient_join_{consultation.id}", width='stretch', type="primary", on_click=self._on_patient_join, args=(consultation.id,))
                        elif consultation.status == TelemedicineStatus.WAITING_ROOM:
                            st.info("✅ En sala de espera")
                        elif consultation.status == TelemedicineStatus.IN_PROGRESS:
                            st.button("📹 Reconectar", key=f"reconnect_{consultation.id}", width='stretch')
                
                st.divider()
    
    def _on_patient_join(self, consultation_id: str):
        """Callback: paciente ingresa a sala de espera."""
        try:
            self.patient_join_waiting_room(consultation_id)
        except Exception as e:
            log_event("telemedicine", f"Error al unirse a sala {consultation_id}: {e}")
            st.error("No se pudo ingresar a la sala de espera.")

    def _render_consultation_history(self):
        """Renderiza historial de consultas."""
        st.header("📊 Historial de Consultas Virtuales")
        
        # Stats
        total = len(self._consultations)
        completadas = len([c for c in self._consultations.values() if c.status == TelemedicineStatus.COMPLETED])
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Consultas", total)
        with col2:
            st.metric("Completadas", completadas)
        with col3:
            rate = (completadas / total * 100) if total > 0 else 0
            st.metric("Tasa de Éxito", f"{rate:.1f}%")
        
        # Lista de consultas completadas
        st.subheader("Consultas Finalizadas Recientemente")
        
        completadas_list = [
            c for c in self._consultations.values()
            if c.status == TelemedicineStatus.COMPLETED
        ]
        
        if not completadas_list:
            st.info("No hay consultas completadas aún")
        else:
            for consultation in sorted(completadas_list, key=lambda x: x.ended_at or datetime.min, reverse=True)[:10]:
                with st.expander(f"{consultation.patient_name} - {consultation.scheduled_time.strftime('%d/%m/%Y')}"):
                    st.markdown(f"**Médico:** Dr. {consultation.doctor_name}")
                    st.markdown(f"**Duración:** {consultation.duration_minutes} min")
                    
                    if consultation.clinical_notes:
                        st.markdown("**Notas:**")
                        st.text(consultation.clinical_notes)
                    
                    if consultation.diagnosis:
                        st.markdown(f"**Diagnóstico:** {consultation.diagnosis}")


# Singleton
_telemedicine_manager: Optional[TelemedicineManager] = None


def get_telemedicine_manager() -> TelemedicineManager:
    """Obtiene instancia del manager de telemedicina."""
    global _telemedicine_manager
    if _telemedicine_manager is None:
        _telemedicine_manager = TelemedicineManager()
    return _telemedicine_manager
