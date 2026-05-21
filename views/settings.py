from __future__ import annotations

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
import time


from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType
from core.config import settings
from core.database import guardar_datos
from core.i18n import render_language_selector
from views.admin_usuarios import render_admin_usuarios


def render_settings_page():
    """Renderiza página completa de configuración."""
    # Verificar permisos
    user = st.session_state.get("u_actual", {})
    is_admin = str(user.get("rol", "")).strip().lower() in {"admin", "superadmin"}
    
    st.title("⚙️ Configuración")
    st.caption(f"Usuario: {user.get('nombre', 'N/A')}")
    
    # Tabs de configuración
    _tabs_list = [
        "🎨 Apariencia",
        "🔔 Notificaciones",
        "🔗 Integraciones",
        "📦 Reglas de Insumos",
        "🔒 Seguridad",
        "⚡ Avanzado",
    ]
    if is_admin:
        _tabs_list.append("👥 Usuarios")
    tabs = st.tabs(_tabs_list)
    
    with tabs[0]:
        render_appearance_settings()
    
    with tabs[1]:
        render_notification_settings()
    
    with tabs[2]:
        render_integration_settings(is_admin)
    
    with tabs[3]:
        render_insumos_rules_settings(is_admin)
    
    with tabs[4]:
        render_security_settings(is_admin)
    
    with tabs[5]:
        render_advanced_settings(is_admin)
    
    if is_admin:
        with tabs[6]:
            render_admin_usuarios()


def render_appearance_settings():
    """Configuración de apariencia."""
    st.header("🎨 Apariencia")
    _s = st.session_state.setdefault("settings_db", {})
    
    # Selector de idioma
    st.subheader("Idioma")
    render_language_selector()
    
    st.divider()
    
    # Tema
    st.subheader("Tema")
    
    _theme_opts = ["Claro", "Oscuro", "Auto"]
    _s_theme = _s.get("app_theme", "Claro")
    theme = st.radio(
        "Tema de color",
        options=_theme_opts,
        index=_theme_opts.index(_s_theme) if _s_theme in _theme_opts else 0,
        help="Selecciona el tema de la aplicación"
    )
    
    if st.button("💾 Guardar Tema"):
        _s["app_theme"] = theme
        st.session_state["theme"] = theme.lower()
        try:
            guardar_datos(spinner=False)
        except Exception as e:
            log_event("settings", f"error:guardar_tema:{e}")
        st.success(f"✅ Tema cambiado a {theme}")
        log_event("settings", f"Theme changed to {theme}")
    
    st.divider()
    
    # Densidad de UI
    st.subheader("Densidad de Interfaz")
    
    density = st.select_slider(
        "Densidad",
        options=["Compacta", "Normal", "Espaciada"],
        value=_s.get("app_density", "Normal"),
        help="Ajusta el espaciado entre elementos"
    )
    
    if st.button("💾 Guardar Densidad"):
        _s["app_density"] = density.lower()
        st.session_state["ui_density"] = density.lower()
        try:
            guardar_datos(spinner=False)
        except Exception as e:
            log_event("settings", f"error:guardar_densidad:{e}")
        st.success(f"✅ Densidad cambiada a {density}")
    
    st.divider()
    
    # Personalización de colores (solo admin)
    user = st.session_state.get("u_actual", {})
    if str(user.get("rol", "")).strip().lower() in {"admin", "superadmin"}:
        st.subheader("Personalización de Colores (Admin)")
        
        col1, col2 = st.columns(2)
        
        with col1:
            primary_color = st.color_picker(
                "Color Primario",
                value=_s.get("app_primary_color", "#14b8a6")
            )
        
        with col2:
            secondary_color = st.color_picker(
                "Color Secundario",
                value=_s.get("app_secondary_color", "#0f172a")
            )
        
        if st.button("💾 Guardar Colores"):
            _s["app_primary_color"] = primary_color
            _s["app_secondary_color"] = secondary_color
            st.session_state["primary_color"] = primary_color
            st.session_state["secondary_color"] = secondary_color
            try:
                guardar_datos(spinner=False)
            except Exception as e:
                log_event("settings", f"error:guardar_colores:{e}")
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
    _s = st.session_state.setdefault("settings_db", {})
    
    # Email notifications
    st.subheader("Notificaciones por Email")
    
    email_enabled = st.toggle(
        "Habilitar notificaciones por email",
        value=_s.get("notif_email_enabled", False),
        help="Recibe alertas importantes por correo"
    )
    
    email = ""
    if email_enabled:
        email = st.text_input(
            "Email para notificaciones",
            value=_s.get("notif_email_addr", st.session_state.get("u_actual", {}).get("email", ""))
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
    
    _toast = st.checkbox("Mostrar toast notifications", value=_s.get("notif_toast", True))
    _badges = st.checkbox("Mostrar badges en menú", value=_s.get("notif_badges", True))
    _sound = st.checkbox("Sonido en alertas críticas", value=_s.get("notif_sound", True))
    
    st.divider()
    
    if st.button("💾 Guardar Configuración de Notificaciones"):
        _s["notif_email_enabled"] = email_enabled
        if email_enabled:
            _s["notif_email_addr"] = email
        _s["notif_toast"] = _toast
        _s["notif_badges"] = _badges
        _s["notif_sound"] = _sound
        try:
            guardar_datos(spinner=False)
        except Exception as e:
            log_event("settings", f"error:guardar_notificaciones:{e}")
        st.success("✅ Configuración guardada")
        log_event("settings", "Notification settings updated")


def render_integration_settings(is_admin: bool):
    """Configuración de integraciones."""
    st.header("🔗 Integraciones")
    
    if not is_admin:
        st.info("🔒 Las integraciones solo pueden ser configuradas por administradores.")
        return
    
    _s = st.session_state.setdefault("settings_db", {})
    
    # Supabase
    st.subheader("Supabase (Base de Datos Cloud)")
    
    supabase_enabled = st.toggle(
        "Habilitar sincronización con Supabase",
        value=_s.get("integ_supabase_enabled", settings.ENABLE_SUPABASE_SYNC if hasattr(settings, 'ENABLE_SUPABASE_SYNC') else False),
        help="Sincroniza datos con Supabase en la nube"
    )
    
    with st.expander("Configuración de Supabase"):
        supabase_url = st.text_input(
            "Supabase URL",
            value=_s.get("integ_supabase_url", settings.SUPABASE_URL if hasattr(settings, 'SUPABASE_URL') else ""),
            type="password"
        )
        
        supabase_key = st.text_input(
            "Supabase Key",
            value=_s.get("integ_supabase_key", ""),
            type="password",
            help="API Key de Supabase"
        )
    
    st.divider()
    
    # Email
    st.subheader("Servidor de Email (SMTP)")
    
    smtp_enabled = st.toggle(
        "Habilitar envío de emails",
        value=_s.get("integ_smtp_enabled", settings.EMAIL_ENABLED if hasattr(settings, 'EMAIL_ENABLED') else False)
    )
    
    with st.expander("Configuración SMTP"):
        col1, col2 = st.columns(2)
        
        with col1:
            smtp_host = st.text_input(
                "SMTP Host",
                value=_s.get("integ_smtp_host", settings.SMTP_HOST if hasattr(settings, 'SMTP_HOST') else "smtp.gmail.com")
            )
            smtp_port = st.number_input(
                "SMTP Port",
                value=_s.get("integ_smtp_port", int(settings.SMTP_PORT) if hasattr(settings, 'SMTP_PORT') else 587),
                min_value=1,
                max_value=65535
            )
        
        with col2:
            smtp_user = st.text_input(
                "SMTP Usuario",
                value=_s.get("integ_smtp_user", settings.SMTP_USER if hasattr(settings, 'SMTP_USER') else "")
            )
            smtp_password = st.text_input(
                "SMTP Password",
                type="password",
                value=_s.get("integ_smtp_password", "")
            )
    
    st.divider()
    
    # Redis
    st.subheader("Redis (Caché Distribuida)")
    
    redis_enabled = st.toggle(
        "Habilitar Redis",
        value=_s.get("integ_redis_enabled", settings.ENABLE_CACHE if hasattr(settings, 'ENABLE_CACHE') else True)
    )
    
    with st.expander("Configuración Redis"):
        redis_url = st.text_input(
            "Redis URL",
            value=_s.get("integ_redis_url", settings.REDIS_URL if hasattr(settings, 'REDIS_URL') else "redis://localhost:6379/0"),
            help="URL de conexión a Redis"
        )
    
    st.divider()
    
    # AI/ML
    st.subheader("🤖 Inteligencia Artificial")
    st.caption("Configurá la IA para tener asistencia en todos los módulos del programa.")

    ai_enabled = st.toggle(
        "Habilitar asistente de IA en todo el programa",
        value=_s.get("integ_ai_enabled", settings.ENABLE_AI_ASSISTANT if hasattr(settings, 'ENABLE_AI_ASSISTANT') else False),
        help="Activa IA contextual, sugerencias de evolución, interpretación de estudios, recetas y más."
    )

    if ai_enabled:
        _ai_providers = ["OpenAI", "Anthropic", "DeepSeek", "Local (Ollama)", "Ninguno"]
        _s_ai_provider = _s.get("integ_ai_provider", "Ninguno")
        ai_provider = st.selectbox(
            "Proveedor de IA",
            options=_ai_providers,
            index=_ai_providers.index(_s_ai_provider) if _s_ai_provider in _ai_providers else 3,
            help="DeepSeek es gratuito y compatible con OpenAI."
        )

        ai_key = _s.get("integ_ai_key", "")
        ai_model = _s.get("integ_ai_model", "deepseek-chat")
        if ai_provider != "Ninguno":
            st.caption(f"💡 Consejo para {ai_provider}:")
            if ai_provider == "DeepSeek":
                st.info("Registrate en https://platform.deepseek.com y generá una API Key. Usá 'deepseek-chat' como modelo.")
            elif ai_provider == "OpenAI":
                st.info("API Key de https://platform.openai.com. Modelos: gpt-4, gpt-4o, gpt-3.5-turbo.")
            elif ai_provider == "Anthropic":
                st.info("API Key de https://console.anthropic.com. Modelos: claude-3-opus, claude-3-sonnet.")
            ai_key = st.text_input("API Key", type="password", value=ai_key,
                help="Tu API key del proveedor seleccionado")
            ai_model = st.text_input(
                "Modelo", value=ai_model,
                help="Ej: deepseek-chat, gpt-4, gpt-4o, claude-3-sonnet-20240229"
            )

            # Test de conexión
            if st.button("🔄 Probar conexión con IA", key="ai_test_btn", use_container_width=True):
                if not ai_key.strip():
                    st.warning("Primero ingresá una API Key.")
                else:
                    _probar_conexion_ia(ai_provider, ai_key, ai_model)
    else:
        ai_provider = "Ninguno"
        ai_key = _s.get("integ_ai_key", "")
        ai_model = _s.get("integ_ai_model", "deepseek-chat")
    
    # Indicador de estado actual
    if is_admin:
        from core.ai_assistant import is_llm_enabled
        if is_llm_enabled():
            st.success("✅ IA conectada y disponible en todo el sistema.")
        else:
            st.warning("⚠️ IA no configurada. Completá los campos y guardá.")

    st.divider()
    
    if st.button("💾 Guardar Configuración de Integraciones"):
        _s["integ_supabase_enabled"] = supabase_enabled
        _s["integ_supabase_url"] = supabase_url
        _s["integ_supabase_key"] = supabase_key
        _s["integ_smtp_enabled"] = smtp_enabled
        _s["integ_smtp_host"] = smtp_host
        _s["integ_smtp_port"] = smtp_port
        _s["integ_smtp_user"] = smtp_user
        _s["integ_smtp_password"] = smtp_password
        _s["integ_redis_enabled"] = redis_enabled
        _s["integ_redis_url"] = redis_url
        _s["integ_ai_enabled"] = ai_enabled
        _s["integ_ai_provider"] = ai_provider
        _s["integ_ai_key"] = ai_key
        _s["integ_ai_model"] = ai_model
        try:
            guardar_datos(spinner=False)
        except Exception as e:
            log_event("settings", f"error:guardar_integraciones:{e}")
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
    
    _s = st.session_state.setdefault("settings_db", {})
    
    # 2FA
    st.subheader("Autenticación de Dos Factores (2FA)")
    
    _sec_2fa_required = st.toggle(
        "Requerir 2FA para todos los usuarios",
        value=_s.get("sec_2fa_required", settings.ENABLE_2FA if hasattr(settings, 'ENABLE_2FA') else False)
    )
    
    _sec_2fa_admin_only = st.toggle(
        "Requerir 2FA solo para administradores",
        value=_s.get("sec_2fa_admin_only", True)
    )
    
    st.divider()
    
    # Política de contraseñas
    st.subheader("Política de Contraseñas")
    
    min_length = st.slider(
        "Longitud mínima",
        min_value=6,
        max_value=20,
        value=_s.get("sec_min_length", 8)
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        _sec_req_upper = st.checkbox("Requerir mayúsculas", value=_s.get("sec_req_upper", True))
    
    with col2:
        _sec_req_num = st.checkbox("Requerir números", value=_s.get("sec_req_num", True))
    
    with col3:
        _sec_req_sym = st.checkbox("Requerir símbolos", value=_s.get("sec_req_sym", False))
    
    st.divider()
    
    # Sesiones
    st.subheader("Gestión de Sesiones")
    
    session_timeout = st.number_input(
        "Timeout de sesión (minutos)",
        min_value=5,
        max_value=240,
        value=_s.get("sec_session_timeout", 30),
        help="Tiempo de inactividad antes de cerrar sesión"
    )
    
    max_attempts = st.number_input(
        "Intentos máximos de login",
        min_value=3,
        max_value=10,
        value=_s.get("sec_max_attempts", 5)
    )
    
    st.divider()
    
    # Auditoría
    st.subheader("Auditoría y Logs")
    
    _sec_audit_enabled = st.checkbox("Habilitar auditoría de acciones", value=_s.get("sec_audit_enabled", True))
    _sec_log_access = st.checkbox("Log de accesos fallidos", value=_s.get("sec_log_access", True))
    _sec_log_changes = st.checkbox("Log de cambios de datos", value=_s.get("sec_log_changes", True))
    
    retention_days = st.number_input(
        "Retención de logs (días)",
        min_value=7,
        max_value=365,
        value=_s.get("sec_retention_days", 90)
    )
    
    st.divider()
    
    # Backup de seguridad
    st.subheader("Backup de Seguridad")
    
    _sec_encrypt_backups = st.checkbox("Encriptar backups", value=_s.get("sec_encrypt_backups", True))
    
    _backup_opts = ["Cada hora", "Cada 6 horas", "Diario", "Semanal"]
    _s_backup_freq = _s.get("sec_backup_freq", "Diario")
    _backup_freq = st.selectbox(
        "Frecuencia de backup",
        options=_backup_opts,
        index=_backup_opts.index(_s_backup_freq) if _s_backup_freq in _backup_opts else 2
    )
    
    st.divider()

    if st.button("💾 Guardar Configuración de Seguridad"):
        _s["sec_2fa_required"] = _sec_2fa_required
        _s["sec_2fa_admin_only"] = _sec_2fa_admin_only
        _s["sec_min_length"] = min_length
        _s["sec_req_upper"] = _sec_req_upper
        _s["sec_req_num"] = _sec_req_num
        _s["sec_req_sym"] = _sec_req_sym
        _s["sec_session_timeout"] = session_timeout
        _s["sec_max_attempts"] = max_attempts
        _s["sec_audit_enabled"] = _sec_audit_enabled
        _s["sec_log_access"] = _sec_log_access
        _s["sec_log_changes"] = _sec_log_changes
        _s["sec_retention_days"] = retention_days
        _s["sec_encrypt_backups"] = _sec_encrypt_backups
        _s["sec_backup_freq"] = _backup_freq
        try:
            guardar_datos(spinner=False)
        except Exception as e:
            log_event("settings", f"error:guardar_seguridad:{e}")
        st.success("✅ Configuración de seguridad guardada")
        
        audit_log(
            AuditEventType.CONFIG_CHANGE,
            resource_type="security",
            resource_id="policy",
            action="UPDATE",
            description="Security settings updated",
            metadata={"session_timeout": session_timeout, "max_attempts": max_attempts}
        )

    st.divider()
    st.subheader("Backup Manual")
    if st.button("💾 Hacer backup ahora", use_container_width=True):
        try:
            from core.database import _db_keys, dumps_db_sorted
            import json
            from pathlib import Path
            from datetime import datetime
            claves = _db_keys()
            data = {k: st.session_state[k] for k in claves if k in st.session_state}
            backup_path = Path(f"backups/backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            backup_path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
            st.success(f"✅ Backup guardado: {backup_path.name}")
            st.session_state["_ultimo_backup_ts"] = time.time()
            log_event("backup", f"manual_backup_ok:{backup_path.name}")
        except Exception as exc:
            st.error(f"❌ Error: {exc}")
            log_event("backup", f"manual_backup_fallo:{type(exc).__name__}:{exc}")


def render_advanced_settings(is_admin: bool):
    """Configuración avanzada."""
    st.header("⚡ Avanzado")
    
    if not is_admin:
        st.info("🔒 Configuración avanzada solo para administradores.")
        return
    
    _s = st.session_state.setdefault("settings_db", {})
    
    # Performance
    st.subheader("Performance")
    
    _adv_aggressive_cache = st.toggle(
        "Habilitar caché agresiva",
        value=_s.get("adv_aggressive_cache", True),
        help="Cachea más datos para mejorar velocidad"
    )
    
    _adv_lazy_loading = st.toggle(
        "Lazy loading de datos",
        value=_s.get("adv_lazy_loading", True),
        help="Carga datos bajo demanda"
    )
    
    cache_ttl = st.number_input(
        "TTL de caché (segundos)",
        min_value=60,
        max_value=3600,
        value=_s.get("adv_cache_ttl", 300)
    )
    
    st.divider()
    
    # Logging
    st.subheader("Logging")
    
    _log_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
    _s_log_level = _s.get("adv_log_level", "INFO")
    log_level = st.selectbox(
        "Nivel de log",
        options=_log_levels,
        index=_log_levels.index(_s_log_level) if _s_log_level in _log_levels else 1
    )
    
    _adv_log_file = st.checkbox("Log a archivo", value=_s.get("adv_log_file", False))
    _adv_log_json = st.checkbox("Log estructurado (JSON)", value=_s.get("adv_log_json", True))
    
    st.divider()
    
    if st.button("💾 Guardar Configuración Avanzada"):
        _s["adv_aggressive_cache"] = _adv_aggressive_cache
        _s["adv_lazy_loading"] = _adv_lazy_loading
        _s["adv_cache_ttl"] = cache_ttl
        _s["adv_log_level"] = log_level
        _s["adv_log_file"] = _adv_log_file
        _s["adv_log_json"] = _adv_log_json
        try:
            guardar_datos(spinner=False)
        except Exception as e:
            log_event("settings", f"error:guardar_avanzado:{e}")
        st.success("✅ Configuración avanzada guardada")
        log_event("settings", "Advanced settings updated")
    
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
        if st.button("🗑️ Limpiar Caché", width='stretch'):
            from core.distributed_cache import get_cache
            cache = get_cache()
            cache.clear()
            st.success("✅ Caché limpiada")
            log_event("maintenance", "Cache cleared from settings")
    
    with col2:
        if st.button("🔄 Forzar Guardado", width='stretch'):
            try:
                guardar_datos(spinner=False)
                st.success("✅ Datos guardados")
            except Exception as e:
                log_event("settings", "error: guardar_datos_fallo")
                st.error(f"❌ Error: {e}")
    
    st.divider()
    
    # Danger Zone
    st.subheader("🚨 Zona de Peligro")
    
    with st.expander("⚠️ Acciones Destructivas"):
        log_event("settings", "acciones_destructivas_expandidas")
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


def render_insumos_rules_settings(is_admin: bool):
    """Configuración de reglas personalizadas de insumos automáticos."""
    st.header("📦 Reglas de Insumos Automáticos")
    st.caption(
        "Definí qué insumos se descuentan automáticamente al administrar un "
        "medicamento o al detectar un procedimiento en la evolución."
    )

    st.markdown("#### Reglas para Medicamentos")
    st.caption("Ej: nombre del medicamento → jeringa 5ml + aguja EV")
    _med_rules: dict = st.session_state.setdefault("_insumos_map_medicamentos", {})
    _med_keys = list(_med_rules.keys())

    if _med_keys:
        for i, k in enumerate(_med_keys):
            with st.container(border=True):
                ca, cb = st.columns([3, 1])
                new_k = ca.text_input("Medicamento (palabra clave)", value=k, key=f"med_k_{i}")
                items_str = ", ".join(
                    f"{v['item']} x{v['cantidad']}" for v in _med_rules[k]
                )
                new_v = ca.text_input("Insumos (formato: 'Jeringa 5ml x1, Aguja EV x1')", value=items_str, key=f"med_v_{i}")
                if cb.button("🗑️", key=f"med_del_{i}"):
                    del _med_rules[k]
                    st.rerun()
                if new_k != k or new_v != items_str:
                    if new_k.strip() and new_v.strip():
                        del _med_rules[k]
                        _med_rules[new_k.strip()] = [
                            {"item": p.rsplit("x", 1)[0].strip(), "cantidad": int(p.rsplit("x", 1)[1].strip())}
                            for p in new_v.split(",") if "x" in p
                        ]
                        st.rerun()
    else:
        st.info("Sin reglas personalizadas todavía. Agregá una abajo.")

    with st.form("nueva_regla_med"):
        nm = st.text_input("Palabra clave del medicamento", placeholder="Ej: mi-medicamento")
        nv = st.text_input("Insumos (separados por coma)", placeholder="Ej: Jeringa 5ml x1, Aguja EV x1")
        if st.form_submit_button("➕ Agregar regla de medicamento", type="primary", use_container_width=True):
            if nm.strip() and nv.strip():
                _med_rules[nm.strip()] = [
                    {"item": p.rsplit("x", 1)[0].strip(), "cantidad": int(p.rsplit("x", 1)[1].strip())}
                    for p in nv.split(",") if "x" in p
                ]
                st.success(f"✅ Regla '{nm.strip()}' agregada")
                st.rerun()

    st.divider()
    st.markdown("#### Reglas para Procedimientos")
    st.caption("Ej: 'baño en cama' → pañal x2, toalla húmeda x4")
    _proc_rules: dict = st.session_state.setdefault("_insumos_map_procedimientos", {})
    _proc_keys = list(_proc_rules.keys())

    if _proc_keys:
        for i, k in enumerate(_proc_keys):
            with st.container(border=True):
                ca, cb = st.columns([3, 1])
                new_k = ca.text_input("Procedimiento", value=k, key=f"proc_k_{i}")
                items_str = ", ".join(
                    f"{v['item']} x{v['cantidad']}" for v in _proc_rules[k]
                )
                new_v = ca.text_input("Insumos", value=items_str, key=f"proc_v_{i}")
                if cb.button("🗑️", key=f"proc_del_{i}"):
                    del _proc_rules[k]
                    st.rerun()
                if new_k != k or new_v != items_str:
                    if new_k.strip() and new_v.strip():
                        del _proc_rules[k]
                        _proc_rules[new_k.strip()] = [
                            {"item": p.rsplit("x", 1)[0].strip(), "cantidad": int(p.rsplit("x", 1)[1].strip())}
                            for p in new_v.split(",") if "x" in p
                        ]
                        st.rerun()

    with st.form("nueva_regla_proc"):
        nm = st.text_input("Palabra clave del procedimiento", placeholder="Ej: curacion + infectada")
        nv = st.text_input("Insumos (separados por coma)", placeholder="Ej: Gasas estériles x10, Guantes estériles x2")
        if st.form_submit_button("➕ Agregar regla de procedimiento", type="primary", use_container_width=True):
            if nm.strip() and nv.strip():
                _proc_rules[nm.strip()] = [
                    {"item": p.rsplit("x", 1)[0].strip(), "cantidad": int(p.rsplit("x", 1)[1].strip())}
                    for p in nv.split(",") if "x" in p
                ]
                st.success(f"✅ Regla '{nm.strip()}' agregada")
                st.rerun()

    if is_admin:
        st.divider()
        with st.expander("🗑️ Restablecer reglas predeterminadas"):
            if st.button("Eliminar TODAS las reglas personalizadas", type="secondary"):
                st.session_state["_insumos_map_medicamentos"] = {}
                st.session_state["_insumos_map_procedimientos"] = {}
                st.success("✅ Reglas personalizadas eliminadas")
                st.rerun()


def get_version() -> str:
    """Obtiene versión de la aplicación."""
    try:
        from core.release_notes import RELEASES
        return RELEASES[0]["version"] if RELEASES else "unknown"
    except Exception:
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


def _probar_conexion_ia(provider_display: str, api_key: str, model: str):
    """Prueba conexión contra el proveedor de IA sin modificar config global."""
    if not api_key.strip():
        st.warning("Primero ingresá una API Key.")
        return
    provider_map = {"OpenAI": "openai", "DeepSeek": "deepseek"}
    internal = provider_map.get(provider_display)
    if not internal:
        st.warning(f"Test automático no soportado para {provider_display}.")
        return
    try:
        from openai import OpenAI, APIError
        base_url = "https://api.deepseek.com/v1" if internal == "deepseek" else None
        client = OpenAI(api_key=api_key, base_url=base_url, timeout=15)
        resp = client.chat.completions.create(
            model=model or "deepseek-chat",
            messages=[{"role": "user", "content": "Respondé SOLO con: OK"}],
            max_tokens=5,
            temperature=0,
        )
        texto = resp.choices[0].message.content.strip()
        if "OK" in texto:
            st.success(f"✅ Conexión exitosa con {provider_display} (modelo: {model})")
        else:
            st.warning(f"⚠️ Conectado pero respuesta inesperada: {texto[:80]}")
    except Exception as e:
        st.error(f"❌ Error de conexión: {e}")
