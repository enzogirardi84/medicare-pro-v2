"""
Configuración para ambiente de desarrollo.
"""

from config.environment import Environment


class DevelopmentConfig(Environment):
    """Configuración para desarrollo local."""
    
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    TESTING: bool = False
    
    # Logging más verbose en desarrollo
    LOG_LEVEL: str = "DEBUG"
    LOG_FORMAT: str = "text"  # Texto es más legible en desarrollo
    
    # Feature flags habilitados para desarrollo
    ENABLE_2FA: bool = False  # Deshabilitado para facilitar testing manual
    ENABLE_RATE_LIMITING: bool = False  # Deshabilitado para no bloquear desarrollo
    ENABLE_CACHE: bool = True
    ENABLE_AUDIT_LOG: bool = True
    ENABLE_NEXTGEN_API: bool = False  # Deshabilitado por defecto
    
    # Timeouts más largos para debugging
    REQUEST_TIMEOUT_SECONDS: int = 60
    SESSION_TIMEOUT_MINUTES: int = 120  # Sesiones largas en desarrollo
    
    # Base de datos local para desarrollo
    DATABASE_URL: str = "postgresql://localhost:5432/medicare_dev"
    
    # Redis local (opcional en desarrollo)
    REDIS_URL: str = "redis://localhost:6379/0"
    
    # Email - usar consola en desarrollo
    SMTP_HOST: str = "localhost"  # Usar mailcatcher o similar
    SMTP_PORT: int = 1025
    
    # CORS abierto para desarrollo
    CORS_ORIGINS: list = ["http://localhost:8501", "http://localhost:3000", "*"]
    
    # Backup menos frecuente en desarrollo
    BACKUP_INTERVAL_HOURS: int = 168  # 1 semana
    
    # Monitoreo deshabilitado en desarrollo
    METRICS_ENABLED: bool = False
    
    @property
    def DATABASE_URL(self) -> str:
        """URL de base de datos con fallback a SQLite para desarrollo rápido."""
        import os
        return os.getenv("DATABASE_URL", "sqlite:///./medicare_dev.db")
