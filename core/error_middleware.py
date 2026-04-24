"""
Middleware global de manejo de errores para Medicare Pro.

Proporciona:
- Captura global de excepciones
- Mapeo automático a excepciones custom
- Fallbacks degradados (graceful degradation)
- Logging estructurado de errores
- Respuestas amigables al usuario
"""

from __future__ import annotations

import functools
import traceback
from typing import Any, Callable, Dict, Optional, Type, Union

from core._error_types import (
    AuthenticationError,
    AuthorizationError,
    BusinessLogicError,
    ConfigurationError,
    DatabaseConnectionError,
    DatabaseError,
    ErrorCategory,
    ErrorResult,
    ErrorSeverity,
    ExternalServiceError,
    MedicareError,
    NetworkError,
    ValidationError,
)
from core.app_logging import log_event


# Mapeo de excepciones nativas a excepciones custom
EXCEPTION_MAPPING: Dict[Type[Exception], Type[MedicareError]] = {
    ConnectionError: NetworkError,
    TimeoutError: NetworkError,
    PermissionError: AuthorizationError,
    ValueError: ValidationError,
    KeyError: ValidationError,
    TypeError: ValidationError,
}


def map_exception_to_custom(exc: Exception) -> MedicareError:
    """Mapea una excepción nativa a una excepción custom de Medicare."""
    exc_type = type(exc)
    
    # Buscar mapeo directo
    if exc_type in EXCEPTION_MAPPING:
        custom_class = EXCEPTION_MAPPING[exc_type]
        return custom_class(str(exc))
    
    # Excepciones de base de datos comunes
    if "supabase" in str(exc).lower() or "postgresql" in str(exc).lower():
        if "connection" in str(exc).lower():
            return DatabaseConnectionError(str(exc))
        return DatabaseError(str(exc))
    
    # Excepciones de red
    if any(kw in str(exc).lower() for kw in ["network", "timeout", "connection", "dns"]):
        return NetworkError(str(exc))
    
    # Por defecto, crear MedicareError genérico
    return MedicareError(
        message=str(exc),
        error_code=f"NATIVE_{exc_type.__name__.upper()}",
        category=ErrorCategory.UNKNOWN,
        severity=ErrorSeverity.MEDIUM,
        details={"original_type": exc_type.__name__}
    )


class ErrorMiddleware:
    """
    Middleware central de manejo de errores.
    
    Captura excepciones, las clasifica, loguea y proporciona
    respuestas estructuradas para el usuario.
    """
    
    def __init__(self):
        self._fallback_handlers: Dict[ErrorCategory, Callable] = {}
        self._error_counts: Dict[str, int] = {}
    
    def register_fallback(self, category: ErrorCategory, handler: Callable):
        """Registra un handler de fallback para una categoría de error."""
        self._fallback_handlers[category] = handler
    
    def handle_error(
        self,
        exc: Exception,
        context: Optional[Dict[str, Any]] = None,
        user_message: Optional[str] = None
    ) -> ErrorResult:
        """
        Maneja una excepción y retorna un ErrorResult estructurado.
        
        Args:
            exc: La excepción capturada
            context: Contexto adicional (user_id, operation, etc.)
            user_message: Mensaje alternativo para el usuario
        
        Returns:
            ErrorResult con información estructurada del error
        """
        context = context or {}
        
        # Convertir a excepción custom si no lo es
        if isinstance(exc, MedicareError):
            custom_exc = exc
        else:
            custom_exc = map_exception_to_custom(exc)
        
        # Actualizar contador de errores
        error_key = f"{custom_exc.category.name}.{custom_exc.error_code}"
        self._error_counts[error_key] = self._error_counts.get(error_key, 0) + 1
        
        # Logging estructurado
        self._log_error(custom_exc, context)
        
        # Determinar mensaje para el usuario
        message = user_message or self._get_user_message(custom_exc)
        
        # Construir resultado
        result = ErrorResult(
            success=False,
            error_code=custom_exc.error_code,
            message=message,
            category=custom_exc.category,
            severity=custom_exc.severity,
            details={
                **custom_exc.details,
                "traceback": traceback.format_exc(),
                "error_count": self._error_counts[error_key]
            },
            recovery_action=custom_exc.recovery_action
        )
        
        # Intentar fallback si existe
        if custom_exc.category in self._fallback_handlers:
            try:
                fallback_result = self._fallback_handlers[custom_exc.category](custom_exc)
                if fallback_result is not None:
                    # El fallback pudo recuperar la operación
                    result.success = True
                    result.details["fallback_applied"] = True
            except Exception as fallback_exc:
                result.details["fallback_error"] = str(fallback_exc)
        
        return result
    
    def _log_error(self, exc: MedicareError, context: Dict[str, Any]):
        """Loguea el error de forma estructurada."""
        log_data = {
            "error_code": exc.error_code,
            "category": exc.category.name,
            "severity": exc.severity.value,
            "message": str(exc),
            "context": context,
            "traceback": traceback.format_exc()
        }
        
        # Log según severidad
        if exc.severity == ErrorSeverity.CRITICAL:
            log_event("error_critical", str(log_data))
        elif exc.severity == ErrorSeverity.HIGH:
            log_event("error_high", str(log_data))
        else:
            log_event("error", str(log_data))
    
    def _get_user_message(self, exc: MedicareError) -> str:
        """Genera un mensaje amigable para el usuario según la categoría."""
        messages = {
            ErrorCategory.DATABASE: "Hubo un problema con la base de datos. Intente nuevamente en unos momentos.",
            ErrorCategory.AUTHENTICATION: "Error de autenticación. Verifique sus credenciales.",
            ErrorCategory.AUTHORIZATION: "No tiene permisos para realizar esta acción.",
            ErrorCategory.VALIDATION: "Los datos ingresados no son válidos. Verifique e intente nuevamente.",
            ErrorCategory.NETWORK: "Problema de conexión. Verifique su conexión a internet.",
            ErrorCategory.CONFIGURATION: "Error de configuración del sistema. Contacte al administrador.",
            ErrorCategory.EXTERNAL_SERVICE: "El servicio externo no está disponible. Intente más tarde.",
            ErrorCategory.BUSINESS_LOGIC: "No se puede realizar esta operación con los datos actuales.",
            ErrorCategory.UNKNOWN: "Ocurrió un error inesperado. Intente nuevamente.",
        }
        
        return messages.get(exc.category, messages[ErrorCategory.UNKNOWN])
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Retorna estadísticas de errores."""
        return {
            "total_errors": sum(self._error_counts.values()),
            "error_counts": dict(self._error_counts),
            "registered_fallbacks": list(self._fallback_handlers.keys())
        }


# Singleton global
_middleware_instance: Optional[ErrorMiddleware] = None


def get_error_middleware() -> ErrorMiddleware:
    """Obtiene instancia global del middleware de errores."""
    global _middleware_instance
    if _middleware_instance is None:
        _middleware_instance = ErrorMiddleware()
    return _middleware_instance


def handle_error(
    exc: Exception,
    context: Optional[Dict[str, Any]] = None,
    user_message: Optional[str] = None
) -> ErrorResult:
    """
    Función helper para manejar errores usando el middleware global.
    
    Uso:
        try:
            resultado = operacion_riesgosa()
        except Exception as e:
            error_result = handle_error(e, context={"user_id": "123"})
            st.error(error_result.message)
    """
    return get_error_middleware().handle_error(exc, context, user_message)


def with_error_handling(
    fallback_return: Any = None,
    context: Optional[Dict[str, Any]] = None,
    user_message: Optional[str] = None
):
    """
    Decorador para envolver funciones con manejo de errores automático.
    
    Uso:
        @with_error_handling(fallback_return=None)
        def mi_funcion():
            return operacion_riesgosa()
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except Exception as exc:
                error_result = handle_error(
                    exc,
                    context=context or {},
                    user_message=user_message
                )
                
                # Si hay fallback configurado y el error no fue recuperable, usar fallback_return
                if not error_result.success and fallback_return is not None:
                    return fallback_return
                
                # Re-lanzar como MedicareError para manejo upstream
                raise MedicareError(
                    message=error_result.message,
                    error_code=error_result.error_code,
                    category=error_result.category,
                    severity=error_result.severity,
                    details=error_result.details
                )
        return wrapper
    return decorator


def safe_execute(
    func: Callable,
    *args,
    fallback_return: Any = None,
    context: Optional[Dict[str, Any]] = None,
    **kwargs
) -> Any:
    """
    Ejecuta una función de forma segura con manejo de errores.
    
    Uso:
        resultado = safe_execute(
            cargar_datos_paciente,
            paciente_id="123",
            fallback_return={},
            context={"operation": "load_patient"}
        )
    """
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        error_result = handle_error(exc, context)
        
        if fallback_return is not None:
            log_event("error_fallback", f"Usando fallback para {func.__name__}: {error_result.error_code}")
            return fallback_return
        
        # Re-lanzar para manejo upstream
        raise


# ============================================================
# FALLBACKS DEGRADADOS POR CATEGORÍA
# ============================================================

def register_default_fallbacks():
    """Registra los fallbacks degradados por defecto."""
    middleware = get_error_middleware()
    
    # Fallback para errores de base de datos: usar caché local
    def db_fallback(exc: DatabaseError) -> Optional[Any]:
        log_event("fallback_db", "Intentando usar datos en caché local")
        # Aquí se implementaría lógica de caché
        return None  # Por ahora, no recuperable
    
    middleware.register_fallback(ErrorCategory.DATABASE, db_fallback)
    
    # Fallback para errores de red: operar en modo offline
    def network_fallback(exc: NetworkError) -> Optional[Any]:
        log_event("fallback_network", "Operando en modo offline limitado")
        # Aquí se implementaría lógica offline
        return None
    
    middleware.register_fallback(ErrorCategory.NETWORK, network_fallback)
    
    # Fallback para servicios externos: usar datos locales
    def external_fallback(exc: ExternalServiceError) -> Optional[Any]:
        log_event("fallback_external", f"Servicio {exc.details.get('service')} no disponible, usando datos locales")
        return None
    
    middleware.register_fallback(ErrorCategory.EXTERNAL_SERVICE, external_fallback)


# Auto-registrar fallbacks al importar
register_default_fallbacks()
