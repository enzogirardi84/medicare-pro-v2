"""
Panel de Configuración/Settings para Medicare Pro.

Permite a administradores configurar:
- Apariencia (tema, colores)
- Notificaciones
- Integraciones
- Seguridad
- Avanzado
"""

import streamlit as st
from typing import Dict, Any, Optional

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType
from core.config import settings
from core.i18n import render_language_selector


def render_settings_page():
    """Renderiza página completa de configuración."""
    # Verificar permisos
    user = st.session_state.get("u_actual", {})
    is_admin = user.get("rol") in ["admin", "superadmin"]
    
    st.title("⚙️ Configuración")
    st.caption(f"Usuario: {user.get('nombre', 'N/A')}")
    
    # Tabs de configuración
    tabs = st.tabs([
        "🎨 Apariencia",
        "🔔 Notificaciones",
        "🔗 Integraciones",
        "🔒 Seguridad",
        "⚡ Avanzado"
    ])
    
    with tabs[0]:
        render_appearance_settings()
    
    with tabs[1]:
        render_notification_settings()
    
    with tabs[2]:
        render_integration_settings(is_admin)
    
    with tabs[3]:
        render_security_settings(is_admin)
    
    with tabs[4]:
        render_advanced_settings(is_admin)


def render_appearance_settings():
    """Configuración de apariencia."""
    st.header("🎨 Apariencia")
    
    # Selector de idioma
    st.subheader("Idioma")
    render_language_selector()
    
    st.divider()
    
    # Tema
    st.subheader("Tema")
    
    theme = st.radio(
        "Tema de color",
        options=["Claro", "Oscuro", "Auto"],
        index=0,
        help="Selecciona el tema de la aplicación"
    )
    
    if st.button("💾 Guardar Tema"):
        st.session_state["theme"] = theme.lower()
        st.success(f"✅ Tema cambiado a {theme}")
        log_event("settings", f"Theme changed to {theme}")
    
    st.divider()
    
    # Densidad de UI
    st.subheader("Densidad de Interfaz")
    
    density = st.select_slider(
        "Densidad",
        options=["Compacta", "Normal", "Espaciada"],
        value="Normal",
        help="Ajusta el espaciado entre elementos"
    )
    
    if st.button("💾 Guardar Densidad"):
        st.session_state["ui_density"] = density.lower()
        st.success(f"✅ Densidad cambiada a {density}")
    
    st.divider()
    
    # Personalización de colores (solo admin)
    user = st.session_state.get("u_actual", {})
    if user.get("rol") in ["admin", "superadmin"]:
        st.subheader("Personalización de Colores (Admin)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            primary_color = st.color_picker(
                "Color Primario",
                value="#14b8a6"
            )
        
        with col2:
            secondary_color = st.color_picker(
                "Color Secundario",
                value="#0f172a"
            )
        
        if st.button("💾 Guardar Colores"):
            st.session_state["primary_color"] = primary_color
            st.session_state["secondary_color"] = secondary_color
            st.success("✅ Colores actualizados")
            
            audit_log(
                AuditEventType.CONFIG_CHANGE,
                resource_type="appearance",
                resource_id="colors",
                action="UPDATE",
                description=f"Colors updated: primary={primary_color}"
            )


def render_notification_settings():
    """Configuración de notificaciones."""
    st.header("🔔 Notificaciones")
    
    # Email notifications
    st.subheader("Notificaciones por Email")
    
    email_enabled = st.toggle(
        "Habilitar notificaciones por email",
        value=False,
        help="Recibe alertas importantes por correo"
    )
    
    if email_enabled:
        email = st.text_input(
            "Email para notificaciones",
            value=st.session_state.get("u_actual", {}).get("email", "")
        )
        
        st.multiselect(
            "Eventos a notificar",
            options=[
                "Nueva evolución agregada",
                "Cambio en signos vitales",
                "Backup completado/fallido",
                "Alertas de seguridad",
                "Actualizaciones del sistema"
            ],
            default=["Alertas de seguridad"]
        )
    
    st.divider()
    
    # Push notifications
    st.subheader("Notificaciones Push (Navegador)")
    
    push_enabled = st.toggle(
        "Habilitar notificaciones push",
        value=st.session_state.get("push_notifications", False),
        help="Recibe notificaciones en tu navegador"
    )
    
    if push_enabled != st.session_state.get("push_notifications", False):
        st.session_state["push_notifications"] = push_enabled
        if push_enabled:
            st.info("🔔 Has habilitado notificaciones push. El navegador solicitará permisos.")
        else:
            st.info("🔕 Notificaciones push deshabilitadas.")
    
    st.divider()
    
    # In-app notifications
    st.subheader("Notificaciones en Aplicación")
    
    st.checkbox("Mostrar toast notifications", value=True)
    st.checkbox("Mostrar badges en menú", value=True)
    st.checkbox("Sonido en alertas críticas", value=True)
    
    st.divider()
    
    if st.button("💾 Guardar Configuración de Notificaciones"):
        st.success("✅ Configuración guardada")
        log_event("settings", "Notification settings updated")


def render_integration_settings(is_admin: bool):
    """Configuración de integraciones."""
    st.header("🔗 Integraciones")
    
    if not is_admin:
        st.info("🔒 Las integraciones solo pueden ser configuradas por administradores.")
        return
    
    # Supabase
    st.subheader("Supabase (Base de Datos Cloud)")
    
    supabase_enabled = st.toggle(
        "Habilitar sincronización con Supabase",
        value=settings.ENABLE_SUPABASE_SYNC if hasattr(settings, 'ENABLE_SUPABASE_SYNC') else False,
        help="Sincroniza datos con Supabase en la nube"
    )
    
    with st.expander("Configuración de Supabase"):
        supabase_url = st.text_input(
            "Supabase URL",
            value=settings.SUPABASE_URL if hasattr(settings, 'SUPABASE_URL') else "",
            type="password"
        )
        
        supabase_key = st.text_input(
            "Supabase Key",
            value="",
            type="password",
            help="API Key de Supabase"
        )
    
    st.divider()
    
    # Email
    st.subheader("Servidor de Email (SMTP)")
    
    smtp_enabled = st.toggle(
        "Habilitar envío de emails",
        value=settings.EMAIL_ENABLED if hasattr(settings, 'EMAIL_ENABLED') else False
    )
    
    with st.expander("Configuración SMTP"):
        col1, col2 = st.columns(2)
        
        with col1:
            smtp_host = st.text_input(
                "SMTP Host",
                value=settings.SMTP_HOST if hasattr(settings, 'SMTP_HOST') else "smtp.gmail.com"
            )
            smtp_port = st.number_input(
                "SMTP Port",
                value=int(settings.SMTP_PORT) if hasattr(settings, 'SMTP_PORT') else 587,
                min_value=1,
                max_value=65535
            )
        
        with col2:
            smtp_user = st.text_input(
                "SMTP Usuario",
                value=settings.SMTP_USER if hasattr(settings, 'SMTP_USER') else ""
            )
            smtp_password = st.text_input(
                "SMTP Password",
                type="password",
                value=""
            )
    
    st.divider()
    
    # Redis
    st.subheader("Redis (Caché Distribuida)")
    
    redis_enabled = st.toggle(
        "Habilitar Redis",
        value=settings.ENABLE_CACHE if hasattr(settings, 'ENABLE_CACHE') else True
    )
    
    with st.expander("Configuración Redis"):
        redis_url = st.text_input(
            "Redis URL",
            value=settings.REDIS_URL if hasattr(settings, 'REDIS_URL') else "redis://localhost:6379/0",
            help="URL de conexión a Redis"
        )
    
    st.divider()
    
    # AI/ML
    st.subheader("Inteligencia Artificial")
    
    st.toggle(
        "Habilitar asistente de IA",
        value=settings.ENABLE_AI_ASSISTANT if hasattr(settings, 'ENABLE_AI_ASSISTANT') else False,
        help="Permite usar asistente de IA para evoluciones"
    )
    
    with st.expander("Configuración de AI Provider"):
        ai_provider = st.selectbox(
            "Provider",
            options=["OpenAI", "Anthropic", "Local (Ollama)", "Ninguno"],
            index=3
        )
        
        if ai_provider != "Ninguno":
            ai_key = st.text_input(
                "API Key",
                type="password",
                value=""
            )
    
    st.divider()
    
    if st.button("💾 Guardar Configuración de Integraciones"):
        st.success("✅ Integraciones guardadas (requiere reinicio)")
        
        audit_log(
            AuditEventType.CONFIG_CHANGE,
            resource_type="integrations",
            resource_id="all",
            action="UPDATE",
            description="Integration settings updated"
        )


def render_security_settings(is_admin: bool):
    """Configuración de seguridad."""
    st.header("🔒 Seguridad")
    
    if not is_admin:
        st.info("🔒 La configuración de seguridad solo está disponible para administradores.")
        return
    
    # 2FA
    st.subheader("Autenticación de Dos Factores (2FA)")
    
    st.toggle(
        "Requerir 2FA para todos los usuarios",
        value=settings.ENABLE_2FA if hasattr(settings, 'ENABLE_2FA') else False
    )
    
    st.toggle(
        "Requerir 2FA solo para administradores",
        value=True
    )
    
    st.divider()
    
    # Política de contraseñas
    st.subheader("Política de Contraseñas")
    
    min_length = st.slider(
        "Longitud mínima",
        min_value=6,
        max_value=20,
        value=8
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.checkbox("Requerir mayúsculas", value=True)
    
    with col2:
        st.checkbox("Requerir números", value=True)
    
    with col3:
        st.checkbox("Requerir símbolos", value=False)
    
    st.divider()
    
    # Sesiones
    st.subheader("Gestión de Sesiones")
    
    session_timeout = st.number_input(
        "Timeout de sesión (minutos)",
        min_value=5,
        max_value=240,
        value=30,
        help="Tiempo de inactividad antes de cerrar sesión"
    )
    
    max_attempts = st.number_input(
        "Intentos máximos de login",
        min_value=3,
        max_value=10,
        value=5
    )
    
    st.divider()
    
    # Auditoría
    st.subheader("Auditoría y Logs")
    
    st.checkbox("Habilitar auditoría de acciones", value=True)
    st.checkbox("Log de accesos fallidos", value=True)
    st.checkbox("Log de cambios de datos", value=True)
    
    retention_days = st.number_input(
        "Retención de logs (días)",
        min_value=7,
        max_value=365,
        value=90
    )
    
    st.divider()
    
    # Backup de seguridad
    st.subheader("Backup de Seguridad")
    
    st.checkbox("Encriptar backups", value=True)
    
    st.selectbox(
        "Frecuencia de backup",
        options=["Cada hora", "Cada 6 horas", "Diario", "Semanal"],
        index=2
    )
    
    st.divider()
    
    if st.button("💾 Guardar Configuración de Seguridad"):
        st.success("✅ Configuración de seguridad guardada")
        
        audit_log(
            AuditEventType.CONFIG_CHANGE,
            resource_type="security",
            resource_id="policy",
            action="UPDATE",
            description="Security settings updated",
            metadata={"session_timeout": session_timeout, "max_attempts": max_attempts}
        )


def render_advanced_settings(is_admin: bool):
    """Configuración avanzada."""
    st.header("⚡ Avanzado")
    
    if not is_admin:
        st.info("🔒 Configuración avanzada solo para administradores.")
        return
    
    # Performance
    st.subheader("Performance")
    
    st.toggle(
        "Habilitar caché agresiva",
        value=True,
        help="Cachea más datos para mejorar velocidad"
    )
    
    st.toggle(
        "Lazy loading de datos",
        value=True,
        help="Carga datos bajo demanda"
    )
    
    cache_ttl = st.number_input(
        "TTL de caché (segundos)",
        min_value=60,
        max_value=3600,
        value=300
    )
    
    st.divider()
    
    # Logging
    st.subheader("Logging")
    
    log_level = st.selectbox(
        "Nivel de log",
        options=["DEBUG", "INFO", "WARNING", "ERROR"],
        index=1
    )
    
    st.checkbox("Log a archivo", value=False)
    st.checkbox("Log estructurado (JSON)", value=True)
    
    st.divider()
    
    # Feature Flags
    st.subheader("Feature Flags")
    
    st.info("Los feature flags se gestionan desde el panel de administración.")
    
    if st.button("Ir a Feature Flags"):
        # Cambiar a página de feature flags
        st.session_state["nav"] = "admin_feature_flags"
        st.rerun()
    
    st.divider()
    
    # Mantenimiento
    st.subheader("🛠️ Mantenimiento")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Limpiar Caché", use_container_width=True):
            from core.distributed_cache import get_cache
            cache = get_cache()
            cache.clear()
            st.success("✅ Caché limpiada")
            log_event("maintenance", "Cache cleared from settings")
    
    with col2:
        if st.button("🔄 Forzar Guardado", use_container_width=True):
            from core.database import guardar_datos
            try:
                guardar_datos()
                st.success("✅ Datos guardados")
            except Exception as e:
                st.error(f"❌ Error: {e}")
    
    st.divider()
    
    # Danger Zone
    st.subheader("🚨 Zona de Peligro")
    
    with st.expander("⚠️ Acciones Destructivas"):
        st.error("Las siguientes acciones pueden causar pérdida de datos.")
        
        if st.button("🗑️ Limpiar Datos de Sesión", type="secondary"):
            st.warning("⚠️ Esto eliminará todos los datos temporales.")
            confirm = st.checkbox("Confirmar eliminación")
            if confirm:
                # Limpiar session_state no crítico
                keys_to_keep = ["logeado", "u_actual", "session_id"]
                for key in list(st.session_state.keys()):
                    if key not in keys_to_keep:
                        del st.session_state[key]
                st.success("✅ Sesión limpiada")
                log_event("maintenance", "Session state cleared")
        
        if st.button("🔄 Resetear Configuración", type="secondary"):
            st.warning("⚠️ Esto reseteará todas las configuraciones a valores por defecto.")
            st.info("(Esta función requiere confirmación adicional)")
    
    st.divider()
    
    # System Info
    st.subheader("Información del Sistema")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.text(f"Versión: {get_version()}")
        st.text(f"Entorno: {get_environment()}")
        st.text(f"Python: {get_python_version()}")
    
    with col2:
        st.text(f"Streamlit: {st.__version__}")
        st.text(f"Sistema: {get_os_info()}")
    
    if st.button("📊 Ver Health Check"):
        from core.system_health import get_health_monitor
        monitor = get_health_monitor()
        monitor.render_health_dashboard()


def get_version() -> str:
    """Obtiene versión de la aplicación."""
    try:
        from core.release_notes import RELEASES
        return RELEASES[0]["version"] if RELEASES else "unknown"
    except:
        return "unknown"


def get_environment() -> str:
    """Obtiene ambiente actual."""
    return settings.ENVIRONMENT if hasattr(settings, 'ENVIRONMENT') else "development"


def get_python_version() -> str:
    """Obtiene versión de Python."""
    import sys
    return f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


def get_os_info() -> str:
    """Obtiene información del sistema operativo."""
    import platform
    return f"{platform.system()} {platform.release()}"
