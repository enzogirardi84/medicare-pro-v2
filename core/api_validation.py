"""Validacion estricta de datos clinicos con Pydantic v2.
Sanitiza XSS, limita longitud de campos, fuerza tipos.
Protege contra inyeccion HTML/JS en evoluciones y notas.
"""
from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic.functional_validators import AfterValidator

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. SANITIZADOR XSS
# ═══════════════════════════════════════════════════════════════════

XSS_PATTERNS = re.compile(
    r"<script|javascript:|onerror=|onload=|onclick=|alert\(|"
    r"&lt;script|&#60;script|%3Cscript",
    re.IGNORECASE,
)


def sanitize_text(value: str) -> str:
    """Limpia texto de posibles ataques XSS.

    - Escapa caracteres HTML peligrosos (<, >, &, ', ")
    - Limita a 5000 caracteres
    - Normaliza whitespace
    """
    if not isinstance(value, str):
        return str(value) if value else ""

    from html import escape

    # Limitar longitud
    value = value[:5000]

    # Escapar HTML primero (neutraliza <script>, <img onerror, etc.)
    value = escape(value)

    # Remover patrones XSS en texto escapado (doble seguridad)
    value = XSS_PATTERNS.sub("", value)

    return value.strip()


def validate_positive_float(value: Optional[float]) -> Optional[float]:
    """Valida que un monto sea positivo."""
    if value is not None and value < 0:
        raise ValueError("El valor no puede ser negativo")
    return value


# ═══════════════════════════════════════════════════════════════════
# 2. MODELOS DE DATOS CLINICOS (Pydantic v2)
# ═══════════════════════════════════════════════════════════════════

class EvolucionCreate(BaseModel):
    """Modelo de creacion de evolucion clinica con sanitizacion."""
    paciente_id: str = Field(..., min_length=1, max_length=64)
    profesional_id: str = Field(..., min_length=1, max_length=64)
    nota: str = Field("", max_length=5000)
    diagnostico: str = Field("", max_length=500)
    medicacion: str = Field("", max_length=1000)
    firma_ecdsa: str = Field("", max_length=4096)

    @field_validator("nota", "diagnostico", "medicacion")
    @classmethod
    def sanitizar_xss(cls, v: str) -> str:
        return sanitize_text(v)

    @field_validator("firma_ecdsa")
    @classmethod
    def validar_firma(cls, v: str) -> str:
        if v and not v.startswith("ME"):
            log_event("validation", "firma_ecdsa_formato_invalido")
        return v


class AdministracionMedCreate(BaseModel):
    """Modelo de administracion de medicamento."""
    paciente_id: str = Field(..., min_length=1, max_length=64)
    profesional_id: str = Field(..., min_length=1, max_length=64)
    medicamento: str = Field(..., min_length=1, max_length=255)
    dosis: str = Field("", max_length=100)
    via: str = Field("", max_length=50)
    estado: str = Field("realizada", pattern=r"^(programada|realizada|omitida|suspendida)$")
    observaciones: str = Field("", max_length=2000)

    @field_validator("medicamento", "dosis", "via", "observaciones")
    @classmethod
    def sanitizar(cls, v: str) -> str:
        return sanitize_text(v)


class CheckinGPSCreate(BaseModel):
    """Modelo de check-in GPS."""
    profesional_id: str = Field(..., min_length=1, max_length=64)
    paciente_id: Optional[str] = Field(None, max_length=64)
    latitud: float = Field(..., ge=-90, le=90)
    longitud: float = Field(..., ge=-180, le=180)
    precision_metros: Optional[float] = Field(None, ge=0, le=10000)
    timestamp: Optional[datetime] = None

    @model_validator(mode="after")
    def validar_coordenadas(self) -> Any:
        if self.latitud == 0.0 and self.longitud == 0.0:
            raise ValueError("Coordenadas (0,0) no permitidas - GPS sin fix")
        return self


class BatchSyncPayload(BaseModel):
    """Payload completo del lote de sincronizacion."""
    batch_id: str = Field(..., min_length=1, max_length=64)
    tenant_id: str = Field(..., min_length=1, max_length=64)
    profesional: str = Field(..., min_length=1, max_length=64)
    firma_ecdsa: str = Field("", max_length=8192)
    operaciones: list[dict[str, Any]] = Field(..., min_length=1, max_length=50)

    @field_validator("firma_ecdsa")
    @classmethod
    def validar_firma_lote(cls, v: str) -> str:
        if v and len(v) < 20:
            raise ValueError("Firma ECDSA del lote demasiado corta")
        return v

    @field_validator("operaciones")
    @classmethod
    def validar_operaciones(cls, ops: list[dict]) -> list[dict]:
        if len(ops) > 50:
            raise ValueError("Maximo 50 operaciones por lote")
        tipos_validos = {"evolucion", "checkin", "receta", "administracion_med"}
        for i, op in enumerate(ops):
            tipo = op.get("tipo", "")
            if tipo not in tipos_validos:
                raise ValueError(f"Operacion {i}: tipo invalido '{tipo}'")
        return ops


# ═══════════════════════════════════════════════════════════════════
# 3. FUNCION DE VALIDACION EN endpoint
# ═══════════════════════════════════════════════════════════════════

def parse_and_validate(payload: dict[str, Any], model_class: type[BaseModel]) -> dict[str, Any]:
    """Valida y sanitiza un payload contra un modelo Pydantic.

    Args:
        payload: Dict con datos a validar.
        model_class: Clase Pydantic del modelo esperado.

    Returns:
        Dict validado y sanitizado.

    Raises:
        ValueError: Si la validacion falla.
    """
    try:
        validated = model_class(**payload)
        return validated.model_dump(exclude_none=True)
    except Exception as exc:
        log_event("validation", f"fallo:{model_class.__name__}:{type(exc).__name__}")
        raise ValueError(f"Datos invalidos: {exc}")
