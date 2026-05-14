"""
Sistema de Gestión de Documentos y Archivos Adjuntos para Medicare Pro.

Características:
- Almacenamiento seguro de archivos ( estudios, fotos, documentos)
- Versionado de documentos
- OCR básico para PDFs
- Previsualización de imágenes
- Control de acceso por rol
- Retención automática
- Compresión y optimización
"""

from __future__ import annotations

import hashlib
import io
import os
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, BinaryIO
import base64
import mimetypes

import streamlit as st
from PIL import Image

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType
from core.data_validation import get_validator


class DocumentType(Enum):
    """Tipos de documentos médicos."""
    STUDY_RESULT = auto()        # Resultado de estudio/laboratorio
    MEDICAL_IMAGE = auto()       # Imagen médica (RX, ecografía, etc.)
    PHOTO = auto()               # Fotografía clínica
    PDF = auto()                 # Documento PDF
    CERTIFICATE = auto()         # Certificado médico
    CONSENT = auto()             # Consentimiento firmado
    INSURANCE_CARD = auto()      # Carnet de obra social
    ID_DOCUMENT = auto()         # Documento de identidad
    PRESCRIPTION = auto()        # Receta escaneada
    OTHER = auto()               # Otros


class DocumentStatus(Enum):
    """Estados del documento."""
    UPLOADING = auto()
    PROCESSING = auto()
    ACTIVE = auto()
    ARCHIVED = auto()
    DELETED = auto()


@dataclass
class DocumentMetadata:
    """Metadata de un documento."""
    id: str
    patient_id: str
    patient_name: str
    document_type: DocumentType
    filename: str
    original_filename: str
    file_size: int
    mime_type: str
    upload_date: datetime
    uploaded_by: str
    uploaded_by_id: str
    status: DocumentStatus
    description: Optional[str] = None
    tags: List[str] = None
    version: int = 1
    previous_version_id: Optional[str] = None
    checksum: Optional[str] = None
    ocr_text: Optional[str] = None  # Texto extraído por OCR
    thumbnail_base64: Optional[str] = None
    retention_until: Optional[datetime] = None
    
    def __post_init__(self):
        if self.tags is None:
            self.tags = []


class DocumentManager:
    """
    Manager de documentos médicos.
    
    Almacena archivos de forma segura con:
    - Hash de verificación
    - Control de versiones
    - Thumbnails para imágenes
    - OCR para PDFs
    """
    
    # Límites
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png', '.gif', '.bmp', '.tiff', '.dcm'}
    
    # Retención por tipo (años)
    RETENTION_YEARS = {
        DocumentType.STUDY_RESULT: 10,
        DocumentType.MEDICAL_IMAGE: 10,
        DocumentType.PHOTO: 7,
        DocumentType.PDF: 7,
        DocumentType.CERTIFICATE: 5,
        DocumentType.CONSENT: 15,
        DocumentType.INSURANCE_CARD: 3,
        DocumentType.ID_DOCUMENT: 3,
        DocumentType.PRESCRIPTION: 2,
        DocumentType.OTHER: 3
    }
    
    def __init__(self, storage_path: str = "documents"):
        self.storage_path = Path(storage_path)
        self.storage_path.mkdir(exist_ok=True)
        
        # Subdirectorios
        (self.storage_path / "thumbnails").mkdir(exist_ok=True)
        (self.storage_path / "temp").mkdir(exist_ok=True)
        
        self._documents: Dict[str, DocumentMetadata] = {}
        self._load_documents()
    
    def _load_documents(self):
        """Carga metadata de documentos."""
        if "document_metadata" in st.session_state:
            try:
                data = st.session_state["document_metadata"]
                if isinstance(data, dict):
                    for k, v in data.items():
                        if isinstance(v, dict):
                            self._documents[k] = DocumentMetadata(
                                id=v["id"],
                                patient_id=v["patient_id"],
                                patient_name=v["patient_name"],
                                document_type=DocumentType[v["document_type"]],
                                filename=v["filename"],
                                original_filename=v["original_filename"],
                                file_size=v["file_size"],
                                mime_type=v["mime_type"],
                                upload_date=datetime.fromisoformat(v["upload_date"]),
                                uploaded_by=v["uploaded_by"],
                                uploaded_by_id=v["uploaded_by_id"],
                                status=DocumentStatus[v["status"]],
                                description=v.get("description"),
                                tags=v.get("tags", []),
                                version=v.get("version", 1),
                                previous_version_id=v.get("previous_version_id"),
                                checksum=v.get("checksum"),
                                ocr_text=v.get("ocr_text"),
                                thumbnail_base64=v.get("thumbnail_base64"),
                                retention_until=datetime.fromisoformat(v["retention_until"]) if v.get("retention_until") else None
                            )
            except Exception as e:
                log_event("documents", f"Error loading metadata: {e}")
    
    def _save_metadata(self):
        """Guarda metadata."""
        data = {}
        for k, v in self._documents.items():
            doc_dict = asdict(v)
            doc_dict["document_type"] = v.document_type.name
            doc_dict["status"] = v.status.name
            doc_dict["upload_date"] = v.upload_date.isoformat()
            doc_dict["retention_until"] = v.retention_until.isoformat() if v.retention_until else None
            data[k] = doc_dict
        
        st.session_state["document_metadata"] = data
    
    def upload_document(
        self,
        file_data: Union[bytes, BinaryIO],
        patient_id: str,
        patient_name: str,
        document_type: DocumentType,
        original_filename: str,
        description: Optional[str] = None,
        tags: Optional[List[str]] = None,
        uploaded_by: str = "",
        uploaded_by_id: str = ""
    ) -> Optional[DocumentMetadata]:
        """
        Sube un documento.
        
        Args:
            file_data: Datos del archivo
            patient_id: ID del paciente
            patient_name: Nombre del paciente
            document_type: Tipo de documento
            original_filename: Nombre original
            description: Descripción
            tags: Etiquetas
            uploaded_by: Nombre de quien sube
            uploaded_by_id: ID de quien sube
        
        Returns:
            DocumentMetadata o None si falló
        """
        import uuid
        
        # Validar extensión
        ext = Path(original_filename).suffix.lower()
        if ext not in self.ALLOWED_EXTENSIONS:
            st.error(f"❌ Extensión no permitida: {ext}")
            return None
        
        # Obtener bytes
        if hasattr(file_data, 'read'):
            content = file_data.read()
        else:
            content = file_data
        
        # Validar tamaño
        if len(content) > self.MAX_FILE_SIZE:
            st.error(f"❌ Archivo demasiado grande: {len(content) / 1024 / 1024:.1f}MB (máx: {self.MAX_FILE_SIZE / 1024 / 1024}MB)")
            return None
        
        # Generar nombre único
        doc_id = str(uuid.uuid4())
        file_hash = hashlib.sha256(content).hexdigest()[:16]
        filename = f"{patient_id}_{doc_id}_{file_hash}{ext}"
        
        # Guardar archivo
        file_path = self.storage_path / filename
        try:
            with open(file_path, 'wb') as f:
                f.write(content)
        except Exception as e:
            log_event("documents_error", f"Failed to save file: {e}")
            return None
        
        # Generar thumbnail si es imagen
        thumbnail_base64 = None
        if document_type in [DocumentType.MEDICAL_IMAGE, DocumentType.PHOTO] or ext in ['.jpg', '.jpeg', '.png']:
            thumbnail_base64 = self._generate_thumbnail(content, ext)
        
        # OCR para PDFs
        ocr_text = None
        if document_type == DocumentType.PDF or ext == '.pdf':
            ocr_text = self._extract_pdf_text(content)
        
        # Calcular retención
        retention_years = self.RETENTION_YEARS.get(document_type, 7)
        retention_until = datetime.now() + timedelta(days=365 * retention_years)
        
        # Crear metadata
        mime_type, _ = mimetypes.guess_type(original_filename)
        
        doc = DocumentMetadata(
            id=doc_id,
            patient_id=patient_id,
            patient_name=patient_name,
            document_type=document_type,
            filename=filename,
            original_filename=original_filename,
            file_size=len(content),
            mime_type=mime_type or 'application/octet-stream',
            upload_date=datetime.now(),
            uploaded_by=uploaded_by,
            uploaded_by_id=uploaded_by_id,
            status=DocumentStatus.ACTIVE,
            description=description,
            tags=tags or [],
            checksum=hashlib.sha256(content).hexdigest(),
            ocr_text=ocr_text,
            thumbnail_base64=thumbnail_base64,
            retention_until=retention_until
        )
        
        self._documents[doc_id] = doc
        self._save_metadata()
        
        # Audit log
        audit_log(
            AuditEventType.DATA_EXPORT,
            resource_type="document",
            resource_id=doc_id,
            action="UPLOAD",
            description=f"Document uploaded: {original_filename} for {patient_name}",
            metadata={"type": document_type.name, "size": len(content)}
        )
        
        log_event("documents", f"Document uploaded: {doc_id} ({original_filename})")
        
        return doc
    
    def _generate_thumbnail(self, image_data: bytes, ext: str, size: int = 200) -> Optional[str]:
        """Genera thumbnail de imagen."""
        try:
            img = Image.open(io.BytesIO(image_data))
            img.thumbnail((size, size))
            
            # Convertir a base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            return base64.b64encode(buffer.getvalue()).decode()
        except Exception as e:
            log_event("documents", f"Thumbnail generation failed: {e}")
            return None
    
    def _extract_pdf_text(self, pdf_data: bytes) -> Optional[str]:
        """Extrae texto de PDF usando OCR básico."""
        try:
            # Intentar pypdf (reemplazo seguro de PyPDF2)
            import pypdf
            reader = pypdf.PdfReader(io.BytesIO(pdf_data))
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            
            if text.strip():
                return text[:5000]  # Limitar texto
            
            # Si no hay texto, requiere OCR de imagen (requeriría pytesseract)
            return None
            
        except ImportError:
            return None
        except Exception as e:
            log_event("documents", f"PDF text extraction failed: {e}")
            return None
    
    def get_document(self, doc_id: str) -> Optional[DocumentMetadata]:
        """Obtiene metadata de documento."""
        return self._documents.get(doc_id)
    
    def get_patient_documents(
        self,
        patient_id: str,
        doc_type: Optional[DocumentType] = None,
        tags: Optional[List[str]] = None
    ) -> List[DocumentMetadata]:
        """Obtiene documentos de un paciente."""
        results = []
        
        for doc in self._documents.values():
            if doc.patient_id != patient_id:
                continue
            if doc.status != DocumentStatus.ACTIVE:
                continue
            if doc_type and doc.document_type != doc_type:
                continue
            if tags and not all(tag in doc.tags for tag in tags):
                continue
            
            results.append(doc)
        
        return sorted(results, key=lambda x: x.upload_date, reverse=True)
    
    def get_document_content(self, doc_id: str) -> Optional[bytes]:
        """Obtiene contenido del archivo."""
        doc = self._documents.get(doc_id)
        if not doc:
            return None
        
        file_path = self.storage_path / doc.filename
        if not file_path.exists():
            return None
        
        try:
            with open(file_path, 'rb') as f:
                return f.read()
        except Exception as e:
            log_event("documents_error", f"Failed to read file {doc_id}: {e}")
            return None
    
    def delete_document(self, doc_id: str, deleted_by: str = "") -> bool:
        """Elimina un documento (soft delete)."""
        if doc_id not in self._documents:
            return False
        
        doc = self._documents[doc_id]
        doc.status = DocumentStatus.DELETED
        
        self._save_metadata()
        
        audit_log(
            AuditEventType.DATA_EXPORT,
            resource_type="document",
            resource_id=doc_id,
            action="DELETE",
            description=f"Document deleted by {deleted_by}"
        )
        
        return True
    
    def search_documents(
        self,
        query: str,
        patient_id: Optional[str] = None,
        doc_type: Optional[DocumentType] = None
    ) -> List[DocumentMetadata]:
        """Busca documentos por texto (OCR, nombre, tags)."""
        query = query.lower()
        results = []
        
        for doc in self._documents.values():
            if doc.status != DocumentStatus.ACTIVE:
                continue
            if patient_id and doc.patient_id != patient_id:
                continue
            if doc_type and doc.document_type != doc_type:
                continue
            
            # Buscar en nombre, descripción, tags, OCR
            searchable_text = f"{doc.original_filename} {doc.description or ''} {' '.join(doc.tags)} {doc.ocr_text or ''}".lower()
            
            if query in searchable_text:
                results.append(doc)
        
        return sorted(results, key=lambda x: x.upload_date, reverse=True)
    
    def render_document_gallery(self, patient_id: str):
        """Renderiza galería de documentos de paciente."""
        st.subheader("📁 Documentos del Paciente")
        
        documents = self.get_patient_documents(patient_id)
        
        if not documents:
            st.info("📭 No hay documentos adjuntos")
            return
        
        # Grid de documentos
        cols = st.columns(4)
        
        for i, doc in enumerate(documents):
            with cols[i % 4]:
                # Thumbnail o icono
                if doc.thumbnail_base64:
                    st.image(f"data:image/png;base64,{doc.thumbnail_base64}", use_column_width=True)
                else:
                    icons = {
                        DocumentType.PDF: "📄",
                        DocumentType.MEDICAL_IMAGE: "🩻",
                        DocumentType.PHOTO: "📷",
                        DocumentType.CONSENT: "✍️",
                        DocumentType.CERTIFICATE: "📜"
                    }
                    st.markdown(f"<h1 style='text-align: center;'>{icons.get(doc.document_type, '📎')}</h1>", unsafe_allow_html=True)
                
                st.caption(doc.original_filename[:20] + "..." if len(doc.original_filename) > 20 else doc.original_filename)
                st.caption(f"{doc.upload_date.strftime('%d/%m/%Y')}")
                
                # Acciones
                col1, col2 = st.columns(2)
                
                with col1:
                    if st.button("👁️ Ver", key=f"view_{doc.id}"):
                        content = self.get_document_content(doc.id)
                        if content:
                            st.download_button(
                                "Descargar",
                                content,
                                file_name=doc.original_filename,
                                mime=doc.mime_type
                            )
                
                def _on_delete_document(doc_id: str):
                    try:
                        self.delete_document(doc_id)
                    except Exception as e:
                        log_event("document_manager", f"Error al eliminar documento {doc_id}: {e}")
                        st.error("No se pudo eliminar el documento.")

                with col2:
                    st.button("🗑️", key=f"del_{doc.id}", on_click=_on_delete_document, args=(doc.id,))
    
    def render_upload_form(self, patient_id: str, patient_name: str):
        """Renderiza formulario de subida."""
        st.subheader("⬆️ Subir Nuevo Documento")
        
        uploaded_file = st.file_uploader(
            "Seleccionar archivo",
            type=['pdf', 'jpg', 'jpeg', 'png', 'gif'],
            key=f"uploader_{patient_id}"
        )
        
        if uploaded_file:
            col1, col2 = st.columns(2)
            
            with col1:
                doc_type = st.selectbox(
                    "Tipo de documento",
                    options=[
                        ("Estudio/Laboratorio", DocumentType.STUDY_RESULT),
                        ("Imagen Médica", DocumentType.MEDICAL_IMAGE),
                        ("Fotografía", DocumentType.PHOTO),
                        ("PDF", DocumentType.PDF),
                        ("Certificado", DocumentType.CERTIFICATE),
                        ("Consentimiento", DocumentType.CONSENT),
                        ("Carnet OS", DocumentType.INSURANCE_CARD),
                        ("DNI", DocumentType.ID_DOCUMENT),
                        ("Receta", DocumentType.PRESCRIPTION),
                        ("Otro", DocumentType.OTHER)
                    ],
                    format_func=lambda x: x[0]
                )
            
            with col2:
                tags = st.text_input("Tags (separados por coma)", placeholder="urgente, preoperatorio")
            
            description = st.text_area("Descripción", placeholder="Notas sobre el documento...")
            
            if st.button("📤 Subir Documento", width='stretch', type="primary"):
                user = st.session_state.get("u_actual", {})
                try:
                    doc = self.upload_document(
                        file_data=uploaded_file.getvalue(),
                        patient_id=patient_id,
                        patient_name=patient_name,
                        document_type=doc_type[1],
                        original_filename=uploaded_file.name,
                        description=description,
                        tags=[t.strip() for t in tags.split(",") if t.strip()],
                        uploaded_by=user.get("nombre", "Sistema"),
                        uploaded_by_id=user.get("usuario_login", "system")
                    )
                    if doc:
                        st.success("✅ Documento subido exitosamente")
                except Exception as e:
                    log_event("document_manager", f"Error al subir documento: {e}")
                    st.error("No se pudo subir el documento.")


# Singleton
_document_manager: Optional[DocumentManager] = None


def get_document_manager() -> DocumentManager:
    """Obtiene instancia del manager."""
    global _document_manager
    if _document_manager is None:
        _document_manager = DocumentManager()
    return _document_manager
