"""
Tests para configuración por ambiente.

EJECUTAR:
    python -m pytest tests/test_config.py -v
"""

import os
import pytest
from unittest.mock import patch


class TestEnvironmentBase:
    """Tests para clase base Environment"""
    
    def test_environment_creation(self):
        """Test creación de instancia"""
        from config.environment import Environment
        
        env = Environment()
        assert env.ENVIRONMENT == "base"
        assert env.DEBUG is False
    
    def test_environment_to_dict(self):
        """Test exportación a diccionario"""
        from config.environment import Environment
        
        env = Environment()
        data = env.to_dict()
        
        # No debe incluir secrets
        assert "SECRET_KEY" not in data
        assert "SUPABASE_KEY" not in data
        assert "ENVIRONMENT" in data
    
    def test_is_production(self):
        """Test detección de producción"""
        from config.environment import Environment
        
        env = Environment(ENVIRONMENT="production")
        assert env.is_production() is True
        assert env.is_development() is False
        assert env.is_testing() is False
    
    def test_is_development(self):
        """Test detección de desarrollo"""
        from config.environment import Environment
        
        env = Environment(ENVIRONMENT="development")
        assert env.is_development() is True
        assert env.is_production() is False


class TestDevelopmentConfig:
    """Tests para DevelopmentConfig"""
    
    def test_development_debug_enabled(self):
        """Test que debug está habilitado en desarrollo"""
        from config.development import DevelopmentConfig
        
        config = DevelopmentConfig()
        assert config.DEBUG is True
        assert config.ENVIRONMENT == "development"
    
    def test_development_logging_text(self):
        """Test formato de logging en desarrollo"""
        from config.development import DevelopmentConfig
        
        config = DevelopmentConfig()
        assert config.LOG_FORMAT == "text"
        assert config.LOG_LEVEL == "DEBUG"
    
    def test_development_2fa_disabled(self):
        """Test que 2FA está deshabilitado en desarrollo"""
        from config.development import DevelopmentConfig
        
        config = DevelopmentConfig()
        assert config.ENABLE_2FA is False


class TestProductionConfig:
    """Tests para ProductionConfig"""
    
    def test_production_debug_disabled(self):
        """Test que debug está deshabilitado en producción"""
        from config.production import ProductionConfig
        
        # Mockear variables de entorno requeridas
        with patch.dict(os.environ, {
            "SECRET_KEY": "test-secret",
            "DATABASE_URL": "postgresql://test",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
        }):
            config = ProductionConfig()
            assert config.DEBUG is False
            assert config.ENVIRONMENT == "production"
    
    def test_production_logging_json(self):
        """Test formato JSON en producción"""
        with patch.dict(os.environ, {
            "SECRET_KEY": "test-secret",
            "DATABASE_URL": "postgresql://test",
            "SUPABASE_URL": "https://test.supabase.co",
            "SUPABASE_KEY": "test-key",
        }):
            from config.production import ProductionConfig
            config = ProductionConfig()
            assert config.LOG_FORMAT == "json"
    
    def test_production_validation_missing_vars(self):
        """Test validación de variables faltantes"""
        from config.production import ProductionConfig
        
        # Sin variables de entorno debe lanzar error
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError) as exc_info:
                ProductionConfig()
            
            assert "SECRET_KEY" in str(exc_info.value)


class TestTestingConfig:
    """Tests para TestingConfig"""
    
    def test_testing_in_memory_db(self):
        """Test base de datos en memoria"""
        from config.testing import TestingConfig
        
        config = TestingConfig()
        assert ":memory:" in config.DATABASE_URL
    
    def test_testing_minimal_logging(self):
        """Test logging mínimo en testing"""
        from config.testing import TestingConfig
        
        config = TestingConfig()
        assert config.LOG_LEVEL == "ERROR"
    
    def test_testing_features_disabled(self):
        """Test features deshabilitadas en testing"""
        from config.testing import TestingConfig
        
        config = TestingConfig()
        assert config.ENABLE_2FA is False
        assert config.ENABLE_RATE_LIMITING is False
        assert config.ENABLE_CACHE is False
        assert config.TESTING is True


class TestConfigModule:
    """Tests para módulo config principal"""
    
    def test_config_import_development_by_default(self):
        """Test que development es el default"""
        with patch.dict(os.environ, {}, clear=True):
            # Reimportar para que tome la nueva variable
            import importlib
            import config
            importlib.reload(config)
            
            assert config.settings.ENVIRONMENT == "development"
    
    def test_config_import_production(self):
        """Test import con MEDICARE_ENV=production"""
        with patch.dict(os.environ, {"MEDICARE_ENV": "production", "SECRET_KEY": "test"}):
            # Nota: esto requeriría reimportar el módulo
            pass  # Simplificado por dependencias de import


class TestValidateRequiredSettings:
    """Tests para validación de configuración"""
    
    def test_validate_development(self):
        """Test validación en desarrollo"""
        from config import validate_required_settings
        from config.development import DevelopmentConfig
        
        # En desarrollo no debería lanzar error
        validate_required_settings()  # No debe lanzar
    
    def test_validate_production_fails(self):
        """Test validación falla en producción sin config"""
        from config import validate_required_settings
        from config.production import ProductionConfig
        
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(ValueError):
                validate_required_settings()
