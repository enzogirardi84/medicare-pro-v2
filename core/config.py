"""Configuración de la aplicación. Fallback seguro si no existe core/config_secure.py."""
from __future__ import annotations

import os
from typing import Any


class AppSettings:
    """Configuración con valores por defecto seguros."""

    # Ambiente
    ENVIRONMENT: str = os.getenv("MEDICARE_ENV", "production")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Supabase
    ENABLE_SUPABASE_SYNC: bool = True
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")

    # Email / SMTP
    EMAIL_ENABLED: bool = False
    SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")

    # Cache
    ENABLE_CACHE: bool = True
    REDIS_URL: str = os.getenv("REDIS_URL", "")

    # IA
    ENABLE_AI_ASSISTANT: bool = False

    # Seguridad
    ENABLE_2FA: bool = False
    SESSION_TIMEOUT_MINUTES: int = 30
    MAX_LOGIN_ATTEMPTS: int = 5

    # App
    APP_NAME: str = "Medicare Pro"
    APP_VERSION: str = "2.0.0"
    PAGE_TITLE: str = "Medicare Pro - Gestión Clínica"

    def __getattr__(self, name: str) -> Any:
        """Retorna False/None para cualquier atributo no definido."""
        return None


settings = AppSettings()
