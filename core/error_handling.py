"""
Error Handling Global - Sistema profesional de manejo de errores para Medicare Pro.

Características:
- Excepciones custom por dominio
- Middleware de manejo de errores
- Fallbacks degradados
- Logging automático de errores
- Recuperación automática donde sea posible
"""

from __future__ import annotations

import functools
import logging
import traceback
from contextlib import contextmanager
from typing import Any, Callable, Dict, List, Optional, Type, Union

from core._error_types import (
    ErrorCategory,
    ErrorSeverity,
    ErrorContext,
    ErrorResult,
    MedicareError,
    DatabaseError,
    DatabaseConnectionError,
    AuthenticationError,
    AuthorizationError,
    ValidationError,
    NetworkError,
    ConfigurationError,
    BusinessLogicError,
    ExternalServiceError,
)

# Configurar logger
logger = logging.getLogger("medicare.errors")


# ============================================================
# DECORADORES DE MANEJO DE ERRORES
# ============================================================

def handle_errors(
    fallback_value: Any = None,
    log_error: bool = True,
    notify_user: bool = True,
    error_message: str = "Ha ocurrido un error. Por favor intente nuevamente."
):
    """
    Decorador para manejo automático de errores.
    
    Args:
        fallback_value: Valor a retornar si hay error
        log_error: Si debe loguear el error
        notify_user: Si debe notificar al usuario
        error_message: Mensaje genérico para el usuario
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            try:
                return func(*args, **kwargs)
            except MedicareError as e:
                if log_error:
                    log_exception(e, context={"function": func.__name__})
                if notify_user:
                    from core.ui_professional import render_alert
                    render_alert(str(e), type_="danger")
                return fallback_value
            except Exception as e:
                if log_error:
                    log_exception(e, context={"function": func.__name__})
                if notify_user:
                    from core.ui_professional import render_alert
                    render_alert(error_message, type_="danger")
                return fallback_value
        return wrapper
    return decorator


def retry_on_error(
    max_attempts: int = 3,
    delay: float = 1.0,
    exceptions: Tuple[Type[Exception], ...] = (Exception,),
    backoff: bool = True
):
    """
    Decorador para reintentar automáticamente en caso de error.
    
    Args:
        max_attempts: Número máximo de intentos
        delay: Tiempo entre intentos (segundos)
        exceptions: Tupla de excepciones a capturar
        backoff: Si usa backoff exponencial
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            import time
            
            current_delay = delay
            last_exception = None
            
            for attempt in range(1, max_attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    logger.warning(
                        f"Intento {attempt}/{max_attempts} fallido para {func.__name__}: {e}"
                    )
                    
                    if attempt < max_attempts:
                        time.sleep(current_delay)
                        if backoff:
                            current_delay *= 2
            
            # Si agotamos intentos, propagar el error
            raise last_exception
        return wrapper
    return decorator


def validate_input(validator: Callable[[Any], bool], error_message: str = "Dato inválido"):
    """Decorador para validar inputs."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            # Validar args
            for arg in args:
                if not validator(arg):
                    raise ValidationError(error_message)
            # Validar kwargs
            for key, value in kwargs.items():
                if not validator(value):
                    raise ValidationError(f"{error_message} en campo {key}")
            return func(*args, **kwargs)
        return wrapper
    return decorator


# ============================================================
# CONTEXT MANAGERS
# ============================================================

@contextmanager
def error_boundary(
    operation: str,
    fallback_value: Any = None,
    log_error: bool = True,
    suppress: bool = True
):
    """
    Context manager para envolver operaciones con manejo de errores.
    
    Uso:
        with error_boundary("guardar paciente"):
            guardar_paciente(datos)
    """
    try:
        yield
    except Exception as e:
        if log_error:
            log_exception(e, context={"operation": operation})
        
        if not suppress:
            raise
        
        logger.warning(f"Error suprimido en '{operation}': {e}")
        return fallback_value


@contextmanager
def database_transaction():
    """Context manager para transacciones de base de datos."""
    try:
        yield
    except Exception as e:
        logger.error(f"Error en transacción de base de datos: {e}")
        # Aquí iría lógica de rollback
        raise DatabaseError(f"Error en transacción: {e}") from e


# ============================================================
# FUNCIÓN DE LOGGING
# ============================================================

def log_exception(
    exception: Exception,
    context: Optional[Dict[str, Any]] = None,
    level: str = "error"
):
    """Loguea una excepción con contexto."""
    error_data = {
        "type": type(exception).__name__,
        "message": str(exception),
        "traceback": traceback.format_exc(),
        "context": context or {}
    }
    
    if isinstance(exception, MedicareError):
        error_data["error_code"] = exception.error_code
        error_data["category"] = exception.category.name
        error_data["severity"] = exception.severity.value
    
    log_func = getattr(logger, level)
    log_func(f"Exception logged: {error_data}")
    
    # Si es crítico, también guardar en archivo
    if isinstance(exception, MedicareError) and exception.severity == ErrorSeverity.CRITICAL:
        _save_critical_error(error_data)


def _save_critical_error(error_data: Dict[str, Any]):
    """Guarda errores críticos en archivo para revisión posterior."""
    import json
    from datetime import datetime
    
    try:
        with open("critical_errors.log", "a") as f:
            entry = {
                "timestamp": datetime.now().isoformat(),
                **error_data
            }
            f.write(json.dumps(entry) + "\n")
    except Exception as _exc:
        import logging
        logging.getLogger("medicare").warning(f"Fallo al escribir log_local: {type(_exc).__name__}")


# ============================================================
# HELPERS PARA STREAMLIT
# ============================================================

def safe_operation(
    operation: Callable,
    error_message: str = "Error al ejecutar operación",
    fallback_value: Any = None,
    show_error: bool = True
) -> Any:
    """
    Ejecuta una operación de forma segura en Streamlit.
    
    Args:
        operation: Función a ejecutar
        error_message: Mensaje de error para mostrar
        fallback_value: Valor a retornar si hay error
        show_error: Si mostrar error en UI
    
    Returns:
        Resultado de la operación o fallback_value
    """
    try:
        return operation()
    except Exception as e:
        log_exception(e, context={"operation": operation.__name__})
        
        if show_error:
            try:
                import streamlit as st
                st.error(f"{error_message}: {str(e)}")
            except Exception:
                pass  # Si Streamlit no está disponible
        
        return fallback_value


def validate_and_execute(
    validator: Callable[[], bool],
    operation: Callable,
    validation_error: str = "Validación fallida",
    operation_error: str = "Error en operación"
):
    """Valida antes de ejecutar."""
    try:
        if not validator():
            raise ValidationError(validation_error)
        return operation()
    except MedicareError:
        raise
    except Exception as e:
        raise BusinessLogicError(f"{operation_error}: {e}")


# ============================================================
# RECOVERY STRATEGIES
# ============================================================

class RecoveryStrategy:
    """Estrategias de recuperación ante fallos."""
    
    @staticmethod
    def fallback_to_local_storage(data_key: str) -> Optional[Any]:
        """Intenta recuperar datos del almacenamiento local."""
        try:
            import json
            from pathlib import Path
            
            local_file = Path(".streamlit/local_data.json")
            if not local_file.exists():
                return None
            
            with open(local_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            
            return data.get(data_key)
        except Exception as e:
            logger.warning(f"Fallback a local storage falló: {e}")
            return None
    
    @staticmethod
    def use_cached_value(cache_key: str) -> Optional[Any]:
        """Intenta usar valor cacheado."""
        try:
            from core.cache_manager import get_cache_manager
            cache = get_cache_manager()
            hit, value = cache.get(cache_key, "default")
            if hit:
                return value
            return None
        except Exception as e:
            logger.warning(f"Fallback a caché falló: {e}")
            return None
    
    @staticmethod
    def degrade_gracefully(operation_name: str) -> Any:
        """Degrada funcionalidad de forma controlada."""
        logger.warning(f"Degradando funcionalidad para: {operation_name}")
        return {
            "degraded": True,
            "message": "Funcionalidad limitada temporalmente",
            "operation": operation_name
        }


# ============================================================
# GLOBAL ERROR HANDLER
# ============================================================

class GlobalErrorHandler:
    """Handler global de errores para la aplicación."""
    
    _instance = None
    _error_handlers: Dict[ErrorCategory, List[Callable]] = {}
    _error_counts: Dict[str, int] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
    
    def register_handler(self, category: ErrorCategory, handler: Callable):
        """Registra un handler para una categoría de error."""
        if category not in self._error_handlers:
            self._error_handlers[category] = []
        self._error_handlers[category].append(handler)
    
    def handle(self, error: MedicareError, context: Optional[ErrorContext] = None):
        """Maneja un error usando los handlers registrados."""
        # Loguear siempre
        log_exception(error, context=context.__dict__ if context else None)
        
        # Incrementar contador
        self._error_counts[error.error_code] = self._error_counts.get(error.error_code, 0) + 1
        
        # Ejecutar handlers específicos
        handlers = self._error_handlers.get(error.category, [])
        for handler in handlers:
            try:
                handler(error, context)
            except Exception as e:
                logger.error(f"Error handler falló: {e}")
    
    def get_error_stats(self) -> Dict[str, int]:
        """Retorna estadísticas de errores."""
        return dict(self._error_counts)


# Singleton global
def get_error_handler() -> GlobalErrorHandler:
    """Obtiene la instancia global del error handler."""
    return GlobalErrorHandler()


# ============================================================
# EJEMPLO DE USO
# ============================================================

if __name__ == "__main__":
    # Ejemplo 1: Decorador
    @handle_errors(fallback_value=None, log_error=True)
    def guardar_paciente(datos: dict) -> Optional[str]:
        if not datos.get("nombre"):
            raise ValidationError("Nombre es requerido", field="nombre")
        return "paciente_123"
    
    # Ejemplo 2: Retry automático
    @retry_on_error(max_attempts=3, delay=0.5)
    def conectar_base_datos():
        # Simular fallo
        import random
        if random.random() < 0.5:
            raise NetworkError("Conexión fallida")
        return "Conectado"
    
    # Ejemplo 3: Context manager
    with error_boundary("operación crítica", fallback_value="default"):
        # Código que puede fallar
        pass
    
    print("Error handling system ready!")
