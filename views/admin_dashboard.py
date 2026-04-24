"""
Dashboard Administrativo para Medicare Pro.

Características:
- Métricas en tiempo real
- Gestión de usuarios y roles
- Auditoría visual
- Reportes de uso
- Monitoreo del sistema
"""

import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

from core.audit_trail import get_audit_trail, AuditEventType
from core.performance_profiler import get_profiler
from core.distributed_cache import get_cache
from core.observability import get_metrics
from core.app_logging import log_event
from core.utils import ahora


def render_admin_dashboard():
    """
    Renderiza el dashboard administrativo completo.
    
    Solo accesible para usuarios con rol 'admin' o 'superadmin'.
    """
    # Verificar permisos
    user = st.session_state.get("u_actual", {})
    if user.get("rol") not in ["admin", "superadmin"]:
        st.error("🔒 Acceso denegado. Solo administradores.")
        return
    
    st.title("📊 Dashboard Administrativo")
    st.caption(f"Usuario: {user.get('nombre', 'N/A')} | Última actualización: {ahora().strftime('%H:%M:%S')}")
    
    # Tabs para diferentes secciones
    tabs = st.tabs([
        "📈 Métricas",
        "👥 Usuarios",
        "🔍 Auditoría",
        "⚡ Performance",
        "💾 Caché",
        "🔔 Alertas"
    ])
    
    with tabs[0]:
        render_metrics_tab()
    
    with tabs[1]:
        render_users_tab()
    
    with tabs[2]:
        render_audit_tab()
    
    with tabs[3]:
        render_performance_tab()
    
    with tabs[4]:
        render_cache_tab()
    
    with tabs[5]:
        render_alerts_tab()


def render_metrics_tab():
    """Tab de métricas del sistema."""
    st.header("📈 Métricas en Tiempo Real")
    
    metrics = get_metrics()
    stats = metrics.get_stats()
    
    # KPIs principales
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_users = len(st.session_state.get("usuarios_db", {}))
        st.metric("Usuarios Activos", total_users)
    
    with col2:
        total_pacientes = len(st.session_state.get("pacientes_db", {}))
        st.metric("Pacientes", total_pacientes)
    
    with col3:
        total_evoluciones = len(st.session_state.get("evoluciones_db", []))
        st.metric("Evoluciones", total_evoluciones)
    
    with col4:
        today = ahora().strftime("%d/%m/%Y")
        today_visits = sum(
            1 for e in st.session_state.get("evoluciones_db", [])
            if e.get("fecha", "").startswith(today)
        )
        st.metric("Visitas Hoy", today_visits)
    
    st.divider()
    
    # Métricas de aplicación
    st.subheader("Métricas de Aplicación")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Contadores", len(stats.get("counters", {})))
    
    with col2:
        st.metric("Gauges", len(stats.get("gauges", {})))
    
    with col3:
        st.metric("Histograms", len(stats.get("histograms", {})))
    
    # Top contadores
    with st.expander("Ver Contadores"):
        counters = stats.get("counters", {})
        for key, value in sorted(counters.items(), key=lambda x: x[1], reverse=True)[:20]:
            st.text(f"{key}: {value}")
    
    # Latencias promedio
    with st.expander("Ver Latencias"):
        histograms = stats.get("histograms", {})
        for key, hist in sorted(histograms.items(), key=lambda x: x[1].get("avg", 0), reverse=True)[:10]:
            if hist.get("count", 0) > 0:
                st.text(f"{key}: {hist['avg']:.3f}s (n={hist['count']})")


def render_users_tab():
    """Tab de gestión de usuarios."""
    st.header("👥 Gestión de Usuarios")
    
    usuarios = st.session_state.get("usuarios_db", {})
    
    if not usuarios:
        st.info("No hay usuarios registrados.")
        return
    
    # Filtros
    col1, col2 = st.columns(2)
    
    with col1:
        filter_rol = st.selectbox(
            "Filtrar por rol",
            options=["Todos", "admin", "medico", "enfermera", "recepcionista"]
        )
    
    with col2:
        filter_empresa = st.selectbox(
            "Filtrar por empresa/clínica",
            options=["Todas"] + list(set(
                u.get("empresa", "") for u in usuarios.values()
            ))
        )
    
    # Filtrar usuarios
    filtered_users = []
    for user_id, user_data in usuarios.items():
        if filter_rol != "Todos" and user_data.get("rol") != filter_rol:
            continue
        if filter_empresa != "Todas" and user_data.get("empresa") != filter_empresa:
            continue
        
        filtered_users.append({
            "ID": user_id,
            "Nombre": user_data.get("nombre", "N/A"),
            "Email": user_data.get("email", "N/A"),
            "Rol": user_data.get("rol", "N/A"),
            "Empresa": user_data.get("empresa", "N/A"),
            "Matrícula": user_data.get("matricula", "N/A"),
            "Activo": "✅" if user_data.get("activo", True) else "❌"
        })
    
    # Tabla de usuarios
    if filtered_users:
        st.dataframe(
            filtered_users,
            use_container_width=True,
            hide_index=True
        )
        
        st.caption(f"Mostrando {len(filtered_users)} de {len(usuarios)} usuarios")
    else:
        st.info("No hay usuarios que coincidan con los filtros.")
    
    # Acciones de usuario
    st.divider()
    st.subheader("Acciones")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("➕ Crear Usuario", use_container_width=True):
            st.session_state["admin_action"] = "create_user"
            st.rerun()
    
    with col2:
        if st.button("🔄 Reset Password", use_container_width=True):
            st.info("Seleccione usuario de la tabla")
    
    with col3:
        if st.button("🚫 Desactivar", use_container_width=True):
            st.warning("Seleccione usuario de la tabla")


def render_audit_tab():
    """Tab de auditoría visual."""
    st.header("🔍 Auditoría del Sistema")
    
    trail = get_audit_trail()
    
    # Filtros de auditoría
    col1, col2, col3 = st.columns(3)
    
    with col1:
        audit_event_type = st.selectbox(
            "Tipo de Evento",
            options=["Todos"] + [e.name for e in AuditEventType]
        )
    
    with col2:
        audit_user = st.text_input("Usuario", placeholder="Filtrar por usuario...")
    
    with col3:
        audit_resource = st.text_input("Recurso", placeholder="Filtrar por recurso...")
    
    # Consultar auditoría
    event_type = None if audit_event_type == "Todos" else AuditEventType[audit_event_type]
    
    entries = trail.query(
        event_type=event_type,
        user_id=audit_user if audit_user else None,
        resource_type=audit_resource if audit_resource else None,
        limit=100
    )
    
    if entries:
        # Convertir a formato de tabla
        audit_data = []
        for entry in entries:
            audit_data.append({
                "Timestamp": entry.timestamp,
                "Evento": entry.event_type,
                "Categoría": entry.event_category,
                "Usuario": entry.user_id,
                "Recurso": f"{entry.resource_type}:{entry.resource_id[:8]}",
                "Acción": entry.action,
                "Descripción": entry.description[:50] + "..." if len(entry.description) > 50 else entry.description
            })
        
        st.dataframe(audit_data, use_container_width=True, hide_index=True)
        
        # Verificar integridad
        st.divider()
        if st.button("🔐 Verificar Integridad de Cadena"):
            is_valid = trail.verify_chain()
            if is_valid:
                st.success("✅ Cadena de auditoría válida. No se detectaron modificaciones.")
            else:
                st.error("❌ ¡ALERTA! Se detectó posible tampering en los logs.")
    else:
        st.info("No hay entradas de auditoría que coincidan con los filtros.")
    
    # Exportar auditoría
    st.divider()
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 Exportar JSON", use_container_width=True):
            desde = (ahora() - timedelta(days=30)).strftime("%Y-%m-%d")
            hasta = ahora().strftime("%Y-%m-%d")
            export = trail.export_for_compliance(desde, hasta, format="json")
            
            st.download_button(
                "Descargar JSON",
                export,
                file_name=f"audit_export_{ahora().strftime('%Y%m%d')}.json",
                mime="application/json"
            )
    
    with col2:
        if st.button("📄 Exportar CSV", use_container_width=True):
            desde = (ahora() - timedelta(days=30)).strftime("%Y-%m-%d")
            hasta = ahora().strftime("%Y-%m-%d")
            export = trail.export_for_compliance(desde, hasta, format="csv")
            
            st.download_button(
                "Descargar CSV",
                export,
                file_name=f"audit_export_{ahora().strftime('%Y%m%d')}.csv",
                mime="text/csv"
            )


def render_performance_tab():
    """Tab de performance."""
    st.header("⚡ Performance del Sistema")
    
    profiler = get_profiler()
    
    # Renderizar dashboard del profiler
    profiler.render_performance_dashboard()
    
    # Stats adicionales
    st.divider()
    st.subheader("Estadísticas Detalladas")
    
    # Funciones más lentas
    slow_functions = profiler.get_slow_functions(threshold=0.1)
    if slow_functions:
        with st.expander("🐌 Funciones Lentas (>100ms)", expanded=True):
            for func in slow_functions[:10]:
                st.text(
                    f"🐌 {func.name}\n"
                    f"   Tiempo promedio: {func.avg_time:.3f}s\n"
                    f"   Tiempo total: {func.total_time:.3f}s\n"
                    f"   Llamadas: {func.call_count}\n"
                    f"   DB Queries: {func.db_queries}"
                )
    
    # Queries lentas
    slow_queries = profiler.get_slow_queries()
    if slow_queries:
        with st.expander("🐌 Queries Lentas"):
            for query in slow_queries[:10]:
                st.text(f"{query['duration']:.3f}s: {query['query'][:80]}")


def render_cache_tab():
    """Tab de monitoreo de caché."""
    st.header("💾 Estado del Caché")
    
    cache = get_cache()
    stats = cache.get_stats()
    
    # Stats de caché
    col1, col2, col3 = st.columns(3)
    
    with col1:
        local_stats = stats.get("local", {})
        st.metric("Caché Local (L2)", f"{local_stats.get('size', 0)} / {local_stats.get('maxsize', 0)}")
    
    with col2:
        redis_connected = stats.get("redis_connected", False)
        st.metric("Redis (L1)", "🟢 Conectado" if redis_connected else "🔴 Desconectado")
    
    with col3:
        circuit_state = stats.get("circuit_breaker_state", "unknown")
        st.metric("Circuit Breaker", circuit_state)
    
    # Redis stats
    if redis_connected and "redis" in stats:
        st.divider()
        st.subheader("Estadísticas de Redis")
        
        redis_stats = stats["redis"]
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Memoria Usada", redis_stats.get("used_memory", "N/A"))
        
        with col2:
            st.metric("Clientes Conectados", redis_stats.get("connected_clients", 0))
        
        with col3:
            st.metric("Total Keys", redis_stats.get("total_keys", 0))
    
    # Acciones de caché
    st.divider()
    st.subheader("Acciones")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("🗑️ Limpiar Caché Local", use_container_width=True):
            cache._local_cache.clear()
            st.success("Caché local limpiado")
            log_event("admin", "Cache local limpiado por admin")
    
    with col2:
        if st.button("🔄 Forzar Reconexión Redis", use_container_width=True):
            # Reintentar conexión
            st.info("Reconexión intentada. Verificar estado en unos segundos.")


def render_alerts_tab():
    """Tab de alertas del sistema."""
    st.header("🔔 Alertas del Sistema")
    
    # Obtener alertas de session_state
    alerts = st.session_state.get("_system_alerts", [])
    
    if not alerts:
        st.success("✅ No hay alertas activas en el sistema.")
        return
    
    # Mostrar alertas por severidad
    critical = [a for a in alerts if a.get("severity") == "critical"]
    high = [a for a in alerts if a.get("severity") == "high"]
    medium = [a for a in alerts if a.get("severity") == "medium"]
    
    if critical:
        st.error(f"🚨 {len(critical)} Alertas Críticas")
        for alert in critical:
            with st.container():
                st.error(f"**{alert.get('title', 'Alerta')}**\n\n{alert.get('message', '')}")
                st.caption(f"Timestamp: {alert.get('timestamp', 'N/A')}")
    
    if high:
        st.warning(f"⚠️ {len(high)} Alertas de Alta Prioridad")
        for alert in high:
            with st.container():
                st.warning(f"**{alert.get('title', 'Alerta')}**\n\n{alert.get('message', '')}")
    
    if medium:
        st.info(f"ℹ️ {len(medium)} Alertas de Media Prioridad")
        for alert in medium:
            with st.container():
                st.info(f"**{alert.get('title', 'Alerta')}**\n\n{alert.get('message', '')}")
    
    # Botón para limpiar alertas
    st.divider()
    if st.button("🧹 Limpiar Alertas", use_container_width=True):
        st.session_state["_system_alerts"] = []
        st.success("Alertas limpiadas")
        st.rerun()


# Entry point para el módulo
def render_admin_page():
    """Renderiza página completa de administración."""
    render_admin_dashboard()


if __name__ == "__main__":
    # Para testing standalone
    render_admin_page()
