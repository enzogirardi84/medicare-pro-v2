"""Contratos de datos inmutables con Pydantic para validacion estricta.

Cada schema define el contrato de entrada para operaciones CRUD,
garantizando que ningun dato corrupto toque Supabase.
"""

from __future__ import annotations

import html
import re
from datetime import date, datetime
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, GetCoreSchemaHandler
from pydantic_core import CoreSchema, core_schema
from core.security import FieldEncryptor


class SanitizedString(str):
    """Tipo de dato que sanitiza automaticamente strings: escapa HTML, remover caracteres de control.

    Previene XSS y datos corruptos antes de que toquen la base de datos.
    """
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler: GetCoreSchemaHandler) -> CoreSchema:
        return core_schema.no_info_after_validator_function(cls.validate, core_schema.str_schema())

    @classmethod
    def validate(cls, v: str) -> str:
        if not v:
            return v
        v_clean = html.escape(str(v))
        v_clean = re.sub(r'[\x00-\x1F\x7F-\x9F]', '', v_clean)
        return v_clean.strip()


class EvolucionClinicaSchema(BaseModel):
    """Evolucion clinica con sanitizacion automatica de texto."""
    paciente_id: str
    nota_subjetiva: SanitizedString
    nota_objetiva: SanitizedString
    diagnostico: Optional[SanitizedString] = None
    firma: SanitizedString = "Sistema"


class SignosVitalesSchema(BaseModel):
    """Signos vitales con validacion clinica de rangos."""
    sistolica: int = Field(..., ge=40, le=280, description="PA Sistolica mmHg")
    diastolica: int = Field(..., ge=30, le=180, description="PA Diastolica mmHg")
    frecuencia_cardiaca: int = Field(..., ge=30, le=220, description="FC lpm")
    frecuencia_respiratoria: int = Field(..., ge=8, le=60, description="FR rpm")
    temperatura: float = Field(..., ge=34.0, le=43.0, description="Temperatura C")
    saturacion_o2: int = Field(..., ge=50, le=100, description="SpO2 %")

    @field_validator('diastolica')
    @classmethod
    def diastolica_menor_que_sistolica(cls, v, info):
        if 'sistolica' in info.data and v >= info.data['sistolica']:
            raise ValueError('PA diastolica debe ser menor que sistolica')
        return v


class EncryptedEvolucionSchema(BaseModel):
    """Evolucion clinica con cifrado automatico de campos sensibles.
    Los campos nota_se subjetiva/objetiva se cifran en memoria antes de persistir.
    """
    paciente_id: str = Field(..., min_length=1)
    diagnostico_cie10: str = Field(..., max_length=10)
    nota_subjetiva: str = Field(..., min_length=1)
    nota_objetiva: str = Field(default="")
    firma: str = Field(default="Sistema")

    @field_validator('nota_subjetiva', 'nota_objetiva')
    @classmethod
    def cifrar_campo_sensible(cls, v: str) -> str:
        if not v:
            return v
        return FieldEncryptor.encrypt_field(v)


class PacienteSchema(BaseModel):
    """Datos minimos para creacion de paciente."""
    nombre_completo: str = Field(..., min_length=2, max_length=200)
    dni: str = Field(..., min_length=6, max_length=20)
    fecha_nacimiento: Optional[str] = None
    sexo: Optional[str] = None
    obra_social: Optional[str] = None
    telefono: Optional[str] = None
    direccion: Optional[str] = None
    alergias: Optional[str] = None
    patologias: Optional[str] = None

    @field_validator('dni')
    @classmethod
    def dni_solo_digitos(cls, v):
        limpio = v.strip().replace('.', '').replace('-', '')
        if not limpio.isdigit():
            raise ValueError('DNI debe contener solo digitos')
        return limpio


class EvolucionSchema(BaseModel):
    """Evolucion clinica."""
    paciente_id: str = Field(..., min_length=1)
    nota: str = Field(..., min_length=1, max_length=10000)
    fecha: str = Field(default_factory=lambda: datetime.now().isoformat())
    firma: str = Field(default="Sistema")


class IndicacionSchema(BaseModel):
    """Indicacion medica / receta."""
    paciente_id: str = Field(..., min_length=1)
    medicamento: str = Field(..., min_length=2)
    dosis: Optional[str] = None
    via: Optional[str] = None
    frecuencia: Optional[str] = None
    medico: str = Field(..., min_length=2)


class BalanceSchema(BaseModel):
    """Balance hidrico."""
    paciente_id: str = Field(..., min_length=1)
    ingresos_ml: float = Field(..., ge=0)
    egresos_ml: float = Field(..., ge=0)
    balance: float = Field(0.0)


class EstudioSchema(BaseModel):
    """Estudio medico."""
    paciente_id: str = Field(..., min_length=1)
    tipo: str = Field(..., min_length=2)
    detalle: Optional[str] = None
