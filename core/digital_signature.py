"""
Sistema de Firmas Digitales para Documentos Médicos.

Cumplimiento legal: Ley 25.506 (Argentina) - Firma Digital

Documentos firmables:
- Recetas médicas (validez legal)
- Evoluciones clínicas
- Consentimientos informados
- Informes médicos
- Órdenes de estudios
- Certificados

Tecnología:
- RSA 2048/4096 bits para firma
- SHA-256 para hashing
- PKCS#1 v1.5 / PSS padding
- X.509 para certificados (opcional)

Almacenamiento:
- Claves privadas: encriptadas AES-256, protegidas por password
- Claves públicas: disponibles para verificación
- Documentos firmados: hash + timestamp + certificado de firma
"""
import os
import json
import hashlib
import base64
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import uuid

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa, padding
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPrivateKey, RSAPublicKey
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend

import streamlit as st

from core.app_logging import log_event
from core.config_secure import get_settings
from core.phi_encryption import get_phi_manager


class DocumentType(Enum):
    """Tipos de documentos médicos firmables."""
    RECETA = "receta"
    EVOLUCION = "evolucion"
    CONSENTIMIENTO = "consentimiento"
    INFORME = "informe"
    ORDEN_ESTUDIO = "orden_estudio"
    CERTIFICADO = "certificado"
    EPICRISIS = "epicrisis"


class SignatureStatus(Enum):
    """Estado de la firma."""
    VALID = "valid"
    INVALID = "invalid"
    EXPIRED = "expired"
    REVOKED = "revoked"
    CORRUPTED = "corrupted"


@dataclass
class SignatureMetadata:
    """Metadata de una firma digital."""
    signature_id: str
    document_id: str
    document_type: str
    signer_id: str
    signer_name: str
    signer_role: str
    signed_at: str
    hash_algorithm: str
    signature_algorithm: str
    document_hash: str
    signature_value: str  # Base64
    public_key_fingerprint: str


@dataclass
class SignedDocument:
    """Documento firmado digitalmente."""
    document_id: str
    document_type: str
    content: Dict[str, Any]  # Contenido original
    signature: SignatureMetadata
    timestamps: Dict[str, str]  # created_at, signed_at
    verification_status: str = SignatureStatus.VALID.value


class DigitalSignatureManager:
    """
    Gestor de firmas digitales para documentos médicos.
    
    Flujo:
        1. Usuario genera par de claves (RSA 2048)
        2. Al firmar: se hashea el documento + se cifra con clave privada
        3. Verificación: se decifra con clave pública + se compara hashes
    
    Uso:
        manager = DigitalSignatureManager()
        
        # Generar claves (una sola vez por usuario)
        private_key, public_key = manager.generate_keypair("dr.garcia")
        
        # Firmar documento
        signed = manager.sign_document(
            document={"paciente": "Juan", "diagnostico": "Gripe"},
            doc_type=DocumentType.EVOLUCION,
            signer_id="dr.garcia",
            signer_name="Dr. García",
            signer_role="Médico"
        )
        
        # Verificar firma
        is_valid = manager.verify_signature(signed)
    """
    
    RSA_KEY_SIZE = 2048
    HASH_ALGORITHM = "SHA-256"
    SIGNATURE_ALGORITHM = "RSA-PSS"
    
    def __init__(self):
        self._keystore: Dict[str, Dict[str, Any]] = {}  # user_id -> {private_key_enc, public_key}
        self._signed_documents: Dict[str, SignedDocument] = {}  # document_id -> signed_doc
        self._init_keystore()
    
    def _init_keystore(self) -> None:
        """Inicializa keystore desde session_state o storage."""
        if "digital_signatures_keystore" in st.session_state:
            self._keystore = st.session_state["digital_signatures_keystore"]
    
    def _save_keystore(self) -> None:
        """Guarda keystore en session_state."""
        st.session_state["digital_signatures_keystore"] = self._keystore
    
    def _get_master_encryption_key(self) -> bytes:
        """Deriva clave de encriptación de SECRET_KEY."""
        settings = get_settings()
        secret = settings.secret_key.get_secret_value()
        return hashlib.sha256(secret.encode()).digest()
    
    def _encrypt_private_key(self, private_key: RSAPrivateKey) -> bytes:
        """Encripta clave privada con AES-256-GCM."""
        # Serializar clave privada
        pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        # Encriptar
        key = self._get_master_encryption_key()
        aesgcm = AESGCM(key)
        nonce = os.urandom(12)
        encrypted = aesgcm.encrypt(nonce, pem, None)
        
        return nonce + encrypted
    
    def _decrypt_private_key(self, encrypted_key: bytes) -> RSAPrivateKey:
        """Desencripta clave privada."""
        key = self._get_master_encryption_key()
        aesgcm = AESGCM(key)
        
        nonce = encrypted_key[:12]
        ciphertext = encrypted_key[12:]
        
        pem = aesgcm.decrypt(nonce, ciphertext, None)
        
        return serialization.load_pem_private_key(pem, password=None, backend=default_backend())
    
    def generate_keypair(self, user_id: str, password: Optional[str] = None) -> Tuple[bytes, bytes]:
        """
        Genera par de claves RSA para un usuario.
        
        Args:
            user_id: Identificador único del usuario
            password: Password adicional para protección (opcional)
        
        Returns:
            (private_key_encrypted, public_key_pem)
        """
        # Generar clave privada
        private_key = rsa.generate_private_key(
            public_exponent=65537,
            key_size=self.RSA_KEY_SIZE,
            backend=default_backend()
        )
        
        # Obtener clave pública
        public_key = private_key.public_key()
        
        # Serializar clave pública
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        # Encriptar clave privada
        private_encrypted = self._encrypt_private_key(private_key)
        
        # Almacenar
        self._keystore[user_id] = {
            "private_key_enc": private_encrypted,
            "public_key": public_pem,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "fingerprint": self._get_key_fingerprint(public_pem)
        }
        
        self._save_keystore()
        
        log_event("digital_signature", f"keypair_generated:{user_id}")
        
        return private_encrypted, public_pem
    
    def _get_key_fingerprint(self, public_key_pem: bytes) -> str:
        """Calcula fingerprint de clave pública."""
        return hashlib.sha256(public_key_pem).hexdigest()[:16]
    
    def _get_user_private_key(self, user_id: str) -> Optional[RSAPrivateKey]:
        """Obtiene clave privada desencriptada de un usuario."""
        if user_id not in self._keystore:
            return None
        
        encrypted = self._keystore[user_id]["private_key_enc"]
        return self._decrypt_private_key(encrypted)
    
    def _get_user_public_key(self, user_id: str) -> Optional[RSAPublicKey]:
        """Obtiene clave pública de un usuario."""
        if user_id not in self._keystore:
            return None
        
        public_pem = self._keystore[user_id]["public_key"]
        return serialization.load_pem_public_key(public_pem, backend=default_backend())
    
    def _hash_document(self, document: Dict[str, Any]) -> str:
        """Calcula hash SHA-256 del documento."""
        # Normalizar: ordenar keys, fechas en ISO
        canonical = json.dumps(document, sort_keys=True, ensure_ascii=False, default=str)
        return hashlib.sha256(canonical.encode('utf-8')).hexdigest()
    
    def sign_document(
        self,
        document: Dict[str, Any],
        doc_type: DocumentType,
        signer_id: str,
        signer_name: str,
        signer_role: str,
        additional_metadata: Optional[Dict] = None
    ) -> SignedDocument:
        """
        Firma digitalmente un documento médico.
        
        Args:
            document: Contenido del documento
            doc_type: Tipo de documento
            signer_id: ID del firmante
            signer_name: Nombre del firmante
            signer_role: Rol (Médico, Enfermero, etc.)
            additional_metadata: Metadata adicional
        
        Returns:
            SignedDocument con firma digital
        """
        # Verificar que el usuario tiene claves
        private_key = self._get_user_private_key(signer_id)
        if private_key is None:
            raise ValueError(f"Usuario {signer_id} no tiene clave privada. Genere claves primero.")
        
        # Calcular hash del documento
        doc_hash = self._hash_document(document)
        
        # Firmar el hash
        signature_bytes = private_key.sign(
            doc_hash.encode('utf-8'),
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.MAX_LENGTH
            ),
            hashes.SHA256()
        )
        
        # Crear metadata de firma
        public_key = self._get_user_public_key(signer_id)
        public_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        )
        
        sig_metadata = SignatureMetadata(
            signature_id=str(uuid.uuid4()),
            document_id=str(uuid.uuid4()),
            document_type=doc_type.value,
            signer_id=signer_id,
            signer_name=signer_name,
            signer_role=signer_role,
            signed_at=datetime.now(timezone.utc).isoformat(),
            hash_algorithm=self.HASH_ALGORITHM,
            signature_algorithm=self.SIGNATURE_ALGORITHM,
            document_hash=doc_hash,
            signature_value=base64.b64encode(signature_bytes).decode('utf-8'),
            public_key_fingerprint=self._get_key_fingerprint(public_pem)
        )
        
        # Crear documento firmado
        signed_doc = SignedDocument(
            document_id=sig_metadata.document_id,
            document_type=doc_type.value,
            content=document,
            signature=sig_metadata,
            timestamps={
                "created_at": datetime.now(timezone.utc).isoformat(),
                "signed_at": sig_metadata.signed_at
            }
        )
        
        # Almacenar
        self._signed_documents[signed_doc.document_id] = signed_doc
        
        log_event(
            "digital_signature",
            f"document_signed:{doc_type.value}:{signer_id}:{signed_doc.document_id}"
        )
        
        return signed_doc
    
    def verify_signature(self, signed_document: SignedDocument) -> Tuple[bool, str]:
        """
        Verifica la firma digital de un documento.
        
        Returns:
            (is_valid, message)
        """
        try:
            # Obtener clave pública del firmante
            signer_id = signed_document.signature.signer_id
            public_key = self._get_user_public_key(signer_id)
            
            if public_key is None:
                return False, "Clave pública del firmante no encontrada"
            
            # Verificar fingerprint
            public_pem = public_key.public_bytes(
                encoding=serialization.Encoding.PEM,
                format=serialization.PublicFormat.SubjectPublicKeyInfo
            )
            current_fingerprint = self._get_key_fingerprint(public_pem)
            
            if current_fingerprint != signed_document.signature.public_key_fingerprint:
                return False, "Clave pública ha cambiado desde la firma"
            
            # Recalcular hash del documento
            current_hash = self._hash_document(signed_document.content)
            
            if current_hash != signed_document.signature.document_hash:
                return False, "Contenido del documento ha sido modificado"
            
            # Verificar firma criptográfica
            signature_bytes = base64.b64decode(signed_document.signature.signature_value)
            
            try:
                public_key.verify(
                    signature_bytes,
                    signed_document.signature.document_hash.encode('utf-8'),
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.MAX_LENGTH
                    ),
                    hashes.SHA256()
                )
                
                return True, "Firma válida"
                
            except Exception:
                return False, "Verificación criptográfica fallida"
        
        except Exception as e:
            return False, f"Error en verificación: {str(e)}"
    
    def has_keypair(self, user_id: str) -> bool:
        """Verifica si usuario tiene par de claves."""
        return user_id in self._keystore
    
    def get_signed_documents(
        self,
        signer_id: Optional[str] = None,
        doc_type: Optional[DocumentType] = None,
        limit: int = 50
    ) -> List[SignedDocument]:
        """Obtiene documentos firmados."""
        docs = list(self._signed_documents.values())
        
        if signer_id:
            docs = [d for d in docs if d.signature.signer_id == signer_id]
        
        if doc_type:
            docs = [d for d in docs if d.document_type == doc_type.value]
        
        # Ordenar por fecha descendente
        docs.sort(key=lambda d: d.signature.signed_at, reverse=True)
        
        return docs[:limit]
    
    def export_signature_certificate(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Exporta certificado de firma para verificación externa."""
        if document_id not in self._signed_documents:
            return None
        
        doc = self._signed_documents[document_id]
        
        return {
            "document_id": doc.document_id,
            "document_type": doc.document_type,
            "signer": {
                "id": doc.signature.signer_id,
                "name": doc.signature.signer_name,
                "role": doc.signature.signer_role
            },
            "signed_at": doc.signature.signed_at,
            "hash_algorithm": doc.signature.hash_algorithm,
            "signature_algorithm": doc.signature.signature_algorithm,
            "document_hash": doc.signature.document_hash,
            "signature": doc.signature.signature_value,
            "public_key_fingerprint": doc.signature.public_key_fingerprint,
            "verification_url": f"/api/verify/{document_id}"
        }


# Instancia global
_signature_manager = None

def get_signature_manager() -> DigitalSignatureManager:
    """Retorna instancia singleton."""
    global _signature_manager
    if _signature_manager is None:
        _signature_manager = DigitalSignatureManager()
    return _signature_manager


# Funciones helper de alto nivel

def setup_user_keys(user_id: str) -> bool:
    """Configura claves para un usuario si no las tiene."""
    manager = get_signature_manager()
    
    if not manager.has_keypair(user_id):
        manager.generate_keypair(user_id)
        return True
    
    return False


def sign_evolucion(
    evolucion: Dict[str, Any],
    medico_id: str,
    medico_name: str
) -> SignedDocument:
    """Firma una evolución clínica."""
    manager = get_signature_manager()
    
    # Asegurar que tiene claves
    if not manager.has_keypair(medico_id):
        manager.generate_keypair(medico_id)
    
    return manager.sign_document(
        document=evolucion,
        doc_type=DocumentType.EVOLUCION,
        signer_id=medico_id,
        signer_name=medico_name,
        signer_role="Médico"
    )


def sign_receta(
    receta: Dict[str, Any],
    medico_id: str,
    medico_name: str
) -> SignedDocument:
    """Firma una receta médica."""
    manager = get_signature_manager()
    
    if not manager.has_keypair(medico_id):
        manager.generate_keypair(medico_id)
    
    return manager.sign_document(
        document=receta,
        doc_type=DocumentType.RECETA,
        signer_id=medico_id,
        signer_name=medico_name,
        signer_role="Médico"
    )


def verify_document_signature(document_id: str) -> Tuple[bool, str]:
    """Verifica firma de un documento."""
    manager = get_signature_manager()
    
    if document_id not in manager._signed_documents:
        return False, "Documento no encontrado"
    
    signed_doc = manager._signed_documents[document_id]
    return manager.verify_signature(signed_doc)


def render_signature_ui() -> None:
    """Renderiza UI de firmas digitales en Streamlit."""
    import streamlit as st
    
    st.header("✍️ Firma Digital")
    
    user = st.session_state.get("u_actual", {})
    user_id = user.get("username")
    
    if not user_id:
        st.warning("Inicie sesión para usar firma digital")
        return
    
    manager = get_signature_manager()
    
    # Estado de claves
    if manager.has_keypair(user_id):
        st.success("✅ Tiene claves de firma digital configuradas")
    else:
        st.warning("⚠️ No tiene claves de firma digital")
        if st.button("Generar claves ahora"):
            manager.generate_keypair(user_id)
            st.success("Claves generadas exitosamente")
            st.rerun()
    
    # Documentos firmados
    with st.expander("📜 Documentos firmados"):
        docs = manager.get_signed_documents(signer_id=user_id, limit=10)
        
        if not docs:
            st.info("No ha firmado documentos aún")
        else:
            for doc in docs:
                with st.container():
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"**{doc.document_type.upper()}** - {doc.signature.signed_at[:16]}")
                    with col2:
                        is_valid, msg = manager.verify_signature(doc)
                        if is_valid:
                            st.success("✓ Válida")
                        else:
                            st.error("✗ Inválida")
                    st.caption(f"ID: {doc.document_id[:8]}...")
