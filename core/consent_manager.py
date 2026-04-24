"""
Sistema de Gestión de Consentimientos Informados para Medicare Pro.

Características:
- Templates digitales de consentimientos
- Firma digital (touch/mouse)
- Versionado de documentos
- Almacenamiento seguro con hash
- Verificación de integridad
- Exportación PDF
"""

from __future__ import annotations

import hashlib
import json
import base64
from dataclasses import dataclass, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional
from enum import Enum, auto
from pathlib import Path

import streamlit as st

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType


class ConsentType(Enum):
    """Tipos de consentimientos."""
    GENERAL = auto()              # Consentimiento general de tratamiento
    PROCEDURE = auto()            # Procedimiento específico
    SURGERY = auto()              # Cirugía
    ANESTHESIA = auto()           # Anestesia
    BLOOD_TRANSFUSION = auto()    # Transfusión sanguínea
    RESEARCH = auto()             # Participación en investigación
    DATA_USE = auto()             # Uso de datos (LGPD/GDPR)
    PHOTO_VIDEO = auto()          # Fotos/videos para documentación
    TELEMEDICINE = auto()         # Telemedicina
    MINORS = auto()               # Tratamiento de menores


class ConsentStatus(Enum):
    """Estados del consentimiento."""
    DRAFT = "draft"               # Borrador
    PENDING = "pending"           # Pendiente de firma
    SIGNED = "signed"             # Firmado
    EXPIRED = "expired"           # Expirado
    REVOKED = "revoked"           # Revocado por el paciente


@dataclass
class ConsentSignature:
    """Datos de firma digital."""
    signer_name: str
    signer_role: str  # paciente, tutor, médico, testigo
    signed_at: datetime
    signature_data: str  # Base64 de la firma (SVG/path)
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    document_hash: Optional[str] = None  # Hash del documento firmado


@dataclass
class ConsentVersion:
    """Versión de un consentimiento."""
    version: str  # Semantic versioning: 1.0.0
    created_at: datetime
    created_by: str
    content: str
    changes: str  # Descripción de cambios


@dataclass
class InformedConsent:
    """Consentimiento informado completo."""
    id: str
    patient_id: str
    patient_name: str
    consent_type: ConsentType
    status: ConsentStatus
    
    # Documento
    template_id: str
    template_version: str
    content: str  # Contenido HTML/texto del consentimiento
    
    # Firmas
    patient_signature: Optional[ConsentSignature] = None
    physician_signature: Optional[ConsentSignature] = None
    witness_signature: Optional[ConsentSignature] = None
    
    # Metadata
    created_at: datetime = None
    expires_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Campos dinámicos del template
    field_values: Dict[str, Any] = None
    
    # Hash de integridad
    content_hash: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.field_values is None:
            self.field_values = {}
    
    def calculate_hash(self) -> str:
        """Calcula hash del contenido para verificación."""
        data = f"{self.content}{self.patient_id}{self.template_version}"
        return hashlib.sha256(data.encode()).hexdigest()
    
    def verify_integrity(self) -> bool:
        """Verifica que el contenido no fue modificado."""
        if not self.content_hash:
            return True  # No se guardó hash
        return self.calculate_hash() == self.content_hash
    
    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            **asdict(self),
            "consent_type": self.consent_type.name,
            "status": self.status.value
        }


class ConsentTemplate:
    """Template de consentimiento."""
    
    TEMPLATES = {
        ConsentType.GENERAL: {
            "title": "Consentimiento General de Tratamiento Médico",
            "content": """
<h2>CONSENTIMIENTO INFORMADO GENERAL</h2>

<p><strong>Paciente:</strong> {patient_name}</p>
<p><strong>Fecha:</strong> {date}</p>

<h3>DECLARACIÓN DEL PACIENTE</h3>

<p>Yo, <strong>{patient_name}</strong>, DNI <strong>{patient_dni}</strong>, declaro que:</p>

<ol>
<li>He sido informado/a sobre la naturaleza de los procedimientos médicos que se me van a realizar.</li>
<li>He tenido la oportunidad de hacer preguntas y mis dudas han sido aclaradas.</li>
<li>Entiendo los riesgos, beneficios y alternativas del tratamiento propuesto.</li>
<li>Autorizo al Dr./Dra. <strong>{physician_name}</strong> a realizar los procedimientos médicos necesarios.</li>
<li>Entiendo que puedo revocar este consentimiento en cualquier momento.</li>
</ol>

<h3>TRATAMIENTO DE DATOS PERSONALES (LGPD/GDPR)</h3>

<p>Autorizo el tratamiento de mis datos personales y clínicos conforme a la política de privacidad.</p>

<h3>DERECHOS DEL PACIENTE</h3>

<p>Se me ha informado sobre mis derechos de:</p>
<ul>
<li>Acceso a mi historia clínica</li>
<li>Rectificación de datos incorrectos</li>
<li>Solicitud de copias de mi documentación</li>
<li>Revocación de este consentimiento</li>
</ul>

<p><strong>Firma del Paciente:</strong> _________________</p>
<p><strong>Firma del Médico:</strong> _________________</p>
<p><strong>Fecha:</strong> {date}</p>
""",
            "required_fields": ["patient_name", "patient_dni", "physician_name"]
        },
        
        ConsentType.PROCEDURE: {
            "title": "Consentimiento para Procedimiento Específico",
            "content": """
<h2>CONSENTIMIENTO PARA PROCEDIMIENTO</h2>

<p><strong>Procedimiento:</strong> {procedure_name}</p>
<p><strong>Paciente:</strong> {patient_name}</p>
<p><strong>Médico:</strong> {physician_name}</p>

<h3>DESCRIPCIÓN DEL PROCEDIMIENTO</h3>
<p>{procedure_description}</p>

<h3>RIESGOS Y COMPLICACIONES</h3>
<p>{procedure_risks}</p>

<h3>BENEFICIOS ESPERADOS</h3>
<p>{procedure_benefits}</p>

<h3>ALTERNATIVAS</h3>
<p>{alternatives}</p>

<h3>DECLARACIÓN</h3>
<p>He leído y entendido la información anterior. Acepto someterme al procedimiento descrito.</p>

<p><strong>Firma del Paciente:</strong> _________________</p>
<p><strong>Firma del Médico:</strong> _________________</p>
""",
            "required_fields": ["procedure_name", "procedure_description", "procedure_risks"]
        },
        
        ConsentType.DATA_USE: {
            "title": "Consentimiento para Uso de Datos (LGPD/GDPR)",
            "content": """
<h2>CONSENTIMIENTO PARA TRATAMIENTO DE DATOS PERSONALES</h2>

<p><strong>Responsable:</strong> Medicare Pro - Sistema de Gestión Clínica</p>

<h3>DATOS QUE SE TRATARÁN</h3>
<ul>
<li>Datos de identificación (nombre, DNI, contacto)</li>
<li>Datos de salud (historia clínica, diagnósticos, tratamientos)</li>
<li>Datos de seguros y cobertura médica</li>
</ul>

<h3>FINALIDADES DEL TRATAMIENTO</h3>
<ul>
<li>Prestación de servicios médicos</li>
<li>Facturación y gestión administrativa</li>
<li>Cumplimiento de obligaciones legales</li>
<li>Mejora de la calidad de atención</li>
</ul>

<h3>BASE LEGAL</h3>
<p>El tratamiento se realiza con base en:</p>
<ul>
<li>Art. 7, II de la LGPD - Ejecución de contrato</li>
<li>Art. 7, IV de la LGPD - Cumplimiento de obligación legal</li>
<li>Art. 7, VII de la LGPD - Protección de la vida</li>
</ul>

<h3>DERECHOS DEL TITULAR</h3>
<p>Como titular de los datos, tengo derecho a:</p>
<ul>
<li>Confirmación de la existencia de tratamiento</li>
<li>Acceso a mis datos</li>
<li>Corrección de datos incompletos o desactualizados</li>
<li>Anonimización, bloqueo o eliminación</li>
<li>Portabilidad de los datos</li>
<li>Revocación del consentimiento</li>
</ul>

<h3>DECLARACIÓN</h3>
<p>Declaro que he sido informado/a sobre el tratamiento de mis datos personales y doy mi consentimiento libre, específico e informado.</p>

<p><strong>Firma:</strong> _________________</p>
<p><strong>Fecha:</strong> {date}</p>
""",
            "required_fields": []
        },
        
        ConsentType.TELEMEDICINE: {
            "title": "Consentimiento para Telemedicina",
            "content": """
<h2>CONSENTIMIENTO PARA ATENCIÓN MÉDICA A DISTANCIA (TELEMEDICINA)</h2>

<p><strong>Paciente:</strong> {patient_name}</p>

<h3>NATURALEZA DEL SERVICIO</h3>
<p>Entiendo que recibiré atención médica a través de medios tecnológicos (videollamada, teléfono, chat) sin presencia física del médico.</p>

<h3>LIMITACIONES</h3>
<p>Entiendo las limitaciones de la telemedicina:</p>
<ul>
<li>No permite examen físico directo</li>
<li>La calidad de diagnóstico puede verse afectada por problemas técnicos</li>
<li>No es apropiada para todas las condiciones médicas</li>
<li>Puede requerir consulta presencial posterior</li>
</ul>

<h3>CONFIDENCIALIDAD Y SEGURIDAD</h3>
<p>Se me ha informado sobre las medidas de seguridad implementadas para proteger la confidencialidad de la consulta.</p>

<h3>CONSENTIMIENTO</h3>
<p>Acepto recibir atención médica a través de telemedicina y entiendo sus limitaciones.</p>

<p><strong>Firma del Paciente:</strong> _________________</p>
<p><strong>Firma del Médico:</strong> _________________</p>
<p><strong>Fecha:</strong> {date}</p>
""",
            "required_fields": ["patient_name"]
        }
    }
    
    @classmethod
    def get_template(cls, consent_type: ConsentType) -> Dict[str, Any]:
        """Obtiene template por tipo."""
        return cls.TEMPLATES.get(consent_type, cls.TEMPLATES[ConsentType.GENERAL])
    
    @classmethod
    def render_template(cls, consent_type: ConsentType, field_values: Dict[str, Any]) -> str:
        """Renderiza template con valores."""
        template = cls.get_template(consent_type)
        content = template["content"]
        
        # Valores por defecto
        defaults = {
            "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
            "patient_name": "[Nombre del Paciente]",
            "patient_dni": "[DNI]",
            "physician_name": "[Nombre del Médico]"
        }
        
        # Combinar
        values = {**defaults, **field_values}
        
        # Reemplazar placeholders
        for key, value in values.items():
            content = content.replace(f"{{{key}}}", str(value))
        
        return content


class ConsentManager:
    """
    Manager de consentimientos informados.
    """
    
    def __init__(self):
        self._consents: Dict[str, InformedConsent] = {}
        self._load_consents()
    
    def _load_consents(self):
        """Carga consentimientos desde session_state."""
        if "informed_consents" in st.session_state:
            try:
                consents_data = st.session_state["informed_consents"]
                if isinstance(consents_data, dict):
                    # Convertir desde dict
                    for k, v in consents_data.items():
                        if isinstance(v, dict):
                            self._consents[k] = InformedConsent(
                                id=v["id"],
                                patient_id=v["patient_id"],
                                patient_name=v["patient_name"],
                                consent_type=ConsentType[v["consent_type"]],
                                status=ConsentStatus(v["status"]),
                                template_id=v["template_id"],
                                template_version=v["template_version"],
                                content=v["content"],
                                patient_signature=self._dict_to_signature(v.get("patient_signature")),
                                physician_signature=self._dict_to_signature(v.get("physician_signature")),
                                witness_signature=self._dict_to_signature(v.get("witness_signature")),
                                created_at=datetime.fromisoformat(v["created_at"]),
                                expires_at=datetime.fromisoformat(v["expires_at"]) if v.get("expires_at") else None,
                                completed_at=datetime.fromisoformat(v["completed_at"]) if v.get("completed_at") else None,
                                field_values=v.get("field_values", {}),
                                content_hash=v.get("content_hash")
                            )
            except Exception as e:
                log_event("consent", f"Failed to load consents: {e}")
    
    def _dict_to_signature(self, data: Optional[Dict]) -> Optional[ConsentSignature]:
        """Convierte dict a ConsentSignature."""
        if not data:
            return None
        return ConsentSignature(
            signer_name=data["signer_name"],
            signer_role=data["signer_role"],
            signed_at=datetime.fromisoformat(data["signed_at"]),
            signature_data=data["signature_data"],
            ip_address=data.get("ip_address"),
            user_agent=data.get("user_agent"),
            document_hash=data.get("document_hash")
        )
    
    def _save_consents(self):
        """Guarda consentimientos a session_state."""
        consents_dict = {}
        for k, v in self._consents.items():
            consents_dict[k] = v.to_dict()
        
        st.session_state["informed_consents"] = consents_dict
    
    def create_consent(
        self,
        patient_id: str,
        patient_name: str,
        consent_type: ConsentType,
        field_values: Dict[str, Any],
        expires_days: Optional[int] = None
    ) -> InformedConsent:
        """
        Crea un nuevo consentimiento.
        
        Args:
            patient_id: ID del paciente
            patient_name: Nombre del paciente
            consent_type: Tipo de consentimiento
            field_values: Valores para el template
            expires_days: Días hasta expiración
        
        Returns:
            InformedConsent creado
        """
        import uuid
        
        # Renderizar contenido
        content = ConsentTemplate.render_template(consent_type, field_values)
        
        # Crear consentimiento
        consent = InformedConsent(
            id=str(uuid.uuid4()),
            patient_id=patient_id,
            patient_name=patient_name,
            consent_type=consent_type,
            status=ConsentStatus.PENDING,
            template_id=consent_type.name,
            template_version="1.0.0",
            content=content,
            field_values=field_values,
            expires_at=datetime.now() + timedelta(days=expires_days) if expires_days else None
        )
        
        # Calcular hash
        consent.content_hash = consent.calculate_hash()
        
        # Guardar
        self._consents[consent.id] = consent
        self._save_consents()
        
        log_event("consent", f"Created consent: {consent_type.name} for {patient_name}")
        
        audit_log(
            AuditEventType.CONFIG_CHANGE,
            resource_type="consent",
            resource_id=consent.id,
            action="CREATE",
            description=f"Consent created: {consent_type.name} for {patient_name}"
        )
        
        return consent
    
    def sign_consent(
        self,
        consent_id: str,
        signer_name: str,
        signer_role: str,
        signature_data: str,  # Base64 SVG/path
        ip_address: Optional[str] = None
    ) -> bool:
        """
        Firma un consentimiento.
        
        Args:
            consent_id: ID del consentimiento
            signer_name: Nombre del firmante
            signer_role: Rol (paciente, médico, testigo)
            signature_data: Datos de la firma (SVG)
            ip_address: IP del firmante
        
        Returns:
            True si se firmó exitosamente
        """
        if consent_id not in self._consents:
            return False
        
        consent = self._consents[consent_id]
        
        # Crear firma
        signature = ConsentSignature(
            signer_name=signer_name,
            signer_role=signer_role,
            signed_at=datetime.now(),
            signature_data=signature_data,
            ip_address=ip_address,
            document_hash=consent.content_hash
        )
        
        # Asignar según rol
        if signer_role == "paciente":
            consent.patient_signature = signature
        elif signer_role == "médico":
            consent.physician_signature = signature
        elif signer_role == "testigo":
            consent.witness_signature = signature
        
        # Verificar si está completo
        if consent.patient_signature and consent.physician_signature:
            consent.status = ConsentStatus.SIGNED
            consent.completed_at = datetime.now()
        
        self._save_consents()
        
        log_event("consent", f"Consent signed: {consent_id} by {signer_name} ({signer_role})")
        
        return True
    
    def get_consent(self, consent_id: str) -> Optional[InformedConsent]:
        """Obtiene consentimiento por ID."""
        return self._consents.get(consent_id)
    
    def get_patient_consents(self, patient_id: str) -> List[InformedConsent]:
        """Obtiene todos los consentimientos de un paciente."""
        return [c for c in self._consents.values() if c.patient_id == patient_id]
    
    def verify_consent(self, consent_id: str) -> Dict[str, Any]:
        """
        Verifica integridad de un consentimiento.
        
        Returns:
            Dict con resultado de verificación
        """
        consent = self._consents.get(consent_id)
        
        if not consent:
            return {"valid": False, "error": "Consent not found"}
        
        # Verificar integridad del contenido
        content_valid = consent.verify_integrity()
        
        # Verificar firmas
        signatures_valid = []
        
        for sig in [consent.patient_signature, consent.physician_signature, consent.witness_signature]:
            if sig:
                sig_valid = sig.document_hash == consent.content_hash
                signatures_valid.append({
                    "signer": sig.signer_name,
                    "role": sig.signer_role,
                    "valid": sig_valid,
                    "date": sig.signed_at
                })
        
        return {
            "valid": content_valid and all(s["valid"] for s in signatures_valid),
            "content_valid": content_valid,
            "signatures": signatures_valid,
            "status": consent.status.value,
            "tampered": not content_valid
        }
    
    def export_to_pdf(self, consent_id: str) -> Optional[bytes]:
        """Exporta consentimiento a PDF."""
        consent = self._consents.get(consent_id)
        if not consent:
            return None
        
        try:
            from fpdf import FPDF
            
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", size=12)
            
            # Convertir HTML a texto plano básico
            content = consent.content
            content = content.replace("<h2>", "\n\n").replace("</h2>", "\n")
            content = content.replace("<h3>", "\n").replace("</h3>", "\n")
            content = content.replace("<p>", "\n").replace("</p>", "\n")
            content = content.replace("<strong>", "**").replace("</strong>", "**")
            content = content.replace("<li>", "\n- ").replace("</li>", "")
            content = content.replace("<ul>", "").replace("</ul>", "")
            content = content.replace("<ol>", "").replace("</ol>", "")
            
            # Limpiar tags restantes
            import re
            content = re.sub('<[^<]+?>', '', content)
            
            # Escribir contenido
            pdf.multi_cell(0, 5, content)
            
            # Agregar firmas si existen
            if consent.patient_signature:
                pdf.add_page()
                pdf.cell(0, 10, "FIRMAS:", ln=True)
                
                if consent.patient_signature:
                    pdf.cell(0, 10, f"Paciente: {consent.patient_signature.signer_name}", ln=True)
                    pdf.cell(0, 10, f"Fecha: {consent.patient_signature.signed_at}", ln=True)
                
                if consent.physician_signature:
                    pdf.cell(0, 10, f"Médico: {consent.physician_signature.signer_name}", ln=True)
            
            return pdf.output(dest="S").encode("latin-1")
            
        except ImportError:
            # Fallback a HTML
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head><title>Consentimiento</title></head>
            <body>
                {consent.content}
                <hr>
                <h3>Firmas</h3>
                {f'<p>Paciente: {consent.patient_signature.signer_name} - {consent.patient_signature.signed_at}</p>' if consent.patient_signature else ''}
                {f'<p>Médico: {consent.physician_signature.signer_name} - {consent.physician_signature.signed_at}</p>' if consent.physician_signature else ''}
            </body>
            </html>
            """
            return html_content.encode("utf-8")
    
    def render_consent_ui(self, consent_id: str):
        """Renderiza UI para firmar un consentimiento."""
        consent = self._consents.get(consent_id)
        
        if not consent:
            st.error("Consentimiento no encontrado")
            return
        
        st.title("📋 Consentimiento Informado")
        
        # Mostrar contenido
        st.markdown(consent.content, unsafe_allow_html=True)
        
        st.divider()
        
        # Estado de firmas
        st.subheader("Estado de Firmas")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            if consent.patient_signature:
                st.success("✅ Paciente firmado")
                st.caption(f"Por: {consent.patient_signature.signer_name}")
                st.caption(f"Fecha: {consent.patient_signature.signed_at.strftime('%d/%m/%Y %H:%M')}")
            else:
                st.warning("⏳ Pendiente firma del paciente")
        
        with col2:
            if consent.physician_signature:
                st.success("✅ Médico firmado")
            else:
                st.warning("⏳ Pendiente firma del médico")
        
        with col3:
            if consent.witness_signature:
                st.info("✅ Testigo (opcional)")
            else:
                st.caption("Sin testigo")
        
        # Botón de firma
        if consent.status != ConsentStatus.SIGNED:
            st.divider()
            st.subheader("🖊️ Firmar Documento")
            
            signer_name = st.text_input("Nombre completo del firmante")
            signer_role = st.selectbox(
                "Rol",
                options=["paciente", "médico", "testigo"]
            )
            
            st.info("En un sistema de producción, aquí iría un componente de firma digital con touch/mouse.")
            
            # Simulación de firma
            if st.checkbox("Confirmo que he leído y acepto el contenido del documento"):
                if st.button("✍️ Firmar Documento", use_container_width=True):
                    # En producción: capturar firma digital real
                    signature_placeholder = "signature_svg_data_placeholder"
                    
                    self.sign_consent(
                        consent_id=consent_id,
                        signer_name=signer_name,
                        signer_role=signer_role,
                        signature_data=signature_placeholder,
                        ip_address="127.0.0.1"  # En producción: obtener IP real
                    )
                    
                    st.success("✅ Documento firmado exitosamente")
                    st.rerun()
        else:
            st.success("✅ Documento completamente firmado")
            
            # Verificación
            verification = self.verify_consent(consent_id)
            
            with st.expander("🔐 Verificar Integridad"):
                if verification["valid"]:
                    st.success("✅ Documento verificado - No ha sido modificado")
                else:
                    st.error("⚠️ ALERTA: El documento puede haber sido alterado")
                
                st.json(verification)
            
            # Exportar
            if st.button("📥 Exportar PDF"):
                pdf_data = self.export_to_pdf(consent_id)
                if pdf_data:
                    st.download_button(
                        "Descargar PDF",
                        pdf_data,
                        file_name=f"consentimiento_{consent_id[:8]}.pdf",
                        mime="application/pdf"
                    )


# Singleton
_consent_manager: Optional[ConsentManager] = None


def get_consent_manager() -> ConsentManager:
    """Obtiene instancia del manager."""
    global _consent_manager
    if _consent_manager is None:
        _consent_manager = ConsentManager()
    return _consent_manager
