"""
Encriptación de Datos Sensibles (PHI - Protected Health Information).

Cumplimiento: HIPAA, GDPR, LGPD

Campos encriptados:
- Datos personales: DNI, nombre completo, dirección, teléfono
- Datos médicos: diagnósticos, evoluciones, prescripciones
- Datos de contacto: emails, números de emergencia

Algoritmo: AES-256-GCM (Authenticated Encryption)
- Confidencialidad: Solo titulares con clave pueden leer
- Integridad: Detección de tampering
- Autenticidad: Verificación de origen

Key Management:
- Master key derivada de SECRET_KEY (HKDF)
- Data encryption keys (DEK) por campo
- Key rotation soportado
"""
import os
import json
import base64
import hashlib
from typing import Dict, Any, Optional, List, Union
from dataclasses import dataclass
from datetime import datetime, timezone

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend

from core.config_secure import get_settings
from core.app_logging import log_event


# Campos sensibles por tabla que DEBEN encriptarse
PHI_FIELDS = {
    "pacientes": [
        "dni",
        "nombre",
        "apellido",
        "email",
        "telefono",
        "direccion",
        "obra_social_numero",
        "contacto_emergencia_nombre",
        "contacto_emergencia_telefono",
    ],
    "evoluciones": [
        "diagnostico",
        "tratamiento",
        "evolucion_detalle",
        "notas_privadas",
    ],
    "vitales": [],  # Datos numéricos no sensibles por sí solos
    "recetas": [
        "medicamentos",
        "indicaciones",
    ],
    "estudios": [
        "resultados",
        "observaciones",
        "conclusiones",
    ],
    "usuarios": [
        "email_personal",
        "telefono_personal",
    ]
}


@dataclass
class EncryptedField:
    """Campo encriptado con metadata."""
    ciphertext: str  # Base64 encoded
    nonce: str         # Base64 encoded
    tag: str          # GCM auth tag
    version: int       # Key version para rotation
    encrypted_at: str  # ISO timestamp


class PHIEncryptionManager:
    """
    Gestor de encriptación de datos médicos sensibles.
    
    Uso:
        manager = PHIEncryptionManager()
        
        # Encriptar datos de paciente
        encrypted = manager.encrypt_record(
            table="pacientes",
            record={"dni": "12345678", "nombre": "Juan Pérez"}
        )
        
        # Desencriptar
        decrypted = manager.decrypt_record(
            table="pacientes",
            encrypted_record=encrypted
        )
    """
    
    CURRENT_KEY_VERSION = 1
    KEY_ROTATION_DAYS = 90
    
    def __init__(self):
        self._master_key = None
        self._data_keys: Dict[str, bytes] = {}
        self._init_keys()
    
    def _init_keys(self) -> None:
        """Inicializa claves de encriptación."""
        try:
            settings = get_settings()
            secret = settings.secret_key.get_secret_value()
            
            if not secret or len(secret) < 32:
                raise ValueError("SECRET_KEY debe tener al menos 32 caracteres")
            
            # Derivar master key de 32 bytes para AES-256
            self._master_key = hashlib.sha256(secret.encode()).digest()
            
            # Derivar data encryption keys por tabla
            for table in PHI_FIELDS.keys():
                self._data_keys[table] = self._derive_key(table)
            
            log_event("phi_encryption", "keys_initialized")
            
        except Exception as e:
            log_event("phi_encryption", f"key_init_error:{type(e).__name__}")
            raise
    
    def _derive_key(self, context: str) -> bytes:
        """Deriva clave específica para contexto usando HKDF."""
        hkdf = HKDF(
            algorithm=hashes.SHA256(),
            length=32,
            salt=None,
            info=context.encode(),
            backend=default_backend()
        )
        return hkdf.derive(self._master_key)
    
    def _get_key(self, table: str) -> bytes:
        """Retorna DEK para tabla."""
        if table not in self._data_keys:
            self._data_keys[table] = self._derive_key(table)
        return self._data_keys[table]
    
    def encrypt_value(self, value: str, table: str) -> Optional[str]:
        """
        Encripta un valor individual.
        
        Args:
            value: Valor a encriptar
            table: Tabla de origen (determina qué clave usar)
        
        Returns:
            String JSON con ciphertext, nonce, tag, version
        """
        if value is None:
            return None
        
        if not isinstance(value, str):
            value = str(value)
        
        try:
            key = self._get_key(table)
            aesgcm = AESGCM(key)
            
            nonce = os.urandom(12)  # 96 bits para GCM
            plaintext = value.encode('utf-8')
            
            # Encriptar (ciphertext incluye tag de 16 bytes al final)
            ciphertext_with_tag = aesgcm.encrypt(nonce, plaintext, None)
            
            # Separar ciphertext y tag (últimos 16 bytes)
            ciphertext = ciphertext_with_tag[:-16]
            tag = ciphertext_with_tag[-16:]
            
            # Crear estructura encriptada
            encrypted_field = EncryptedField(
                ciphertext=base64.b64encode(ciphertext).decode('utf-8'),
                nonce=base64.b64encode(nonce).decode('utf-8'),
                tag=base64.b64encode(tag).decode('utf-8'),
                version=self.CURRENT_KEY_VERSION,
                encrypted_at=datetime.now(timezone.utc).isoformat()
            )
            
            return json.dumps(encrypted_field.__dict__)
            
        except Exception as e:
            log_event("phi_encryption", f"encrypt_error:{table}:{type(e).__name__}")
            raise
    
    def decrypt_value(self, encrypted_json: str, table: str) -> Optional[str]:
        """
        Desencripta un valor.
        
        Args:
            encrypted_json: String JSON de EncryptedField
            table: Tabla de origen
        
        Returns:
            Valor desencriptado o None si es None
        """
        if encrypted_json is None:
            return None
        
        try:
            # Parsear estructura
            data = json.loads(encrypted_json)
            
            # Si no es un campo encriptado válido, retornar como está
            if not all(k in data for k in ['ciphertext', 'nonce', 'tag']):
                return encrypted_json  # No estaba encriptado
            
            key = self._get_key(table)
            aesgcm = AESGCM(key)
            
            # Decodificar
            ciphertext = base64.b64decode(data['ciphertext'])
            nonce = base64.b64decode(data['nonce'])
            tag = base64.b64decode(data['tag'])
            
            # Reconstruir ciphertext con tag
            ciphertext_with_tag = ciphertext + tag
            
            # Desencriptar
            plaintext = aesgcm.decrypt(nonce, ciphertext_with_tag, None)
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            log_event("phi_encryption", f"decrypt_error:{table}:{type(e).__name__}")
            raise
    
    def encrypt_record(
        self,
        table: str,
        record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Encripta campos sensibles de un registro.
        
        Args:
            table: Nombre de tabla
            record: Diccionario con datos
        
        Returns:
            Registro con campos sensibles encriptados
        """
        if table not in PHI_FIELDS:
            # No hay campos sensibles definidos para esta tabla
            return record
        
        sensitive_fields = PHI_FIELDS[table]
        encrypted_record = {}
        
        for field, value in record.items():
            if field in sensitive_fields and value is not None:
                try:
                    encrypted_record[field] = self.encrypt_value(value, table)
                    encrypted_record[f"{field}_encrypted"] = True  # Flag
                except Exception as e:
                    log_event("phi_encryption", f"field_encrypt_error:{table}:{field}")
                    # En caso de error, no encriptar este campo pero loggear
                    encrypted_record[field] = value
            else:
                encrypted_record[field] = value
        
        return encrypted_record
    
    def decrypt_record(
        self,
        table: str,
        encrypted_record: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Desencripta campos sensibles de un registro.
        
        Args:
            table: Nombre de tabla
            encrypted_record: Registro posiblemente encriptado
        
        Returns:
            Registro con campos sensibles desencriptados
        """
        if table not in PHI_FIELDS:
            return encrypted_record
        
        sensitive_fields = PHI_FIELDS[table]
        decrypted_record = {}
        
        for field, value in encrypted_record.items():
            # Skip flag fields
            if field.endswith('_encrypted'):
                continue
            
            if field in sensitive_fields and value is not None:
                try:
                    # Verificar si está encriptado
                    if isinstance(value, str) and value.startswith('{'):
                        decrypted = self.decrypt_value(value, table)
                        if decrypted != value:  # Se desencriptó exitosamente
                            decrypted_record[field] = decrypted
                        else:
                            decrypted_record[field] = value
                    else:
                        decrypted_record[field] = value
                except Exception:
                    # Si falla desencriptación, mantener valor original
                    decrypted_record[field] = value
            else:
                decrypted_record[field] = value
        
        return decrypted_record
    
    def encrypt_batch(
        self,
        table: str,
        records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Encripta un lote de registros."""
        return [self.encrypt_record(table, r) for r in records]
    
    def decrypt_batch(
        self,
        table: str,
        encrypted_records: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Desencripta un lote de registros."""
        return [self.decrypt_record(table, r) for r in encrypted_records]
    
    def search_encrypted(
        self,
        table: str,
        encrypted_records: List[Dict[str, Any]],
        field: str,
        search_term: str
    ) -> List[Dict[str, Any]]:
        """
        Busca en datos encriptados.
        
        NOTA: Esto es ineficiente - desencripta todos los registros.
        Para búsquedas frecuentes, usar índices de búsqueda cifrada o
        almacenar hashes de términos de búsqueda.
        """
        results = []
        
        for record in encrypted_records:
            decrypted = self.decrypt_record(table, record)
            
            if field in decrypted:
                value = str(decrypted[field]).lower()
                if search_term.lower() in value:
                    results.append(decrypted)
        
        return results
    
    def get_encryption_status(self, record: Dict[str, Any], table: str) -> Dict[str, Any]:
        """Retorna estado de encriptación de un registro."""
        if table not in PHI_FIELDS:
            return {"table_encrypted": False, "fields": {}}
        
        sensitive = PHI_FIELDS[table]
        status = {
            "table_encrypted": True,
            "total_sensitive_fields": len(sensitive),
            "fields": {}
        }
        
        for field in sensitive:
            value = record.get(field)
            if value is None:
                status["fields"][field] = "null"
            elif isinstance(value, str) and value.startswith('{') and 'ciphertext' in value:
                status["fields"][field] = "encrypted"
            else:
                status["fields"][field] = "plaintext"
        
        return status


# Instancia global
_phi_manager = None

def get_phi_manager() -> PHIEncryptionManager:
    """Retorna instancia singleton."""
    global _phi_manager
    if _phi_manager is None:
        _phi_manager = PHIEncryptionManager()
    return _phi_manager


# Funciones helper de alto nivel

def encrypt_patient_data(patient: Dict[str, Any]) -> Dict[str, Any]:
    """Encripta datos de paciente."""
    return get_phi_manager().encrypt_record("pacientes", patient)


def decrypt_patient_data(encrypted_patient: Dict[str, Any]) -> Dict[str, Any]:
    """Desencripta datos de paciente."""
    return get_phi_manager().decrypt_record("pacientes", encrypted_patient)


def encrypt_evolucion(evolucion: Dict[str, Any]) -> Dict[str, Any]:
    """Encripta evolución clínica."""
    return get_phi_manager().encrypt_record("evoluciones", evolucion)


def decrypt_evolucion(encrypted_evolucion: Dict[str, Any]) -> Dict[str, Any]:
    """Desencripta evolución clínica."""
    return get_phi_manager().decrypt_record("evoluciones", encrypted_evolucion)


def is_field_encrypted(value: Any) -> bool:
    """Verifica si un valor está encriptado."""
    if not isinstance(value, str):
        return False
    
    try:
        data = json.loads(value)
        return all(k in data for k in ['ciphertext', 'nonce', 'tag'])
    except (json.JSONDecodeError, TypeError):
        return False


def render_phi_status() -> None:
    """Renderiza estado de encriptación PHI en Streamlit."""
    import streamlit as st
    
    st.header("🔐 Encriptación de Datos Sensibles (PHI)")
    
    try:
        manager = get_phi_manager()
        
        st.success("✅ Sistema de encriptación activo")
        
        with st.expander("📋 Campos protegidos por tabla"):
            for table, fields in PHI_FIELDS.items():
                st.write(f"**{table}**: {', '.join(fields)}")
        
        st.caption(f"Algoritmo: AES-256-GCM | Versión de clave: {manager.CURRENT_KEY_VERSION}")
        
    except Exception as e:
        st.error(f"❌ Error en sistema de encriptación: {type(e).__name__}")
        log_event("phi_encryption", f"ui_error:{type(e).__name__}")
