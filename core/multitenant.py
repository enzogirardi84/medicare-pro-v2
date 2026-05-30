"""Arquitectura multi-tenancy para despliegues multi-cliente.

Cada tenant (cliente) tiene:
- Su propio archivo de configuracion en tenants/{tenant_id}/
- Su propia conexion a base de datos aislada
- Su propio branding (nombre, logo, colores)
- Logs y almacenamiento segregados

La seleccion del tenant se hace via variable de entorno MEDICARE_TENANT.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. CONFIGURACION POR TENANT
# ═══════════════════════════════════════════════════════════════════

@dataclass
class TenantConfig:
    """Configuracion especifica de un cliente (tenant)."""
    tenant_id: str
    nombre: str
    logo_pdf: str = ""  # Path al logo para PDFs
    color_primario: str = "#1e3a5f"
    color_secundario: str = "#2d5a8e"
    supabase_url: str = ""
    supabase_key: str = ""
    db_tenant_key: str = ""  # Para sharding en Supabase
    session_timeout_min: int = 480
    max_login_attempts: int = 5
    lockout_seconds: int = 300
    offline_queue_dir: str = ""
    audit_log_dir: str = ""
    upload_dir: str = ""

    @property
    def slug(self) -> str:
        return self.tenant_id.lower().replace(" ", "_")


class TenantManager:
    """Gestiona la configuracion multi-tenant.

    Lee la variable MEDICARE_TENANT para determinar el tenant activo.
    Si no se configura, usa 'default' como fallback.
    """

    TENANTS_DIR = Path(__file__).resolve().parent.parent / "tenants"

    def __init__(self):
        self._tenant_id = os.environ.get("MEDICARE_TENANT", "default").strip()
        self._tenant_id_env = os.environ.get("MEDICARE_TENANT_ID", "0").strip()
        self._config: Optional[TenantConfig] = None

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    def cargar_configuracion(self) -> TenantConfig:
        """Carga la configuracion del tenant activo.

        Orden de precedencia:
        1. Variables de entorno (produccion)
        2. Archivo tenants/{tenant_id}/config.json
        3. Valores por defecto
        """
        if self._config is not None:
            return self._config

        tenant_dir = self.TENANTS_DIR / self._tenant_id

        # Intentar cargar desde archivo JSON
        config_json_path = tenant_dir / "config.json"
        config_data: dict[str, Any] = {}

        if config_json_path.exists():
            try:
                import json
                config_data = json.loads(config_json_path.read_text(encoding="utf-8"))
            except Exception as exc:
                log_event("tenant", f"config_json_error:{type(exc).__name__}")

        # Override con variables de entorno
        env_overrides = {
            "supabase_url": os.environ.get("SUPABASE_URL"),
            "supabase_key": os.environ.get("SUPABASE_KEY"),
            "session_timeout_min": os.environ.get("SESSION_TIMEOUT_MINUTES"),
            "max_login_attempts": os.environ.get("MAX_LOGIN_ATTEMPTS"),
            "lockout_seconds": os.environ.get("LOGIN_LOCKOUT_SECONDS"),
        }

        for key, val in env_overrides.items():
            if val is not None:
                config_data[key] = val

        # Valores por defecto
        self._config = TenantConfig(
            tenant_id=self._tenant_id,
            nombre=config_data.get("nombre", f"Cliente {self._tenant_id}"),
            logo_pdf=config_data.get("logo_pdf", ""),
            color_primario=config_data.get("color_primario", "#1e3a5f"),
            color_secundario=config_data.get("color_secundario", "#2d5a8e"),
            supabase_url=config_data.get("supabase_url", os.environ.get("SUPABASE_URL", "")),
            supabase_key=config_data.get("supabase_key", os.environ.get("SUPABASE_KEY", "")),
            db_tenant_key=config_data.get("db_tenant_key", f"tenant_{self._tenant_id}"),
            session_timeout_min=int(config_data.get("session_timeout_min", 480)),
            max_login_attempts=int(config_data.get("max_login_attempts", 5)),
            lockout_seconds=int(config_data.get("lockout_seconds", 300)),
            offline_queue_dir=str(tenant_dir / "offline_queue"),
            audit_log_dir=str(tenant_dir / "audit_logs"),
            upload_dir=str(tenant_dir / "estudios"),
        )

        # Crear directorios del tenant
        for d in [self._config.offline_queue_dir, self._config.audit_log_dir, self._config.upload_dir]:
            Path(d).mkdir(parents=True, exist_ok=True)

        log_event("tenant", f"configuracion_cargada:{self._tenant_id}")
        return self._config

    def aplicar_configuracion(self) -> None:
        """Aplica la configuracion del tenant al sistema (secrets, timeouts, etc)."""
        config = self.cargar_configuracion()

        # Configurar session timeout via st.secrets simulacro
        try:
            import streamlit as st
            if config.session_timeout_min:
                st.session_state["_mc_tenant_timeout"] = config.session_timeout_min
        except Exception:
            pass

        log_event("tenant", f"configuracion_aplicada:{config.nombre}")


# ═══════════════════════════════════════════════════════════════════
# 2. EJEMPLO DE TENANT DEFAULT
# ═══════════════════════════════════════════════════════════════════

def generar_tenant_default() -> None:
    """Genera la estructura de tenant por defecto si no existe."""
    tenants_dir = TenantManager.TENANTS_DIR
    default_dir = tenants_dir / "default"
    default_dir.mkdir(parents=True, exist_ok=True)

    config_file = default_dir / "config.json"
    if not config_file.exists():
        import json
        config_file.write_text(json.dumps({
            "nombre": "MediCare PRO - Instancia Default",
            "color_primario": "#1e3a5f",
            "color_secundario": "#2d5a8e",
            "session_timeout_min": 480,
            "max_login_attempts": 5,
            "lockout_seconds": 300,
        }, indent=2), encoding="utf-8")
        log_event("tenant", "tenant_default_creado")

    # Crear directorios
    for d in ["offline_queue", "audit_logs", "estudios"]:
        (default_dir / d).mkdir(parents=True, exist_ok=True)


# ═══════════════════════════════════════════════════════════════════
# 3. FUNCION DE AYUDA PARA BRANDING EN PDFs
# ═══════════════════════════════════════════════════════════════════

def obtener_branding_tenant() -> dict[str, str]:
    """Obtiene los colores y logo del tenant actual para PDFs."""
    try:
        tm = TenantManager()
        config = tm.cargar_configuracion()
        return {
            "nombre": config.nombre,
            "color_primario": config.color_primario,
            "color_secundario": config.color_secundario,
            "logo_pdf": config.logo_pdf,
        }
    except Exception as exc:
        log_event("tenant", f"branding_error:{type(exc).__name__}")
        return {
            "nombre": "MediCare Enterprise PRO",
            "color_primario": "#1e3a5f",
            "color_secundario": "#2d5a8e",
            "logo_pdf": "",
        }
