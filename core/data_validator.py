"""
Validación de datos clínicos con schemas estrictos.

- Validación de tipos y rangos
- Sanitización de entrada
- Mensajes de error específicos por campo
- Soporte para validación condicional
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime, date
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple, Union


class ValidationSeverity(Enum):
    """Niveles de severidad de validación."""
    ERROR = "error"      # Bloquea la operación
    WARNING = "warning"  # Advierte pero permite
    INFO = "info"        # Solo informativo


@dataclass
class ValidationResult:
    """Resultado de validación de un campo."""
    field: str
    valid: bool
    value: Any
    sanitized_value: Any
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    severity: ValidationSeverity = ValidationSeverity.ERROR


@dataclass
class ValidationSchema:
    """Definición de schema para validación."""
    field: str
    field_type: type
    required: bool = True
    min_length: Optional[int] = None
    max_length: Optional[int] = None
    min_value: Optional[Union[int, float]] = None
    max_value: Optional[Union[int, float]] = None
    pattern: Optional[str] = None
    allowed_values: Optional[List[Any]] = None
    custom_validator: Optional[Callable[[Any], Tuple[bool, str]]] = None
    sanitizer: Optional[Callable[[Any], Any]] = None
    default_value: Any = None


class DataValidator:
    """
    Validador de datos clínicos con soporte para schemas complejos.
    """

    # Patrones comunes
    PATTERNS = {
        "dni": r"^\d{7,8}$",
        "cuit": r"^\d{2}-?\d{8}-?\d$",
        "telefono": r"^\+?[\d\s\-\(\)]{8,20}$",
        "email": r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        "matricula": r"^[A-Z]{1,2}\.?\s?\d{1,6}$",
        "obra_social": r"^[\w\s\-\.]{2,50}$",
    }

    def __init__(self):
        self._schemas: Dict[str, ValidationSchema] = {}
        self._custom_types: Dict[str, Callable[[Any], Any]] = {
            "dni": self._sanitize_dni,
            "telefono": self._sanitize_telefono,
            "texto": self._sanitize_texto,
            "nombre": self._sanitize_nombre,
        }

    def register_schema(self, schema: ValidationSchema):
        """Registra un schema de validación."""
        self._schemas[schema.field] = schema

    def register_schemas(self, schemas: List[ValidationSchema]):
        """Registra múltiples schemas."""
        for schema in schemas:
            self.register_schema(schema)

    def validate(
        self,
        data: Dict[str, Any],
        schema_names: Optional[List[str]] = None,
        strict: bool = False,
    ) -> Tuple[bool, Dict[str, ValidationResult]]:
        """
        Valida datos contra schemas registrados.

        Returns:
            (all_valid, results_by_field)
        """
        results: Dict[str, ValidationResult] = {}
        all_valid = True

        # Determinar qué schemas aplicar
        schemas_to_check = []
        if schema_names:
            schemas_to_check = [
                self._schemas.get(name)
                for name in schema_names
                if name in self._schemas
            ]
        else:
            schemas_to_check = list(self._schemas.values())

        # Validar cada campo
        for schema in schemas_to_check:
            result = self._validate_field(data.get(schema.field), schema)
            results[schema.field] = result

            if not result.valid and result.severity == ValidationSeverity.ERROR:
                all_valid = False

        # Validar campos extra si es estricto
        if strict:
            known_fields = set(self._schemas.keys())
            extra_fields = set(data.keys()) - known_fields
            if extra_fields:
                all_valid = False
                for field in extra_fields:
                    results[field] = ValidationResult(
                        field=field,
                        valid=False,
                        value=data[field],
                        sanitized_value=None,
                        errors=["Campo no permitido"],
                        severity=ValidationSeverity.ERROR,
                    )

        return all_valid, results

    def _validate_field(
        self,
        value: Any,
        schema: ValidationSchema,
    ) -> ValidationResult:
        """Valida un campo individual."""
        result = ValidationResult(
            field=schema.field,
            valid=True,
            value=value,
            sanitized_value=value,
        )

        # Sanitizar primero
        if schema.sanitizer:
            try:
                value = schema.sanitizer(value)
                result.sanitized_value = value
            except Exception as e:
                result.valid = False
                result.errors.append(f"Error de sanitización: {str(e)}")
                result.severity = ValidationSeverity.ERROR
                return result

        # Verificar requerido
        if schema.required and (value is None or value == ""):
            result.valid = False
            result.errors.append("Campo requerido")
            result.severity = ValidationSeverity.ERROR
            return result

        # Si es opcional y está vacío, es válido
        if not schema.required and (value is None or value == ""):
            # Usar valor por defecto si existe
            if schema.default_value is not None and value is None:
                result.sanitized_value = schema.default_value
            return result

        # Validar tipo
        if not self._check_type(value, schema.field_type):
            result.valid = False
            result.errors.append(
                f"Tipo inválido: esperado {schema.field_type.__name__}, "
                f"recibido {type(value).__name__}"
            )
            result.severity = ValidationSeverity.ERROR
            return result

        # Validar longitud (strings, listas)
        if hasattr(value, "__len__"):
            length = len(value)
            if schema.min_length is not None and length < schema.min_length:
                result.valid = False
                result.errors.append(
                    f"Longitud mínima {schema.min_length}, actual {length}"
                )
            if schema.max_length is not None and length > schema.max_length:
                result.valid = False
                result.errors.append(
                    f"Longitud máxima {schema.max_length}, actual {length}"
                )

        # Validar rangos numéricos
        if isinstance(value, (int, float)):
            if schema.min_value is not None and value < schema.min_value:
                result.valid = False
                result.errors.append(
                    f"Valor mínimo {schema.min_value}, actual {value}"
                )
            if schema.max_value is not None and value > schema.max_value:
                result.valid = False
                result.errors.append(
                    f"Valor máximo {schema.max_value}, actual {value}"
                )

        # Validar patrón regex
        if schema.pattern and isinstance(value, str):
            if not re.match(schema.pattern, value):
                result.valid = False
                result.errors.append("Formato inválido")

        # Validar valores permitidos
        if schema.allowed_values is not None:
            if value not in schema.allowed_values:
                result.valid = False
                result.errors.append(
                    f"Valor no permitido. Opciones: {schema.allowed_values}"
                )

        # Validador custom
        if schema.custom_validator:
            try:
                valid, message = schema.custom_validator(value)
                if not valid:
                    result.valid = False
                    result.errors.append(message)
            except Exception as e:
                result.valid = False
                result.errors.append(f"Error en validador: {str(e)}")

        # Determinar severidad
        if result.errors:
            result.severity = ValidationSeverity.ERROR
        elif result.warnings:
            result.severity = ValidationSeverity.WARNING

        return result

    def _check_type(self, value: Any, expected_type: type) -> bool:
        """Verifica si un valor es del tipo esperado."""
        if expected_type == str:
            return isinstance(value, str)
        elif expected_type == int:
            return isinstance(value, int) and not isinstance(value, bool)
        elif expected_type == float:
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        elif expected_type == bool:
            return isinstance(value, bool)
        elif expected_type == datetime:
            return isinstance(value, (datetime, date))
        elif expected_type == list:
            return isinstance(value, list)
        elif expected_type == dict:
            return isinstance(value, dict)
        else:
            return isinstance(value, expected_type)

    # Sanitizadores integrados

    def _sanitize_dni(self, value: Any) -> str:
        """Sanitiza DNI argentino."""
        if value is None:
            return ""
        dni = str(value).strip().replace(".", "").replace("-", "")
        if not re.match(r"^\d{7,8}$", dni):
            raise ValueError(f"DNI inválido: {value}")
        return dni

    def _sanitize_telefono(self, value: Any) -> str:
        """Sanitiza número de teléfono."""
        if value is None:
            return ""
        tel = str(value).strip()
        # Remover caracteres no numéricos excepto + al inicio
        tel = re.sub(r"[^\d+]", "", tel)
        if not re.match(r"^\+?\d{8,}$", tel):
            raise ValueError(f"Teléfono inválido: {value}")
        return tel

    def _sanitize_texto(self, value: Any) -> str:
        """Sanitiza texto general."""
        if value is None:
            return ""
        texto = str(value).strip()
        # Remover caracteres de control excepto \n y \t
        texto = "".join(
            c for c in texto
            if ord(c) >= 32 or c in "\n\t"
        )
        return texto

    def _sanitize_nombre(self, value: Any) -> str:
        """Sanitiza nombres propios."""
        if value is None:
            return ""
        nombre = self._sanitize_texto(value)
        # Capitalizar
        nombre = nombre.title()
        # Remover múltiples espacios
        nombre = " ".join(nombre.split())
        return nombre


# Schemas predefinidos para Medicare Pro

def get_paciente_schema() -> List[ValidationSchema]:
    """Schemas para validación de pacientes."""
    return [
        ValidationSchema(
            field="nombre",
            field_type=str,
            required=True,
            min_length=2,
            max_length=100,
            sanitizer=lambda x: str(x).strip().title() if x else "",
        ),
        ValidationSchema(
            field="apellido",
            field_type=str,
            required=True,
            min_length=2,
            max_length=100,
            sanitizer=lambda x: str(x).strip().title() if x else "",
        ),
        ValidationSchema(
            field="dni",
            field_type=str,
            required=True,
            pattern=r"^\d{7,8}$",
            sanitizer=lambda x: str(x).replace(".", "").replace("-", "") if x else "",
        ),
        ValidationSchema(
            field="telefono",
            field_type=str,
            required=False,
            pattern=r"^\+?[\d\s\-\(\)]{8,20}$",
        ),
        ValidationSchema(
            field="obra_social",
            field_type=str,
            required=False,
            max_length=50,
        ),
        ValidationSchema(
            field="fecha_nacimiento",
            field_type=str,
            required=False,
            pattern=r"^\d{2}/\d{2}/\d{4}$",
        ),
        ValidationSchema(
            field="alergias",
            field_type=str,
            required=False,
            max_length=500,
        ),
    ]


def get_usuario_schema() -> List[ValidationSchema]:
    """Schemas para validación de usuarios."""
    return [
        ValidationSchema(
            field="nombre",
            field_type=str,
            required=True,
            min_length=2,
            max_length=100,
        ),
        ValidationSchema(
            field="usuario_login",
            field_type=str,
            required=True,
            min_length=3,
            max_length=50,
            pattern=r"^[a-zA-Z0-9_]+$",
        ),
        ValidationSchema(
            field="email",
            field_type=str,
            required=False,
            pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$",
        ),
        ValidationSchema(
            field="matricula",
            field_type=str,
            required=False,
            max_length=20,
        ),
        ValidationSchema(
            field="rol",
            field_type=str,
            required=True,
            allowed_values=[
                "SuperAdmin", "Admin", "Coordinador", "Administrativo",
                "Medico", "Enfermeria", "Operativo", "Auditoria"
            ],
        ),
    ]


# Instancia global
_validator_instance: Optional[DataValidator] = None


def get_validator() -> DataValidator:
    """Obtiene instancia global del validador."""
    global _validator_instance
    if _validator_instance is None:
        _validator_instance = DataValidator()
        # Registrar schemas comunes
        _validator_instance.register_schemas(get_paciente_schema())
        _validator_instance.register_schemas(get_usuario_schema())
    return _validator_instance


def validate_paciente(data: Dict[str, Any]) -> Tuple[bool, Dict[str, ValidationResult]]:
    """Valida datos de paciente."""
    validator = get_validator()
    field_names = ["nombre", "apellido", "dni", "telefono", "obra_social", "fecha_nacimiento", "alergias"]
    return validator.validate(data, field_names)


def validate_usuario(data: Dict[str, Any]) -> Tuple[bool, Dict[str, ValidationResult]]:
    """Valida datos de usuario."""
    validator = get_validator()
    field_names = ["nombre", "usuario_login", "email", "matricula", "rol"]
    return validator.validate(data, field_names)


def sanitize_string(value: Any, max_length: int = 255) -> str:
    """Sanitiza una cadena de texto básica."""
    if value is None:
        return ""
    text = str(value).strip()
    # Remover caracteres de control
    text = "".join(c for c in text if ord(c) >= 32 or c in "\n\t")
    return text[:max_length]
