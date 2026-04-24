"""
Tests para el middleware de manejo de errores

EJECUTAR:
    python -m pytest tests/test_error_middleware.py -v
"""

import pytest
from unittest.mock import Mock, patch


class TestMapExceptionToCustom:
    """Tests para mapeo de excepciones"""
    
    def test_connection_error_to_network(self):
        """Test que ConnectionError se mapea a NetworkError"""
        from core.error_middleware import map_exception_to_custom
        from core._error_types import NetworkError
        
        exc = ConnectionError("Connection refused")
        custom = map_exception_to_custom(exc)
        
        assert isinstance(custom, NetworkError)
    
    def test_permission_error_to_authorization(self):
        """Test que PermissionError se mapea a AuthorizationError"""
        from core.error_middleware import map_exception_to_custom
        from core._error_types import AuthorizationError
        
        exc = PermissionError("Access denied")
        custom = map_exception_to_custom(exc)
        
        assert isinstance(custom, AuthorizationError)
    
    def test_value_error_to_validation(self):
        """Test que ValueError se mapea a ValidationError"""
        from core.error_middleware import map_exception_to_custom
        from core._error_types import ValidationError
        
        exc = ValueError("Invalid value")
        custom = map_exception_to_custom(exc)
        
        assert isinstance(custom, ValidationError)
    
    def test_supabase_error_to_database(self):
        """Test que errores de Supabase se mapean a DatabaseError"""
        from core.error_middleware import map_exception_to_custom
        from core._error_types import DatabaseError
        
        exc = Exception("Supabase connection failed")
        custom = map_exception_to_custom(exc)
        
        assert isinstance(custom, DatabaseError)


class TestErrorMiddleware:
    """Tests para ErrorMiddleware"""
    
    def test_handle_error_creates_result(self):
        """Test que handle_error crea ErrorResult"""
        from core.error_middleware import ErrorMiddleware
        from core._error_types import ValidationError
        
        middleware = ErrorMiddleware()
        exc = ValidationError("Campo requerido", field="nombre")
        
        result = middleware.handle_error(exc)
        
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"
        assert result.category.name == "VALIDATION"
    
    def test_handle_error_counts_errors(self):
        """Test que cuenta errores por tipo"""
        from core.error_middleware import ErrorMiddleware
        from core._error_types import ValidationError
        
        middleware = ErrorMiddleware()
        exc = ValidationError("Error 1")
        
        middleware.handle_error(exc)
        middleware.handle_error(exc)
        
        stats = middleware.get_error_stats()
        assert stats["total_errors"] == 2
    
    def test_handle_error_native_exception(self):
        """Test que maneja excepciones nativas"""
        from core.error_middleware import ErrorMiddleware
        
        middleware = ErrorMiddleware()
        exc = ValueError("Test error")
        
        result = middleware.handle_error(exc)
        
        assert result.success is False
        assert result.error_code == "VALIDATION_ERROR"
    
    def test_register_fallback(self):
        """Test registro de fallback handler"""
        from core.error_middleware import ErrorMiddleware
        from core._error_types import ErrorCategory, DatabaseError
        
        middleware = ErrorMiddleware()
        
        def dummy_fallback(exc):
            return "recovered"
        
        middleware.register_fallback(ErrorCategory.DATABASE, dummy_fallback)
        
        stats = middleware.get_error_stats()
        assert ErrorCategory.DATABASE in stats["registered_fallbacks"]


class TestHandleErrorHelper:
    """Tests para función helper handle_error"""
    
    def test_handle_error_helper(self):
        """Test función helper global"""
        from core.error_middleware import handle_error
        from core._error_types import ValidationError
        
        exc = ValidationError("Test")
        result = handle_error(exc, context={"user_id": "123"})
        
        assert result.success is False
        assert "user_id" in str(result.details.get("context", {}))


class TestWithErrorHandlingDecorator:
    """Tests para decorador with_error_handling"""
    
    def test_decorator_success(self):
        """Test decorador con función exitosa"""
        from core.error_middleware import with_error_handling
        
        @with_error_handling(fallback_return="fallback")
        def success_func():
            return "success"
        
        result = success_func()
        assert result == "success"
    
    def test_decorator_with_error_and_fallback(self):
        """Test decorador con error usando fallback"""
        from core.error_middleware import with_error_handling
        from core._error_types import MedicareError
        
        @with_error_handling(fallback_return="fallback_value")
        def error_func():
            raise ValueError("Test error")
        
        # Como tiene fallback, no debería lanzar excepción
        result = error_func()
        assert result == "fallback_value"
    
    def test_decorator_with_error_no_fallback(self):
        """Test decorador con error sin fallback"""
        from core.error_middleware import with_error_handling
        from core._error_types import MedicareError
        
        @with_error_handling()  # Sin fallback
        def error_func():
            raise ValueError("Test error")
        
        # Debería lanzar MedicareError
        with pytest.raises(MedicareError):
            error_func()


class TestSafeExecute:
    """Tests para safe_execute"""
    
    def test_safe_execute_success(self):
        """Test ejecución exitosa"""
        from core.error_middleware import safe_execute
        
        def success_func(arg1, arg2):
            return arg1 + arg2
        
        result = safe_execute(success_func, 1, 2)
        assert result == 3
    
    def test_safe_execute_with_fallback(self):
        """Test ejecución con fallback"""
        from core.error_middleware import safe_execute
        
        def error_func():
            raise ValueError("Error")
        
        result = safe_execute(error_func, fallback_return="default")
        assert result == "default"
    
    def test_safe_execute_without_fallback_raises(self):
        """Test que lanza excepción sin fallback"""
        from core.error_middleware import safe_execute
        
        def error_func():
            raise ValueError("Error")
        
        with pytest.raises(ValueError):
            safe_execute(error_func)


class TestUserMessages:
    """Tests para mensajes de usuario"""
    
    def test_database_error_message(self):
        """Test mensaje para error de base de datos"""
        from core.error_middleware import ErrorMiddleware
        from core._error_types import DatabaseError
        
        middleware = ErrorMiddleware()
        result = middleware.handle_error(DatabaseError("DB error"))
        
        assert "base de datos" in result.message.lower()
    
    def test_auth_error_message(self):
        """Test mensaje para error de autenticación"""
        from core.error_middleware import ErrorMiddleware
        from core._error_types import AuthenticationError
        
        middleware = ErrorMiddleware()
        result = middleware.handle_error(AuthenticationError("Auth failed"))
        
        assert "credenciales" in result.message.lower()
    
    def test_network_error_message(self):
        """Test mensaje para error de red"""
        from core.error_middleware import ErrorMiddleware
        from core._error_types import NetworkError
        
        middleware = ErrorMiddleware()
        result = middleware.handle_error(NetworkError("Network down"))
        
        assert "conexión" in result.message.lower()


class TestErrorStats:
    """Tests para estadísticas de errores"""
    
    def test_error_stats_structure(self):
        """Test estructura de estadísticas"""
        from core.error_middleware import ErrorMiddleware
        from core._error_types import ValidationError
        
        middleware = ErrorMiddleware()
        middleware.handle_error(ValidationError("Error 1"))
        
        stats = middleware.get_error_stats()
        
        assert "total_errors" in stats
        assert "error_counts" in stats
        assert "registered_fallbacks" in stats
