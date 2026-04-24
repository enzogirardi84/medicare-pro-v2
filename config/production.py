"""
Configuración para ambiente de producción.

WARNING: Este archivo contiene configuraciones sensibles.
NUNCA commitear secrets reales - usar variables de entorno.
"""

import os
from config.environment import Environment


class ProductionConfig(Environment):
    """Configuración para producción."""
    
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    TESTING: bool = False
    
    # Seguridad reforzada
    SECRET_KEY: str = os.getenv("SECRET_KEY", "")
    PASSWORD_SALT: str = os.getenv("PASSWORD_SALT", "")
    
    # Logging estructurado para producción
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    LOG_TO_FILE: bool = True
    
    # Feature flags de producción
    ENABLE_2FA: bool = True
    ENABLE_RATE_LIMITING: bool = True
    ENABLE_CACHE: bool = True
    ENABLE_AUDIT_LOG: bool = True
    ENABLE_NEXTGEN_API: bool = False  # Habilitar solo cuando esté listo
    
    # Timeouts estrictos
    REQUEST_TIMEOUT_SECONDS: int = 30
    SESSION_TIMEOUT_MINUTES: int = 30
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 30
    
    # Conexión a base de datos desde variables de entorno
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_KEY: str = os.getenv("SUPABASE_KEY", "")
    
    # Redis requerido en producción
    REDIS_URL: str = os.getenv("REDIS_URL", "")
    
    # Email real en producción
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@medicare.com")
    
    # Hosts permitidos (restringir en producción)
    ALLOWED_HOSTS: list = os.getenv("ALLOWED_HOSTS", "").split(",") if os.getenv("ALLOWED_HOSTS") else []
    CORS_ORIGINS: list = os.getenv("CORS_ORIGINS", "").split(",") if os.getenv("CORS_ORIGINS") else []
    
    # Performance optimizado
    MAX_WORKERS: int = int(os.getenv("MAX_WORKERS", "8"))
    CONNECTION_POOL_SIZE: int = int(os.getenv("CONNECTION_POOL_SIZE", "20"))
    
    # Backup frecuente en producción
    BACKUP_ENABLED: bool = True
    BACKUP_INTERVAL_HOURS: int = 24
    BACKUP_RETENTION_DAYS: int = 90
    
    # Monitoreo habilitado
    HEALTH_CHECK_ENABLED: bool = True
    METRICS_ENABLED: bool = True
    SENTRY_DSN: str = os.getenv("SENTRY_DSN", "")
    
    def validate(self) -> None:
        """Valida que todas las configuraciones requeridas estén presentes."""
        required_vars = [
            "SECRET_KEY",
            "DATABASE_URL",
            "SUPABASE_URL",
            "SUPABASE_KEY",
        ]
        
        missing = []
        for var in required_vars:
            value = getattr(self, var, "")
            if not value:
                missing.append(var)
        
        if missing:
            raise ValueError(
                f"Variables de entorno faltantes en producción: {', '.join(missing)}. "
                "Configurar antes de iniciar la aplicación."
            )
    
    def __post_init__(self):
        """Validar configuración al instanciar."""
        self.validate()
