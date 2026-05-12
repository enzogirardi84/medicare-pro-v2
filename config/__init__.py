"""
Configuración por ambiente para Medicare Pro.

Uso:
    from config import settings
    
    # Acceder a configuración
    db_url = settings.DATABASE_URL
    debug = settings.DEBUG
    
    # Verificar ambiente actual
    if settings.ENVIRONMENT == "production":
        # Lógica específica de producción
        pass
"""

import os
from typing import Any, Dict

from config.environment import Environment

# Detectar ambiente automáticamente
ENV = os.getenv("MEDICARE_ENV", "development").lower()

# Importar configuración según ambiente
if ENV == "production":
    from config.production import ProductionConfig as Config
elif ENV == "testing":
    from config.testing import TestingConfig as Config
else:
    from config.development import DevelopmentConfig as Config

# Instancia global de configuración
settings = Config()

# Helper para validar configuración requerida
def validate_required_settings():
    """Valida que todas las configuraciones requeridas estén presentes."""
    required = [
        "DATABASE_URL",
    ]
    
    if settings.ENVIRONMENT == "production":
        # En producción, requerir configuraciones adicionales
        required.extend([
            "SECRET_KEY",
            "PASSWORD_SALT",
            "SUPABASE_URL",
            "SUPABASE_KEY",
        ])
    
    missing = []
    for key in required:
        value = getattr(settings, key, None)
        if not value or value == "default":
            missing.append(key)
    
    if missing:
        raise ValueError(f"Configuraciones faltantes: {', '.join(missing)}")


# Exportar clases para testing
__all__ = [
    "settings",
    "Config",
    "Environment",
    "validate_required_settings",
]
