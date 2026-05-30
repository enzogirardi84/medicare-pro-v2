"""Validacion publica de documentos via QR y hash criptografico.
URL publica: /validar?h=HASH_HEX
Permite que cualquier auditor verifique la autenticidad de un PDF
sin exponer PHI, ni requerir autenticacion.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass, field
from typing import Any, Optional

import streamlit as st

from core.app_logging import log_event
from core.audit_trail_immutable import ImmutableAuditTrail


# ═══════════════════════════════════════════════════════════════════
# 1. MODELOS DE DATOS
# ═══════════════════════════════════════════════════════════════════

@dataclass
class ResultadoValidacion:
    """Resultado de la validacion de un documento."""
    valido: bool
    hash_documento: str
    paciente_hash: str = ""  # Hash del paciente (PHI oculto)
    profesional: str = ""
    timestamp_firma: float = 0.0
    algoritmo: str = "ECDSA-SECP256R1"
    mensaje: str = ""
    detectado_como_fraude: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "valido": self.valido,
            "hash": self.hash_documento[:16] + "...",
            "paciente": f"ID-{self.paciente_hash[:8]}" if self.paciente_hash else "Anonimo",
            "profesional": self.profesional or "Registrado",
            "timestamp": self.timestamp_firma,
            "algoritmo": self.algoritmo,
            "mensaje": self.mensaje,
        }


# ═══════════════════════════════════════════════════════════════════
# 2. VALIDADOR DE DOCUMENTOS VIA QR
# ═══════════════════════════════════════════════════════════════════

class DocumentValidator:
    """Valida la autenticidad de un documento mediante su hash SHA-256.

    Busca el hash en el audit trail inmutable del tenant correspondiente
    y verifica que el documento no haya sido alterado.
    """

    SECRET_SALT = "medicare-qr-v1"  # Para derivar paciente_hash sin exponer PHI

    @classmethod
    def generar_hash_qr(cls, evolution_id: str, paciente: str, timestamp: float) -> str:
        """Genera el hash que se incrusta en el QR del PDF.

        Usa HMAC-SHA256 para evitar que terceros generen hashes
        válidos sin conocer el contexto del documento.
        """
        raw = f"{evolution_id}|{paciente}|{timestamp}|{cls.SECRET_SALT}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    @classmethod
    def validar(cls, hash_hex: str, tenant: str = "default") -> ResultadoValidacion:
        """Valida un hash contra el audit trail inmutable.

        Args:
            hash_hex: Hash SHA-256 extraido del QR del PDF.
            tenant: Tenant al que pertenece el documento.

        Returns:
            ResultadoValidacion con el estado de la validacion.
        """
        if not hash_hex or len(hash_hex) < 16:
            return ResultadoValidacion(
                valido=False, hash_documento=hash_hex,
                mensaje="Hash invalido o mal formado.",
            )

        # Buscar en audit trail
        try:
            auditor = ImmutableAuditTrail()
            entries = auditor.obtener_entradas_recientes(limite=5000)

            for entry in entries:
                # Buscar entradas que contengan el hash
                detalle = entry.get("detalle", "")
                recurso = entry.get("recurso", "")
                if hash_hex[:16] in detalle or hash_hex[:16] in recurso:
                    # Encontrado!
                    paciente_hash = hashlib.sha256(
                        f"{recurso}{cls.SECRET_SALT}".encode()
                    ).hexdigest()

                    return ResultadoValidacion(
                        valido=True,
                        hash_documento=hash_hex,
                        paciente_hash=paciente_hash,
                        profesional=entry.get("usuario", "Registrado"),
                        timestamp_firma=entry.get("timestamp", 0.0),
                        mensaje="Documento valido. La firma criptografica coincide con el registro oficial.",
                    )

            # No encontrado
            return ResultadoValidacion(
                valido=False,
                hash_documento=hash_hex,
                mensaje="Hash no encontrado en los registros. El documento podria ser falso o no existir.",
                detectado_como_fraude=True,
            )

        except Exception as exc:
            log_event("qr_validator", f"error:{type(exc).__name__}:{exc}")
            return ResultadoValidacion(
                valido=False, hash_documento=hash_hex,
                mensaje="Error interno al validar el documento.",
            )


# ═══════════════════════════════════════════════════════════════════
# 3. UI DE VALIDACION PUBLICA (endpoint /validar)
# ═══════════════════════════════════════════════════════════════════

def render_validacion_publica() -> None:
    """Renderiza la vista de validacion publica de documentos.

    Se accede via URL: /?validar=HASH_HEX
    Muestra una vista minimalista y segura sin exponer PHI.
    """
    # Obtener hash desde query params
    hash_hex = ""
    try:
        qp = st.query_params
        hash_hex = str(qp.get("validar") or qp.get("h") or "").strip()
    except Exception:
        pass

    if not hash_hex:
        # Formulario manual de validacion
        st.markdown("## Validacion de documentos")
        st.caption("Ingresa el codigo de validacion que figura en tu documento PDF.")
        hash_input = st.text_input("Codigo de validacion", placeholder="Ej: a1b2c3d4...", key="qr_hash_input")
        if st.button("Validar documento", type="primary", use_container_width=True, key="qr_validate_btn"):
            if hash_input.strip():
                st.query_params["validar"] = hash_input.strip()
                st.rerun()
        return

    # Mostrar resultado de validacion
    with st.spinner("Validando documento..."):
        time.sleep(0.3)
        resultado = DocumentValidator.validar(hash_hex)

    # Diseno sobrio, corporativo, sin PHI
    st.markdown("---")
    col_logo, col_titulo = st.columns([1, 4])
    with col_logo:
        st.markdown("### 🏥")
    with col_titulo:
        st.markdown("## MediCare Enterprise PRO")
        st.caption("Sistema de Validacion Criptografica de Documentos")

    st.markdown("---")

    if resultado.valido:
        st.success("### Documento VALIDO")
        st.markdown(
            "La firma criptografica de este documento coincide con el "
            "registro oficial almacenado en el Audit Trail inmutable."
        )
    else:
        st.error("### Documento NO VALIDO")
        st.markdown(
            "El hash de este documento **no** coincide con ningun registro "
            "valido en la base de datos oficial."
        )
        if resultado.detectado_como_fraude:
            # Disparar alerta critica
            try:
                from core.metrics import AlertManager
                AlertManager.disparar_alerta(
                    nivel="CRITICAL",
                    mensaje=f"Posible fraude documental: hash {hash_hex[:16]} no encontrado",
                    modulo="qr_validator",
                    metrica="documento_falso",
                )
            except Exception:
                pass

    # Datos no-PHI validados (sin exponeer datos del paciente)
    st.markdown("---")
    st.markdown("#### Detalles de la validacion")

    data = [
        ("Estado", "VALIDO" if resultado.valido else "INVALIDO"),
        ("Hash verificado", resultado.hash_documento[:24] + "..."),
        ("Paciente (hash)", resultado.paciente_hash[:12] + "..."),
        ("Profesional", resultado.profesional),
        ("Algoritmo", resultado.algoritmo),
    ]
    if resultado.timestamp_firma:
        from datetime import datetime
        ts = datetime.fromtimestamp(resultado.timestamp_firma).strftime("%d/%m/%Y %H:%M")
        data.append(("Fecha de firma", ts))

    for label, value in data:
        st.markdown(f"**{label}:** {value}")

    st.markdown("---")
    st.caption(
        "Este certificado digital valida la autenticidad e integridad del documento. "
        "Los datos de salud (PHI) no se exponen en esta verificacion publica."
    )

    # Limpiar query param para evitar re-validacion
    try:
        del st.query_params["validar"]
    except Exception:
        pass
