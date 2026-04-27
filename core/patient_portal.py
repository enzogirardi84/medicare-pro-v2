"""
Portal del Paciente para Medicare Pro.

Permite a pacientes:
- Ver su historia clínica resumida
- Descargar estudios y recetas
- Agendar turnos online
- Ver próximos turnos
- Comunicarse con el médico
- Actualizar datos personales
"""

from __future__ import annotations

import streamlit as st
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum, auto

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType
from core.document_manager import get_document_manager, DocumentType
from core.appointment_scheduler import get_scheduler, AppointmentStatus


class PortalAccessLevel(Enum):
    """Niveles de acceso al portal."""
    BASIC = auto()      # Solo ver turnos y descargar recetas
    STANDARD = auto()   # Ver historia, estudios
    FULL = auto()       # Todo + mensajería con médico


@dataclass
class PortalSession:
    """Sesión de portal de paciente."""
    patient_id: str
    patient_name: str
    access_level: PortalAccessLevel
    login_time: datetime
    last_activity: datetime
    ip_address: Optional[str] = None


class PatientPortal:
    """
    Portal de acceso para pacientes.
    
    NOTA: Este es un módulo para futura implementación.
    Requiere:
    - Autenticación de pacientes
    - Sistema de mensajería
    - Notificaciones push
    """
    
    def __init__(self):
        self._sessions: Dict[str, PortalSession] = {}
    
    def authenticate_patient(self, patient_dni: str, password: str) -> Optional[PortalSession]:
        """
        Autentica un paciente para acceder al portal.
        
        En producción:
        - Verificar DNI + contraseña
        - Enviar 2FA si es primer login
        - Registrar intentos fallidos
        """
        pacientes = st.session_state.get("pacientes_db", {})
        
        if patient_dni not in pacientes:
            return None
        
        paciente = pacientes[patient_dni]
        
        # Verificar si tiene acceso habilitado
        if not paciente.get("portal_enabled", False):
            st.error("🔒 Acceso al portal no habilitado. Contacte a recepción.")
            return None
        
        # Crear sesión
        session = PortalSession(
            patient_id=paciente.get("id", patient_dni),
            patient_name=f"{paciente['nombre']} {paciente['apellido']}",
            access_level=PortalAccessLevel.STANDARD,
            login_time=datetime.now(),
            last_activity=datetime.now()
        )
        
        self._sessions[paciente.get("id", patient_dni)] = session
        
        audit_log(
            AuditEventType.LOGIN_SUCCESS,
            resource_type="patient_portal",
            resource_id=patient_dni,
            action="LOGIN",
            description=f"Patient {session.patient_name} logged into portal"
        )
        
        return session
    
    def render_portal_landing(self):
        """Renderiza página de login del portal."""
        st.title("🏥 Portal del Paciente")
        st.subheader("Acceda a su información médica de forma segura")
        
        col1, col2, col3 = st.columns([1, 2, 1])
        
        with col2:
            st.markdown("### 🔐 Iniciar Sesión")
            
            dni = st.text_input("DNI", placeholder="Ingrese su DNI sin puntos")
            password = st.text_input("Contraseña", type="password")
            
            if st.button("Ingresar", use_container_width=True, type="primary"):
                session = self.authenticate_patient(dni, password)

                if session:
                    st.session_state["portal_session"] = session
                else:
                    st.error("❌ DNI o contraseña incorrectos")
            
            st.divider()
            
            st.caption("¿No tiene acceso? Contacte a la recepción de la clínica para habilitar su cuenta.")
            st.caption("¿Olvidó su contraseña? Haga clic en 'Recuperar contraseña'")
    
    def render_patient_dashboard(self):
        """Renderiza dashboard del paciente."""
        session = st.session_state.get("portal_session")
        
        if not session:
            self.render_portal_landing()
            return
        
        # Header
        col1, col2, col3 = st.columns([1, 3, 1])
        
        with col1:
            st.markdown("### 🏥 Medicare Pro")
        
        with col2:
            st.markdown(f"## 👤 Bienvenido/a, {session.patient_name}")
        
        with col3:
            if st.button("🚪 Cerrar Sesión"):
                del st.session_state["portal_session"]
        
        st.divider()
        
        # Menú lateral
        menu = st.sidebar.radio(
            "Menú",
            options=[
                "📋 Mis Turnos",
                "📄 Mis Documentos",
                "💊 Mis Recetas",
                "📊 Mis Estudios",
                "👤 Mis Datos",
                "💬 Mensajes"
            ]
        )
        
        if menu == "📋 Mis Turnos":
            self._render_my_appointments(session)
        elif menu == "📄 Mis Documentos":
            self._render_my_documents(session)
        elif menu == "💊 Mis Recetas":
            self._render_my_prescriptions(session)
        elif menu == "📊 Mis Estudios":
            self._render_my_studies(session)
        elif menu == "👤 Mis Datos":
            self._render_my_profile(session)
        elif menu == "💬 Mensajes":
            self._render_messages(session)
    
    def _render_my_appointments(self, session: PortalSession):
        """Renderiza turnos del paciente."""
        st.header("📋 Mis Próximos Turnos")
        
        scheduler = get_scheduler()
        turnos = scheduler.get_appointments(patient_id=session.patient_id)
        
        # Filtrar futuros
        turnos_futuros = [t for t in turnos if t.date >= date.today()]
        
        if not turnos_futuros:
            st.info("📭 No tiene turnos agendados")
            
            st.divider()
            st.subheader("📅 Agendar Nuevo Turno")
            st.info("Para agendar un turno, contacte a recepción al (011) 5555-1234")
        else:
            for turno in turnos_futuros:
                with st.container():
                    col1, col2 = st.columns([1, 3])
                    
                    with col1:
                        st.markdown(f"### {turno.time.strftime('%H:%M')}")
                        st.caption(f"{turno.date.strftime('%d/%m/%Y')}")
                    
                    with col2:
                        status_icons = {
                            AppointmentStatus.SCHEDULED: "🔵",
                            AppointmentStatus.CONFIRMED: "✅",
                            AppointmentStatus.IN_PROGRESS: "🟡"
                        }
                        icon = status_icons.get(turno.status, "⚪")
                        
                        st.markdown(f"**{icon} Turno con Dr. {turno.doctor_name}**")
                        st.caption(f"Motivo: {turno.reason}")
                        st.caption(f"Estado: {turno.status.value}")
                        
                        if turno.status == AppointmentStatus.SCHEDULED:
                            if st.button("✅ Confirmar asistencia", key=f"conf_{turno.id}"):
                                scheduler.update_status(turno.id, AppointmentStatus.CONFIRMED)
                                st.success("✅ Turno confirmado")
                
                st.divider()
        
        # Historial
        with st.expander("📜 Historial de Turnos"):
            turnos_pasados = [t for t in turnos if t.date < date.today()]
            
            if turnos_pasados:
                for turno in turnos_pasados[:10]:
                    st.markdown(f"**{turno.date.strftime('%d/%m/%Y')}** - Dr. {turno.doctor_name} - {turno.status.value}")
            else:
                st.caption("No hay turnos anteriores")
    
    def _render_my_documents(self, session: PortalSession):
        """Renderiza documentos del paciente."""
        st.header("📄 Mis Documentos")
        
        doc_manager = get_document_manager()
        documentos = doc_manager.get_patient_documents(session.patient_id)
        
        if not documentos:
            st.info("📭 No tiene documentos adjuntos")
        else:
            for doc in documentos:
                with st.container():
                    col1, col2, col3 = st.columns([1, 3, 1])
                    
                    with col1:
                        if doc.thumbnail_base64:
                            st.image(f"data:image/png;base64,{doc.thumbnail_base64}", width=100)
                        else:
                            st.markdown("📄")
                    
                    with col2:
                        st.markdown(f"**{doc.original_filename}**")
                        st.caption(f"Tipo: {doc.document_type.name}")
                        st.caption(f"Fecha: {doc.upload_date.strftime('%d/%m/%Y')}")
                        if doc.description:
                            st.caption(f"Notas: {doc.description}")
                    
                    with col3:
                        content = doc_manager.get_document_content(doc.id)
                        if content:
                            st.download_button(
                                "⬇️ Descargar",
                                content,
                                file_name=doc.original_filename,
                                mime=doc.mime_type,
                                key=f"dl_{doc.id}"
                            )
                
                st.divider()
    
    def _render_my_prescriptions(self, session: PortalSession):
        """Renderiza recetas del paciente."""
        st.header("💊 Mis Recetas")
        
        recetas = st.session_state.get("recetas_db", [])
        recetas_paciente = [r for r in recetas if r.get("paciente_id") == session.patient_id]
        
        if not recetas_paciente:
            st.info("📭 No tiene recetas registradas")
        else:
            for receta in sorted(recetas_paciente, key=lambda x: x.get("fecha", ""), reverse=True):
                with st.container():
                    st.markdown(f"**📋 Receta - {receta.get('fecha', 'Sin fecha')}**")
                    
                    medicamentos = receta.get("medicamentos", [])
                    for med in medicamentos:
                        st.markdown(f"- **{med.get('nombre', 'Desconocido')}**")
                        st.caption(f"  {med.get('dosis', '')} - {med.get('frecuencia', '')}")
                    
                    if receta.get("observaciones"):
                        st.caption(f"Notas: {receta['observaciones']}")
                    
                    # Verificar vigencia
                    vigencia = receta.get("vigencia_dias", 30)
                    fecha_receta = datetime.strptime(receta.get("fecha", datetime.now().strftime("%d/%m/%Y")), "%d/%m/%Y")
                    dias_transcurridos = (datetime.now() - fecha_receta).days
                    
                    if dias_transcurridos > vigencia:
                        st.error("⚠️ Esta receta ha vencido")
                    else:
                        dias_restantes = vigencia - dias_transcurridos
                        st.success(f"✅ Válida por {dias_restantes} días más")
                
                st.divider()
    
    def _render_my_studies(self, session: PortalSession):
        """Renderiza estudios del paciente."""
        st.header("📊 Mis Estudios y Laboratorios")
        
        # Buscar documentos de tipo estudio
        doc_manager = get_document_manager()
        estudios = doc_manager.get_patient_documents(
            session.patient_id,
            doc_type=DocumentType.STUDY_RESULT
        )
        
        # También buscar en estudios_db
        estudios_db = st.session_state.get("estudios_db", [])
        estudios_paciente = [e for e in estudios_db if e.get("paciente_id") == session.patient_id]
        
        if not estudios and not estudios_paciente:
            st.info("📭 No tiene estudios registrados")
        else:
            # Mostrar estudios con documentos
            for estudio in estudios:
                with st.container():
                    st.markdown(f"**📁 {estudio.original_filename}**")
                    st.caption(f"Subido: {estudio.upload_date.strftime('%d/%m/%Y')}")
                    
                    content = doc_manager.get_document_content(estudio.id)
                    if content:
                        st.download_button(
                            "⬇️ Descargar Resultado",
                            content,
                            file_name=estudio.original_filename,
                            mime=estudio.mime_type
                        )
                
                st.divider()
    
    def _render_my_profile(self, session: PortalSession):
        """Renderiza perfil del paciente."""
        st.header("👤 Mis Datos Personales")
        
        pacientes = st.session_state.get("pacientes_db", {})
        paciente = None
        
        # Buscar paciente por ID
        for dni, p in pacientes.items():
            if p.get("id") == session.patient_id:
                paciente = p
                break
        
        if not paciente:
            st.error("❌ No se encontraron datos del paciente")
            return
        
        # Mostrar datos (solo lectura en portal)
        col1, col2 = st.columns(2)
        
        with col1:
            st.text_input("Nombre", value=paciente.get("nombre", ""), disabled=True)
            st.text_input("Apellido", value=paciente.get("apellido", ""), disabled=True)
            st.text_input("DNI", value=paciente.get("dni", ""), disabled=True)
            st.date_input("Fecha de Nacimiento", 
                         value=datetime.strptime(paciente.get("fecha_nacimiento", "01/01/1900"), "%d/%m/%Y").date() 
                         if paciente.get("fecha_nacimiento") else None, 
                         disabled=True)
        
        with col2:
            st.text_input("Teléfono", value=paciente.get("telefono", ""), disabled=True)
            st.text_input("Email", value=paciente.get("email", ""), disabled=True)
            st.text_input("Obra Social", value=paciente.get("obra_social", ""), disabled=True)
            st.text_input("N° Afiliado", value=paciente.get("numero_afiliado", ""), disabled=True)
        
        st.info("ℹ️ Para actualizar sus datos, contacte a recepción.")
        
        # Cambiar contraseña
        st.divider()
        st.subheader("🔐 Seguridad")
        
        with st.expander("Cambiar contraseña"):
            st.text_input("Contraseña actual", type="password")
            st.text_input("Nueva contraseña", type="password")
            st.text_input("Confirmar nueva contraseña", type="password")
            
            if st.button("Actualizar contraseña"):
                st.info("Función en desarrollo")
    
    def _render_messages(self, session: PortalSession):
        """Renderiza sistema de mensajes."""
        st.header("💬 Mensajes con mi Médico")
        
        st.info("🚧 Sistema de mensajería segura en desarrollo.")
        st.caption("Esta función permitirá comunicarse de forma segura con su médico tratante.")
        
        st.divider()
        
        st.subheader("📞 Contacto de Emergencia")
        st.markdown("""
        **Para consultas médicas urgentes:**
        - 📞 Línea directa: (011) 5555-1234
        - 🕐 Horario: 24hs para emergencias
        - 📧 Email: urgencias@medicare.local
        """)


# Singleton
_patient_portal: Optional[PatientPortal] = None


def get_patient_portal() -> PatientPortal:
    """Obtiene instancia del portal."""
    global _patient_portal
    if _patient_portal is None:
        _patient_portal = PatientPortal()
    return _patient_portal
