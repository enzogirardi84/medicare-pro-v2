"""
Configuración para ambiente de testing (CI/CD, tests unitarios).
"""

from dataclasses import dataclass

from config.environment import Environment


@dataclass
class TestingConfig(Environment):
    """Configuración para testing automatizado."""
    
    ENVIRONMENT: str = "testing"
    DEBUG: bool = False
    TESTING: bool = True
    
    # Base de datos en memoria para tests rápidos
    DATABASE_URL: str = "sqlite:///:memory:"
    
    # Deshabilitar features que no son necesarias en testing
    ENABLE_2FA: bool = False
    ENABLE_RATE_LIMITING: bool = False
    ENABLE_CACHE: bool = False
    ENABLE_AUDIT_LOG: bool = False
    ENABLE_NEXTGEN_API: bool = False
    
    # Logging mínimo en testing (solo errores)
    LOG_LEVEL: str = "ERROR"
    LOG_FORMAT: str = "text"
    
    # Timeouts cortos para tests rápidos
    REQUEST_TIMEOUT_SECONDS: int = 5
    SESSION_TIMEOUT_MINUTES: int = 5
    
    # Email simulado (no enviar mails reales)
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 1025
    
    # Redis deshabilitado en testing (usar mocks)
    REDIS_URL: str = ""
    
    # Backup deshabilitado
    BACKUP_ENABLED: bool = False
    
    # Monitoreo deshabilitado
    METRICS_ENABLED: bool = False
    
    # Workers mínimos
    MAX_WORKERS: int = 1
    CONNECTION_POOL_SIZE: int = 2
