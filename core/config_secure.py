"""
Configuración segura con validación estricta usando Pydantic.
Evita el hardcodeo de credenciales y valida variables de entorno.
"""
from functools import lru_cache
from typing import List, Optional
from pydantic import field_validator, SecretStr, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict
import os


class SecureSettings(BaseSettings):
    """Configuración segura - todas las credenciales son SecretStr."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )
    
    # Ambiente (default seguro: production)
    medicare_env: str = "production"
    debug: bool = False
    
    # Seguridad - SecretStr oculta los valores en logs/traces
    secret_key: SecretStr
    password_salt: SecretStr
    jwt_secret: SecretStr
    
    # Base de datos - Connection Pooling (puerto 6543 para Supabase)
    database_url: SecretStr
    supabase_url: str
    supabase_key: SecretStr
    supabase_service_key: SecretStr
    
    # Redis para caché distribuida
    redis_url: Optional[SecretStr] = None
    
    # Email
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: Optional[SecretStr] = None
    email_from: str = "noreply@medicare.local"
    
    # Auditoría
    audit_secret_key: SecretStr
    enable_audit_log: bool = True
    
    # Feature Flags
    enable_2fa: bool = False
    enable_rate_limiting: bool = True
    enable_cache: bool = True
    
    # Performance
    connection_pool_size: int = 20
    max_workers: int = 4
    db_cache_ttl_seconds: int = 300
    
    # Seguridad adicional
    allowed_hosts: List[str] = ["*"]
    cors_origins: List[str] = ["*"]
    max_login_attempts: int = 5
    login_lockout_minutes: int = 15
    session_timeout_minutes: int = 30
    
    @field_validator("medicare_env")
    @classmethod
    def validate_environment(cls, v: str) -> str:
        """Valida que el ambiente sea permitido."""
        allowed = {"development", "testing", "production", "staging"}
        v_lower = v.lower()
        if v_lower not in allowed:
            raise ValueError(f"Ambiente '{v}' no permitido. Use: {', '.join(allowed)}")
        return v_lower
    
    @field_validator("connection_pool_size")
    @classmethod
    def validate_pool_size(cls, v: int) -> int:
        """Valida tamaño del connection pool."""
        if v < 1 or v > 100:
            raise ValueError("connection_pool_size debe estar entre 1 y 100")
        return v
    
    @field_validator("supabase_url")
    @classmethod
    def validate_supabase_url(cls, v: str) -> str:
        """Valida formato de URL de Supabase."""
        if v and not v.startswith(("https://", "http://")):
            raise ValueError("supabase_url debe comenzar con https:// o http://")
        return v
    
    def is_production(self) -> bool:
        """Retorna True si es ambiente de producción."""
        return self.medicare_env == "production"
    
    def validate_production_settings(self) -> None:
        """Valida configuraciones requeridas en producción."""
        if not self.is_production():
            return
        
        required_secrets = [
            ("secret_key", "SECRET_KEY"),
            ("database_url", "DATABASE_URL"),
            ("supabase_url", "SUPABASE_URL"),
            ("supabase_key", "SUPABASE_KEY"),
            ("audit_secret_key", "AUDIT_SECRET_KEY"),
        ]
        
        missing = []
        for attr, env_name in required_secrets:
            value = getattr(self, attr)
            if isinstance(value, SecretStr):
                value = value.get_secret_value()
            if not value or value == f"change-this-to-a-secure-{env_name.lower()}-in-production":
                missing.append(env_name)
        
        if missing:
            raise ValueError(
                f"CRÍTICO - Variables faltantes en producción: {', '.join(missing)}"
            )


@lru_cache()
def get_settings() -> SecureSettings:
    """Retorna configuración cacheada (singleton)."""
    settings = SecureSettings()
    settings.validate_production_settings()
    return settings


def get_database_url_with_pool() -> str:
    """
    Retorna URL de base de datos optimizada para connection pooling.
    Para Supabase, usa el puerto 6543 del pooler de conexiones.
    """
    settings = get_settings()
    url = settings.database_url.get_secret_value()
    
    # Si es Supabase y no tiene el puerto de pool, sugerirlo
    if "supabase.co" in url and ":5432" in url:
        # Log warning pero no modificar automáticamente
        import logging
        logger = logging.getLogger(__name__)
        logger.warning(
            "Se detectó URL de Supabase sin connection pool. "
            "Considere usar puerto 6543 para mejor performance."
        )
    
    return url


# Instancia global
secure_config = get_settings()
