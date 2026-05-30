"""Firma digital de lotes offline (batch signing) para SyncManager.
Cada lote de 25 operaciones viaja firmado con ECDSA (SECP256R1).
El servidor valida la firma en el perimetro antes de procesar.
Mitiga suplantacion y ataques de inyeccion en redes moviles.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

from cryptography.hazmat.primitives import hashes
from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. ESTRUCTURA DEL LOTE FIRMADO
# ═══════════════════════════════════════════════════════════════════

@dataclass
class BatchPayload:
    """Payload de un lote de operaciones firmado."""
    batch_id: str = ""
    timestamp: float = field(default_factory=time.time)
    tenant_id: str = "default"
    profesional: str = ""
    operaciones: list[dict[str, Any]] = field(default_factory=list)
    firma_ecdsa: str = ""  # Firma del payload completo
    fingerprint_clave: str = ""  # SHA-256 de la clave publica del firmante
    version: int = 2  # Version del formato de lote

    def serializar(self) -> str:
        """Serializa el lote a JSON canonico para firma."""
        return json.dumps({
            "batch_id": self.batch_id,
            "timestamp": self.timestamp,
            "tenant_id": self.tenant_id,
            "profesional": self.profesional,
            "operaciones": self.operaciones,
            "version": self.version,
        }, sort_keys=True, ensure_ascii=False, default=str)

    def hash_hex(self) -> str:
        """Hash SHA-256 del payload serializado."""
        return hashlib.sha256(self.serializar().encode("utf-8")).hexdigest()


# ═══════════════════════════════════════════════════════════════════
# 2. FIRMA DEL LOTE EN EL CLIENTE (SyncManager)
# ═══════════════════════════════════════════════════════════════════

class BatchSigner:
    """Firma lotes de operaciones en el cliente antes de enviarlos.

    El SyncManager llama a firmar_lote() antes de la sincronizacion.
    La clave privada del profesional se usa para firmar el batch.
    """

    @staticmethod
    def firmar_lote(
        operaciones: list[dict[str, Any]],
        clave_privada_pem: bytes,
        profesional: str,
        tenant_id: str = "default",
    ) -> BatchPayload:
        """Firma un lote de operaciones con ECDSA.

        Args:
            operaciones: Lista de operaciones a sincronizar.
            clave_privada_pem: Clave privada ECDSA del profesional.
            profesional: Identificador del profesional.
            tenant_id: Tenant al que pertenecen los datos.

        Returns:
            BatchPayload con la firma ECDSA incluida.
        """
        from core.ecdsa_signature import ECDSASignatureManager, fingerprint_clave_publica

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import ec

        # Obtener fingerprint de la clave publica
        private_key = serialization.load_pem_private_key(clave_privada_pem, password=None)
        public_key = private_key.public_key()
        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        fingerprint = fingerprint_clave_publica(pub_pem)

        payload = BatchPayload(
            batch_id=f"batch_{int(time.time())}_{profesional}",
            tenant_id=tenant_id,
            profesional=profesional,
            operaciones=operaciones,
            fingerprint_clave=fingerprint,
        )

        # Firmar el hash del payload
        hash_payload = payload.hash_hex()
        signature = private_key.sign(
            hash_payload.encode("utf-8"),
            ec.ECDSA(hashes.SHA256()),
        )

        payload.firma_ecdsa = base64.b64encode(signature).decode("ascii")
        log_event("batch_signer",
                  f"lote_firmado:{payload.batch_id}:{len(operaciones)}ops:{profesional}")
        return payload

    @staticmethod
    def serializar_lote(payload: BatchPayload) -> str:
        """Serializa el lote firmado para transmision."""
        import uuid
        if not payload.batch_id:
            payload.batch_id = str(uuid.uuid4())
        return json.dumps({
            "batch_id": payload.batch_id,
            "timestamp": payload.timestamp,
            "tenant_id": payload.tenant_id,
            "profesional": payload.profesional,
            "operaciones": payload.operaciones,
            "firma_ecdsa": payload.firma_ecdsa,
            "fingerprint_clave": payload.fingerprint_clave,
            "version": payload.version,
        }, ensure_ascii=False, default=str)


# ═══════════════════════════════════════════════════════════════════
# 3. VALIDACION DEL LOTE EN EL SERVIDOR (Middleware perimetral)
# ═══════════════════════════════════════════════════════════════════

class BatchValidator:
    """Valida lotes firmados en el perimetro del servidor.

    Se ejecuta ANTES de que el lote toque el pool de PostgreSQL.
    Si la firma no coincide, el lote se descarta ATOMICAMENTE.
    """

    @staticmethod
    def parsear_lote(json_str: str) -> BatchPayload:
        """Deserializa un lote desde JSON."""
        data = json.loads(json_str)
        payload = BatchPayload(
            batch_id=data.get("batch_id", ""),
            timestamp=data.get("timestamp", 0.0),
            tenant_id=data.get("tenant_id", "default"),
            profesional=data.get("profesional", ""),
            operaciones=data.get("operaciones", []),
            firma_ecdsa=data.get("firma_ecdsa", ""),
            fingerprint_clave=data.get("fingerprint_clave", ""),
            version=data.get("version", 1),
        )
        return payload

    @staticmethod
    def validar_lote(json_str: str, clave_publica_pem: bytes) -> tuple[bool, str, Optional[BatchPayload]]:
        """Valida la firma de un lote entrante.

        Args:
            json_str: JSON del lote recibido.
            clave_publica_pem: Clave publica ECDSA del profesional.

        Returns:
            (valido, mensaje, payload) donde payload es None si es invalido.
        """
        try:
            payload = BatchValidator.parsear_lote(json_str)

            from cryptography.exceptions import InvalidSignature
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec

            # Recalcular hash del payload (sin la firma)
            hash_payload = payload.hash_hex()

            # Verificar firma
            public_key = serialization.load_pem_public_key(clave_publica_pem)
            firma_bytes = base64.b64decode(payload.firma_ecdsa)

            public_key.verify(
                firma_bytes,
                hash_payload.encode("utf-8"),
                ec.ECDSA(hashes.SHA256()),
            )

            log_event("batch_validator",
                      f"lote_valido:{payload.batch_id}:{len(payload.operaciones)}ops")
            return True, "Firma valida", payload

        except InvalidSignature:
            log_event("batch_validator",
                      f"FIRMA_INVALIDA:{payload.batch_id if 'payload' in dir() else 'unknown'}")
            return False, "Firma ECDSA invalida. El lote fue rechazado.", None

        except Exception as exc:
            log_event("batch_validator",
                      f"error_validacion:{type(exc).__name__}:{exc}")
            return False, f"Error de validacion: {exc}", None


# ═══════════════════════════════════════════════════════════════════
# 4. INTEGRACION CON SYNCMANAGER
# ═══════════════════════════════════════════════════════════════════

def procesar_lote_sincronizacion(
    json_lote: str,
    obtener_clave_publica: callable,
) -> tuple[bool, str, list[dict[str, Any]]]:
    """Pipeline completo de recepcion de lote sincronizado.

    1. Validar firma ECDSA
    2. Si invalida -> descartar lote, alertar
    3. Si valida -> procesar operaciones

    Args:
        json_lote: JSON del lote firmado recibido.
        obtener_clave_publica: Funcion que retorna la clave publica
                               del profesional (bytes PEM).

    Returns:
        (procesado, mensaje, operaciones_validas)
    """
    # Extraer profesional y tenant para buscar clave publica
    try:
        data = json.loads(json_lote)
        profesional = data.get("profesional", "")
        tenant = data.get("tenant_id", "default")
    except json.JSONDecodeError as exc:
        return False, f"JSON invalido: {exc}", []

    if not profesional:
        return False, "Profesional no especificado en el lote.", []

    # Obtener clave publica
    try:
        pub_key = obtener_clave_publica(profesional, tenant)
        if not pub_key:
            return False, f"Clave publica no encontrada para: {profesional}", []
    except Exception as exc:
        return False, f"Error obteniendo clave publica: {exc}", []

    # Validar firma
    valido, msg, payload = BatchValidator.validar_lote(json_lote, pub_key)
    if not valido:
        # Alerta critica
        try:
            from core.metrics import AlertManager
            AlertManager.disparar_alerta(
                nivel="CRITICAL",
                mensaje=f"Lote rechazado por firma invalida: {profesional} - {msg}",
                tenant=tenant,
                modulo="batch_validator",
                metrica="lote_rechazado",
            )
        except Exception:
            pass
        return False, msg, []

    # Lote valido -> retornar operaciones para procesar
    return True, f"Lote valido: {len(payload.operaciones)} operaciones", payload.operaciones
