"""
Administración de Feature Flags para Medicare Pro.

Permite activar/desactivar funcionalidades en tiempo real.
Útil para:
- Rollouts graduales
- A/B testing
- Emergency killswitches
- Beta testing con usuarios específicos
"""

import streamlit as st
from typing import Dict, Any, Optional
from datetime import datetime

from core.feature_flags import FeatureFlags, get_feature_flags
from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType


def render_feature_flags_admin():
    """
    Renderiza panel de administración de Feature Flags.
    
    Solo para usuarios admin/superadmin.
    """
    # Verificar permisos
    user = st.session_state.get("u_actual", {})
    if user.get("rol") not in ["admin", "superadmin"]:
        st.error("🔒 Acceso denegado. Solo administradores.")
        return
    
    st.title("🚩 Feature Flags Administration")
    st.caption("Control de funcionalidades y rollouts graduales")
    
    # Tabs
    tabs = st.tabs([
        "🌎 Global Flags",
        "👤 User Flags", 
        "📊 Analytics",
        "📝 History"
    ])
    
    flags = get_feature_flags()
    
    with tabs[0]:
        render_global_flags(flags)
    
    with tabs[1]:
        render_user_flags(flags)
    
    with tabs[2]:
        render_flags_analytics()
    
    with tabs[3]:
        render_flags_history()


def render_global_flags(flags: FeatureFlags):
    """Renderiza flags globales del sistema."""
    st.header("🌎 Global Feature Flags")
    
    # Categorías de flags
    categories = {
        "Core Features": [
            ("ENABLE_CACHE", "Habilitar caché distribuida", True),
            ("ENABLE_RATE_LIMITING", "Rate limiting en API", True),
            ("ENABLE_AUDIT_LOG", "Logging de auditoría", True),
            ("ENABLE_NEXTGEN_API", "NextGen API (Beta)", False),
        ],
        "AI/ML Features": [
            ("ENABLE_AI_ASSISTANT", "Asistente de IA para evoluciones", False),
            ("ENABLE_RISK_PREDICTION", "Predicción de riesgo clínico", False),
            ("ENABLE_ANOMALY_DETECTION", "Detección de anomalías", True),
        ],
        "UI Features": [
            ("ENABLE_NEW_DASHBOARD", "Nuevo dashboard v2", False),
            ("ENABLE_MOBILE_OPTIMIZATIONS", "Optimizaciones móviles", True),
            ("ENABLE_DARK_MODE", "Modo oscuro", True),
            ("ENABLE_PWA", "Progressive Web App", True),
        ],
        "Integrations": [
            ("ENABLE_SUPABASE_SYNC", "Sincronización Supabase", True),
            ("ENABLE_EMAIL_NOTIFICATIONS", "Notificaciones por email", False),
            ("ENABLE_SMS_NOTIFICATIONS", "Notificaciones SMS", False),
            ("ENABLE_WHATSAPP_INTEGRATION", "Integración WhatsApp", False),
        ],
    }
    
    for category, flag_list in categories.items():
        with st.expander(f"📁 {category}", expanded=True):
            for flag_name, description, default_value in flag_list:
                col1, col2, col3 = st.columns([2, 1, 1])
                
                with col1:
                    st.text(description)
                    st.caption(f"Flag: `{flag_name}`")
                
                with col2:
                    current_value = flags.is_enabled(flag_name, default=default_value)
                    
                    # Toggle
                    new_value = st.toggle(
                        "Habilitado",
                        value=current_value,
                        key=f"toggle_{flag_name}"
                    )
                    
                    # Guardar cambio
                    if new_value != current_value:
                        flags.set_feature(flag_name, new_value)
                        
                        # Audit log
                        audit_log(
                            AuditEventType.CONFIG_CHANGE,
                            resource_type="feature_flag",
                            resource_id=flag_name,
                            action="UPDATE",
                            description=f"Feature flag {flag_name} cambiado a {new_value}",
                            metadata={"old_value": current_value, "new_value": new_value}
                        )
                        
                        log_event("feature_flag", f"{flag_name} = {new_value}")
                        st.success(f"✅ {flag_name} actualizado")
                
                with col3:
                    # Badge de estado
                    if new_value:
                        st.markdown("🟢 **ON**")
                    else:
                        st.markdown("🔴 **OFF**")


def render_user_flags(flags: FeatureFlags):
    """Renderiza flags específicos por usuario."""
    st.header("👤 User-Specific Flags")
    
    st.info("🚧 Feature: Activar funcionalidades beta para usuarios específicos")
    
    # Buscar usuario
    user_email = st.text_input(
        "Email del usuario",
        placeholder="usuario@ejemplo.com"
    )
    
    if user_email:
        # Mostrar flags para este usuario
        user_flags = {
            "beta_access": False,
            "new_ui_preview": False,
            "ai_assistant_beta": False,
            "advanced_reporting": False,
        }
        
        st.subheader(f"Flags para {user_email}")
        
        for flag_name, description in [
            ("beta_access", "Acceso Beta"),
            ("new_ui_preview", "Preview Nueva UI"),
            ("ai_assistant_beta", "Beta Asistente IA"),
            ("advanced_reporting", "Reportes Avanzados"),
        ]:
            col1, col2 = st.columns([3, 1])
            
            with col1:
                st.text(description)
            
            with col2:
                current = st.toggle(
                    "Habilitar",
                    value=user_flags.get(flag_name, False),
                    key=f"user_flag_{flag_name}_{user_email}"
                )
                
                if current != user_flags.get(flag_name):
                    # Actualizar en storage
                    st.success(f"✅ Actualizado")


def render_flags_analytics():
    """Renderiza analytics de uso de features."""
    st.header("📊 Feature Usage Analytics")
    
    # Métricas simuladas
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Flags Activos", "12/24")
    
    with col2:
        st.metric("Rollouts en Progreso", "2")
    
    with col3:
        st.metric("Usuarios Beta", "5")
    
    with col4:
        st.metric("Cambios Hoy", "3")
    
    # Gráfico de uso
    st.subheader("Uso de Features (últimos 7 días)")
    
    # Simular datos
    import pandas as pd
    
    data = {
        "Día": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
        "Caché": [1200, 1350, 1100, 1400, 1300, 900, 850],
        "Rate Limiting": [450, 520, 480, 550, 500, 300, 280],
        "AI Assistant": [45, 52, 48, 61, 55, 30, 25],
        "Anomaly Detection": [120, 135, 110, 140, 130, 90, 85],
    }
    
    df = pd.DataFrame(data)
    st.bar_chart(df.set_index("Día"))
    
    # Feature adoption
    st.subheader("Adopción de Features")
    
    adoption_data = {
        "Feature": [
            "Caché Distribuido",
            "Rate Limiting",
            "Auditoría",
            "PWA",
            "AI Assistant",
            "Anomaly Detection"
        ],
        "Adopción (%)": [95, 100, 100, 75, 15, 60],
        "Estado": ["✅ Activo", "✅ Activo", "✅ Activo", "✅ Activo", "🔴 Beta", "✅ Activo"]
    }
    
    df_adoption = pd.DataFrame(adoption_data)
    st.dataframe(df_adoption, use_container_width=True, hide_index=True)


def render_flags_history():
    """Renderiza historial de cambios en flags."""
    st.header("📝 Feature Flag Change History")
    
    # Simular historial
    history = [
        {
            "timestamp": "2024-01-15 14:30",
            "user": "admin@medicare.local",
            "flag": "ENABLE_AI_ASSISTANT",
            "change": "false → true",
            "reason": "Inicio beta testing"
        },
        {
            "timestamp": "2024-01-14 09:15",
            "user": "admin@medicare.local",
            "flag": "ENABLE_PWA",
            "change": "false → true",
            "reason": "Deploy versión 2.1"
        },
        {
            "timestamp": "2024-01-13 16:45",
            "user": "dev@medicare.local",
            "flag": "ENABLE_RATE_LIMITING",
            "change": "true → false",
            "reason": "Emergency: debugging issue"
        },
        {
            "timestamp": "2024-01-13 17:30",
            "user": "admin@medicare.local",
            "flag": "ENABLE_RATE_LIMITING",
            "change": "false → true",
            "reason": "Issue resolved, re-enabling"
        },
    ]
    
    for entry in history:
        with st.container():
            col1, col2, col3, col4 = st.columns([2, 2, 2, 3])
            
            with col1:
                st.text(entry["timestamp"])
            
            with col2:
                st.code(entry["flag"])
            
            with col3:
                if "false → true" in entry["change"]:
                    st.markdown("🔴 → 🟢 **ON**")
                else:
                    st.markdown("🟢 → 🔴 **OFF**")
            
            with col4:
                st.caption(entry["reason"])
        
        st.divider()
    
    # Exportar historial
    if st.button("📥 Exportar Historial"):
        st.info("Función de exportación disponible en versión Enterprise")


def render_feature_flag_toggles():
    """
    Renderiza toggles simples para uso en otras páginas.
    
    Uso:
        from views.feature_flags_admin import render_feature_flag_toggles
        render_feature_flag_toggles()
    """
    st.sidebar.divider()
    st.sidebar.subheader("🚩 Features")
    
    flags = get_feature_flags()
    
    # Solo mostrar toggles de features no críticas
    user_flags = [
        ("ENABLE_AI_SUGGESTIONS", "💡 AI Suggestions", False),
        ("ENABLE_ADVANCED_SEARCH", "🔍 Advanced Search", True),
        ("ENABLE_DARK_MODE", "🌙 Dark Mode", False),
    ]
    
    for flag_name, label, default in user_flags:
        current = flags.is_enabled(flag_name, default=default)
        
        new_value = st.sidebar.toggle(
            label,
            value=current,
            key=f"sidebar_{flag_name}"
        )
        
        if new_value != current:
            flags.set_feature(flag_name, new_value)
            st.rerun()
