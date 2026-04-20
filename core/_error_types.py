"""Tipos, enums y excepciones de error. Extraído de core/error_handling.py."""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Dict, Optional


class ErrorCategory(Enum):
    """Categorías de error para clasificación."""
    DATABASE = auto()
    AUTHENTICATION = auto()
    AUTHORIZATION = auto()
    VALIDATION = auto()
    NETWORK = auto()
    CONFIGURATION = auto()
    BUSINESS_LOGIC = auto()
    EXTERNAL_SERVICE = auto()
    UNKNOWN = auto()


class ErrorSeverity(Enum):
    """Severidad del error."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class ErrorContext:
    """Contexto enriquecido del error."""
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    endpoint: Optional[str] = None
    operation: Optional[str] = None
    extra_data: Optional[Dict[str, Any]] = None


@dataclass
class ErrorResult:
    """Resultado estructurado de un error."""
    success: bool
    error_code: str
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    details: Optional[Dict[str, Any]] = None
    recovery_action: Optional[str] = None


# ============================================================
# EXCEPCIONES CUSTOM
# ============================================================

class MedicareError(Exception):
    """Excepción base del sistema."""

    def __init__(
        self,
        message: str,
        error_code: str = "UNKNOWN_ERROR",
        category: ErrorCategory = ErrorCategory.UNKNOWN,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        details: Optional[Dict[str, Any]] = None,
        recovery_action: Optional[str] = None
    ):
        super().__init__(message)
        self.error_code = error_code
        self.category = category
        self.severity = severity
        self.details = details or {}
        self.recovery_action = recovery_action

    def to_dict(self) -> Dict[str, Any]:
        return {
            "error_code": self.error_code,
            "message": str(self),
            "category": self.category.name,
            "severity": self.severity.value,
            "details": self.details,
            "recovery_action": self.recovery_action
        }


class DatabaseError(MedicareError):
    """Errores de base de datos."""

    def __init__(self, message: str, details: Optional[Dict] = None):
        super().__init__(
            message=message,
            error_code="DB_ERROR",
            category=ErrorCategory.DATABASE,
            severity=ErrorSeverity.HIGH,
            details=details,
            recovery_action="Verificar conexión a Supabase/PostgreSQL"
        )


class DatabaseConnectionError(DatabaseError):
    """Error de conexión a base de datos."""

    def __init__(self, message: str = "No se pudo conectar a la base de datos"):
        super().__init__(
            message=message,
            details={"suggestion": "Verificar credenciales y red"}
        )
        self.error_code = "DB_CONNECTION_ERROR"
        self.severity = ErrorSeverity.CRITICAL


class AuthenticationError(MedicareError):
    """Errores de autenticación."""

    def __init__(self, message: str = "Error de autenticación"):
        super().__init__(
            message=message,
            error_code="AUTH_ERROR",
            category=ErrorCategory.AUTHENTICATION,
            severity=ErrorSeverity.HIGH,
            recovery_action="Verificar credenciales e intentar nuevamente"
        )


class AuthorizationError(MedicareError):
    """Errores de autorización (permisos)."""

    def __init__(self, message: str = "No tiene permisos para esta acción"):
        super().__init__(
            message=message,
            error_code="FORBIDDEN",
            category=ErrorCategory.AUTHORIZATION,
            severity=ErrorSeverity.HIGH,
            recovery_action="Contactar al administrador del sistema"
        )


class ValidationError(MedicareError):
    """Errores de validación de datos."""

    def __init__(self, message: str, field: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="VALIDATION_ERROR",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.MEDIUM,
            details={"field": field} if field else None,
            recovery_action="Corregir los datos ingresados"
        )


class NetworkError(MedicareError):
    """Errores de red."""

    def __init__(self, message: str = "Error de conexión de red"):
        super().__init__(
            message=message,
            error_code="NETWORK_ERROR",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.HIGH,
            recovery_action="Verificar conexión a internet e intentar nuevamente"
        )


class ConfigurationError(MedicareError):
    """Errores de configuración."""

    def __init__(self, message: str, config_key: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="CONFIG_ERROR",
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.CRITICAL,
            details={"config_key": config_key} if config_key else None,
            recovery_action="Verificar archivo de configuración"
        )


class BusinessLogicError(MedicareError):
    """Errores de lógica de negocio."""

    def __init__(self, message: str, rule: Optional[str] = None):
        super().__init__(
            message=message,
            error_code="BUSINESS_RULE_ERROR",
            category=ErrorCategory.BUSINESS_LOGIC,
            severity=ErrorSeverity.MEDIUM,
            details={"rule": rule} if rule else None
        )


class ExternalServiceError(MedicareError):
    """Errores de servicios externos."""

    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"Error en {service}: {message}",
            error_code="EXTERNAL_SERVICE_ERROR",
            category=ErrorCategory.EXTERNAL_SERVICE,
            severity=ErrorSeverity.HIGH,
            details={"service": service},
            recovery_action="El servicio externo está experimentando problemas. Intente más tarde."
        )
