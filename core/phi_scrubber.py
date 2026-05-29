"""PHI scrubber: elimina o enmascara datos sensibles antes de enviar a proveedores externos (IA, logs)."""

from __future__ import annotations

import re

_PHI_PATTERNS = [
    (re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"), "IP.OFUSCADA"),
    (re.compile(r"\b\d{8}\b"), "DNI_OFUSCADO"),
    (re.compile(r"DNI:\s*\S+", re.IGNORECASE), "DNI: [OFUSCADO]"),
    (re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\s?\d{4}\b"), "TARJETA_OFUSCADA"),
    (re.compile(r"\b\d{10,11}\b"), "TEL_OFUSCADO"),
    (re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"), "[EMAIL_OFUSCADO]"),
    (re.compile(r"\b(Tel(efono)?|Telef|Email|Direccion|Dirección|Contacto)\s*:?\s*\S+", re.IGNORECASE), r"\1: [OFUSCADO]"),
    (re.compile(r"\bCUIT\s*:?\s*\d{2}-\d{8}-\d{1}\b", re.IGNORECASE), "CUIT: [OFUSCADO]"),
]

def scrub_phi(text: str, replacement: str = "[PHI_OMITIDO]") -> str:
    """Reemplaza PHI en el texto con marcadores seguros.

    Args:
        text: Texto que puede contener PHI.
        replacement: Texto de reemplazo por defecto.

    Returns:
        Texto sin PHI.
    """
    if not text:
        return text
    result = text
    # Remover datos estructurados primero
    result = re.sub(
        r"(?i)\b(DNI|CUIT|CUIL|Pasaporte|Telefono|Telefono|Telef|Email|Direccion|Dirección|Contacto|Matricula)\s*[:=]\s*\S+",
        r"\1: [OFUSCADO]",
        result,
    )
    # Remover direcciones de calle
    result = re.sub(
        r"\b(Calle|Av|Avenida|Pasaje|Jujuy|San Martín|San Martin|Belgrano|Rivadavia|Sarmiento|Mitre|Alvear|Pueyrredón|Pueyrredon|Córdoba|Cordoba|Santa Fe|Corrientes|Callao|Paso|Laprida|Moreno|Belgrano|Defensa|Hipólito Yrigoyen|Buenos Aires|Rosario|CABA|La Plata|Mar del Plata)\s+\d+",
        "[DIRECCION_OFUSCADA]",
        result,
        flags=re.IGNORECASE,
    )
    # Patrones genéricos
    for pattern, replacement_text in _PHI_PATTERNS:
        result = pattern.sub(replacement_text, result)
    return result
