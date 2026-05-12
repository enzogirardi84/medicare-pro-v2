"""
Clase base para configuración por ambiente.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
import os


_INSECURE_SENTINELS = {
    "",
    "default-secret-key-change-in-production",
    "default-salt",
    "change-this-to-a-secure-random-key-in-production",
    "another-random-salt-value",
    "your-supabase-anon-key",
    "your-supabase-service-key",
    "your-api-key",
}


@dataclass
class Environment:
    """Configuración base que aplica a todos los ambientes."""
    
    # Identificación
    ENVIRONMENT: str = "base"
    DEBUG: bool = False
    TESTING: bool = False
    
    # Seguridad
    SECRET_KEY: str = field(default_factory=lambda: os.getenv("SECRET_KEY", ""))
    PASSWORD_SALT: str = field(default_factory=lambda: os.getenv("PASSWORD_SALT", ""))
    
    # Base de datos
    DATABASE_URL: str = field(default_factory=lambda: os.getenv("DATABASE_URL", ""))
    SUPABASE_URL: str = field(default_factory=lambda: os.getenv("SUPABASE_URL", ""))
    SUPABASE_KEY: str = field(default_factory=lambda: os.getenv("SUPABASE_KEY", ""))
    
    # Redis/Cache
    REDIS_URL: str = field(default_factory=lambda: os.getenv("REDIS_URL", ""))
    CACHE_TTL_SECONDS: int = 300
    
    # API NextGen
    NEXTGEN_API_URL: str = field(default_factory=lambda: os.getenv("NEXTGEN_API_URL", "http://localhost:8000"))
    NEXTGEN_API_KEY: str = field(default_factory=lambda: os.getenv("NEXTGEN_API_KEY", ""))
    
    # Email
    SMTP_HOST: str = field(default_factory=lambda: os.getenv("SMTP_HOST", ""))
    SMTP_PORT: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    SMTP_USER: str = field(default_factory=lambda: os.getenv("SMTP_USER", ""))
    SMTP_PASSWORD: str = field(default_factory=lambda: os.getenv("SMTP_PASSWORD", ""))
    EMAIL_FROM: str = field(default_factory=lambda: os.getenv("EMAIL_FROM", "noreply@medicare.local"))
    
    # Feature Flags
    ENABLE_2FA: bool = field(default_factory=lambda: os.getenv("ENABLE_2FA", "false").lower() == "true")
    ENABLE_RATE_LIMITING: bool = True
    ENABLE_CACHE: bool = True
    ENABLE_AUDIT_LOG: bool = True
    ENABLE_NEXTGEN_API: bool = field(default_factory=lambda: os.getenv("ENABLE_NEXTGEN_API", "false").lower() == "true")
    
    # Límites y timeouts
    MAX_LOGIN_ATTEMPTS: int = 5
    LOGIN_LOCKOUT_MINUTES: int = 15
    SESSION_TIMEOUT_MINUTES: int = 30
    REQUEST_TIMEOUT_SECONDS: int = 30
    
    # Logging
    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"  # json o text
    LOG_TO_FILE: bool = False
    LOG_FILE_PATH: str = "/var/log/medicare/app.log"
    
    # Performance
    MAX_WORKERS: int = 4
    CONNECTION_POOL_SIZE: int = 10
    
    # Seguridad adicional
    ALLOWED_HOSTS: List[str] = field(default_factory=lambda: ["*"])
    CORS_ORIGINS: List[str] = field(default_factory=lambda: ["*"])
    
    # Backup
    BACKUP_ENABLED: bool = True
    BACKUP_INTERVAL_HOURS: int = 24
    BACKUP_RETENTION_DAYS: int = 30
    
    # Monitoreo
    HEALTH_CHECK_ENABLED: bool = True
    METRICS_ENABLED: bool = False
    SENTRY_DSN: str = field(default_factory=lambda: os.getenv("SENTRY_DSN", ""))

    def insecure_settings(self) -> List[str]:
        """Retorna settings sensibles vacios o con placeholders conocidos."""
        values = {
            "SECRET_KEY": self.SECRET_KEY,
            "PASSWORD_SALT": self.PASSWORD_SALT,
            "SUPABASE_KEY": self.SUPABASE_KEY,
        }
        return [
            key
            for key, value in values.items()
            if str(value or "").strip() in _INSECURE_SENTINELS
        ]

    def validate_security(self) -> None:
        """Falla temprano en produccion ante secrets faltantes o placeholders."""
        if not self.is_production():
            return
        insecure = self.insecure_settings()
        if insecure:
            raise ValueError(
                "Configuracion insegura en produccion. Revisar variables: "
                + ", ".join(sorted(insecure))
            )
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Environment":
        """Crea instancia desde diccionario."""
        return cls(**data)
    
    def to_dict(self) -> Dict:
        """Exporta configuración a diccionario (sin secrets)."""
        return {
            k: v for k, v in self.__dict__.items()
            if not k.endswith("_KEY") and not k.endswith("_PASSWORD") and not k.endswith("_SECRET")
        }
    
    def is_production(self) -> bool:
        """Retorna True si es ambiente de producción."""
        return self.ENVIRONMENT == "production"
    
    def is_development(self) -> bool:
        """Retorna True si es ambiente de desarrollo."""
        return self.ENVIRONMENT == "development"
    
    def is_testing(self) -> bool:
        """Retorna True si es ambiente de testing."""
        return self.ENVIRONMENT == "testing"
