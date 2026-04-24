"""
Indicador de Estado de Conexión y Sincronización para MediCare.
Muestra estado Online/Offline, sincronización con Supabase y alertas de datos pendientes.
"""
import time
import threading
from typing import Optional, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

import streamlit as st


class ConnectionState(Enum):
    """Estados de conexión posibles."""
    ONLINE = "online"
    OFFLINE = "offline"
    SYNCING = "syncing"
    ERROR = "error"
    PENDING = "pending"  # Datos pendientes por sincronizar


@dataclass
class ConnectionStatus:
    """Estado completo de la conexión."""
    state: ConnectionState
    last_sync: Optional[str] = None
    pending_count: int = 0
    latency_ms: Optional[int] = None
    error_message: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "last_sync": self.last_sync,
            "pending_count": self.pending_count,
            "latency_ms": self.latency_ms,
            "error": self.error_message,
        }


class ConnectionMonitor:
    """
    Monitor de conexión en background.
    Detecta cambios de estado y actualiza la UI.
    """
    
    def __init__(self, check_interval: int = 30):
        self.check_interval = check_interval
        self._status = ConnectionStatus(ConnectionState.ONLINE)
        self._listeners: list[Callable] = []
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._pending_operations: list = []
    
    def start(self):
        """Iniciar monitoreo en background."""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._monitor_loop, daemon=True)
            self._thread.start()
    
    def stop(self):
        """Detener monitoreo."""
        self._running = False
    
    def _monitor_loop(self):
        """Loop de monitoreo continuo."""
        while self._running:
            try:
                self._check_connection()
                time.sleep(self.check_interval)
            except Exception as e:
                self._update_status(ConnectionState.ERROR, error=str(e))
    
    def _check_connection(self):
        """Verificar estado de conexión con Supabase."""
        try:
            # Intentar una operación simple (ping)
            from core.database import supabase
            
            if supabase is None:
                self._update_status(ConnectionState.OFFLINE, error="No hay conexión con Supabase")
                return
            
            # Medir latencia
            start = time.time()
            # Query simple para test
            response = supabase.table("pacientes").select("count", count="exact").limit(1).execute()
            latency = int((time.time() - start) * 1000)
            
            # Verificar datos pendientes
            pending = len(self._pending_operations)
            
            if pending > 0:
                self._update_status(
                    ConnectionState.PENDING,
                    latency_ms=latency,
                    pending_count=pending
                )
            else:
                self._update_status(
                    ConnectionState.ONLINE,
                    latency_ms=latency,
                    pending_count=0
                )
                
        except Exception as e:
            self._update_status(ConnectionState.ERROR, error=str(e))
    
    def _update_status(self, state: ConnectionState, latency_ms: int = None, 
                       pending_count: int = None, error: str = None):
        """Actualizar estado y notificar listeners."""
        old_state = self._status.state
        
        self._status.state = state
        self._status.last_sync = datetime.now().isoformat()
        if latency_ms:
            self._status.latency_ms = latency_ms
        if pending_count is not None:
            self._status.pending_count = pending_count
        if error:
            self._status.error_message = error
        
        # Notificar si cambió el estado
        if old_state != state:
            for listener in self._listeners:
                try:
                    listener(self._status)
                except:
                    pass
    
    def add_listener(self, callback: Callable[[ConnectionStatus], None]):
        """Agregar callback para cambios de estado."""
        self._listeners.append(callback)
    
    def get_status(self) -> ConnectionStatus:
        """Obtener estado actual."""
        return self._status
    
    def add_pending_operation(self, operation: dict):
        """Registrar operación pendiente."""
        self._pending_operations.append(operation)
        self._update_status(
            ConnectionState.PENDING,
            pending_count=len(self._pending_operations)
        )
    
    def clear_pending(self):
        """Limpiar operaciones pendientes."""
        self._pending_operations.clear()
        self._update_status(ConnectionState.ONLINE, pending_count=0)


# Instancia global
_connection_monitor: Optional[ConnectionMonitor] = None

def get_connection_monitor() -> ConnectionMonitor:
    """Obtener instancia del monitor."""
    global _connection_monitor
    if _connection_monitor is None:
        _connection_monitor = ConnectionMonitor()
    return _connection_monitor


# ============================================================
# COMPONENTES UI PARA STREAMLIT
# ============================================================

def render_connection_badge(
    position: str = "fixed",
    show_details: bool = True,
    key: str = "conn_badge",
) -> ConnectionStatus:
    """
    Renderizar badge de estado de conexión.
    
    Args:
        position: "fixed" (top-right) o "inline"
        show_details: Mostrar detalles al hacer hover
        key: Clave única
    
    Returns:
        ConnectionStatus actual
    """
    # Obtener estado
    monitor = get_connection_monitor()
    status = monitor.get_status()
    
    # Estilos según estado
    styles = {
        ConnectionState.ONLINE: {
            "bg": "rgba(34, 197, 94, 0.15)",
            "border": "rgba(34, 197, 94, 0.3)",
            "color": "#22c55e",
            "icon": "🟢",
            "text": "Online",
            "pulse": False,
        },
        ConnectionState.OFFLINE: {
            "bg": "rgba(239, 68, 68, 0.15)",
            "border": "rgba(239, 68, 68, 0.3)",
            "color": "#ef4444",
            "icon": "🔴",
            "text": "Offline",
            "pulse": True,
        },
        ConnectionState.SYNCING: {
            "bg": "rgba(59, 130, 246, 0.15)",
            "border": "rgba(59, 130, 246, 0.3)",
            "color": "#3b82f6",
            "icon": "🔄",
            "text": "Sincronizando...",
            "pulse": True,
        },
        ConnectionState.ERROR: {
            "bg": "rgba(245, 158, 11, 0.15)",
            "border": "rgba(245, 158, 11, 0.3)",
            "color": "#f59e0b",
            "icon": "⚠️",
            "text": "Error de conexión",
            "pulse": True,
        },
        ConnectionState.PENDING: {
            "bg": "rgba(139, 92, 246, 0.15)",
            "border": "rgba(139, 92, 246, 0.3)",
            "color": "#8b5cf6",
            "icon": "⏳",
            "text": f"{status.pending_count} pendientes",
            "pulse": True,
        },
    }
    
    style = styles.get(status.state, styles[ConnectionState.ERROR])
    
    # CSS para posición fija
    position_css = """
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 999999;
    """ if position == "fixed" else """
        display: inline-flex;
        margin-bottom: 0.5rem;
    """
    
    # Animación de pulso si es necesario
    pulse_animation = """
        @keyframes pulse-conn {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.7; transform: scale(1.05); }
        }
        .conn-pulse {
            animation: pulse-conn 2s ease-in-out infinite;
        }
    """ if style["pulse"] else ""
    
    # Detalles de tooltip
    details_html = ""
    if show_details:
        latency_text = f"{status.latency_ms}ms" if status.latency_ms else "N/A"
        last_sync = status.last_sync[:19] if status.last_sync else "Nunca"
        
        details_html = f"""
        <div style="
            position: absolute;
            top: 100%;
            right: 0;
            margin-top: 0.5rem;
            background: rgba(15, 23, 42, 0.95);
            border: 1px solid rgba(148, 163, 184, 0.2);
            border-radius: 8px;
            padding: 0.75rem;
            font-size: 0.8rem;
            color: #94a3b8;
            min-width: 200px;
            box-shadow: 0 10px 40px rgba(2, 6, 23, 0.4);
            opacity: 0;
            visibility: hidden;
            transition: all 0.25s ease;
            z-index: 1000000;
        " class="conn-tooltip">
            <div style="margin-bottom: 0.5rem;"><strong>Latencia:</strong> {latency_text}</div>
            <div style="margin-bottom: 0.5rem;"><strong>Última sync:</strong> {last_sync}</div>
            {f'<div style="color: #f59e0b;"><strong>Pendientes:</strong> {status.pending_count}</div>' if status.pending_count > 0 else ''}
            {f'<div style="color: #ef4444; margin-top: 0.5rem; font-size: 0.75rem;">{status.error_message}</div>' if status.error_message else ''}
        </div>
        """
    
    html = f"""
    <style>
        {pulse_animation}
        
        .conn-badge-container {{
            {position_css}
        }}
        
        .conn-badge-container:hover .conn-tooltip {{
            opacity: 1;
            visibility: visible;
        }}
        
        .conn-badge {{
            display: inline-flex;
            align-items: center;
            gap: 0.5rem;
            padding: 0.5rem 1rem;
            background: {style['bg']};
            border: 1px solid {style['border']};
            border-radius: 9999px;
            font-size: 0.875rem;
            font-weight: 500;
            color: {style['color']};
            backdrop-filter: blur(8px);
            cursor: default;
            transition: all 0.2s ease;
        }}
        
        .conn-badge:hover {{
            transform: translateY(-1px);
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
        }}
    </style>
    
    <div class="conn-badge-container">
        <div class="conn-badge {'conn-pulse' if style['pulse'] else ''}">
            <span>{style['icon']}</span>
            <span>{style['text']}</span>
        </div>
        {details_html}
    </div>
    """
    
    st.markdown(html, unsafe_allow_html=True)
    
    return status


def render_sync_button(
    on_sync: Optional[Callable] = None,
    key: str = "sync_button",
) -> bool:
    """
    Botón de sincronización manual con indicador de estado.
    
    Returns:
        True si se hizo clic en sincronizar
    """
    monitor = get_connection_monitor()
    status = monitor.get_status()
    
    # Estilo según estado
    button_disabled = status.state == ConnectionState.SYNCING
    
    cols = st.columns([1, 3])
    
    with cols[0]:
        clicked = st.button(
            "🔄" if not button_disabled else "⏳",
            key=f"{key}_btn",
            disabled=button_disabled,
            help="Sincronizar datos pendientes" if not button_disabled else "Sincronizando...",
        )
    
    with cols[1]:
        if status.pending_count > 0:
            st.caption(f"⏳ {status.pending_count} operaciones pendientes")
        elif status.last_sync:
            st.caption(f"✅ Sync: {status.last_sync[11:16]}")
        else:
            st.caption("Sin sincronizar")
    
    if clicked and on_sync:
        # Simular sincronización
        monitor._update_status(ConnectionState.SYNCING)
        try:
            on_sync()
            monitor.clear_pending()
            st.toast("✅ Sincronización completada")
        except Exception as e:
            monitor._update_status(ConnectionState.ERROR, error=str(e))
            st.toast(f"❌ Error: {e}")
    
    return clicked


def render_pending_data_alert(
    operations: list,
    on_retry: Optional[Callable] = None,
    key: str = "pending_alert",
):
    """
    Alerta visual cuando hay datos pendientes por sincronizar.
    
    Args:
        operations: Lista de operaciones pendientes
        on_retry: Callback para reintentar
    """
    if not operations:
        return
    
    with st.container():
        st.markdown(f"""
        <div style="
            background: linear-gradient(135deg, rgba(139, 92, 246, 0.15) 0%, rgba(124, 58, 237, 0.1) 100%);
            border: 1px solid rgba(139, 92, 246, 0.3);
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1rem;
        ">
            <div style="display: flex; align-items: center; gap: 0.75rem; margin-bottom: 0.75rem;">
                <span style="font-size: 1.5rem;">⏳</span>
                <div>
                    <div style="font-weight: 600; color: #c4b5fd;">Datos pendientes por sincronizar</div>
                    <div style="font-size: 0.875rem; color: #a78bfa;">
                        {len(operations)} operación(es) en cola
                    </div>
                </div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        
        # Listar operaciones
        for i, op in enumerate(operations[:5]):  # Mostrar máximo 5
            with st.expander(f"📋 {op.get('type', 'Operación')} - {op.get('timestamp', 'Sin fecha')[:10]}", expanded=False):
                st.json(op)
        
        if len(operations) > 5:
            st.caption(f"... y {len(operations) - 5} operaciones más")
        
        # Botón de reintento
        cols = st.columns([1, 1, 2])
        with cols[0]:
            if st.button("🔄 Reintentar todo", key=f"{key}_retry", use_container_width=True):
                if on_retry:
                    on_retry()
        
        with cols[1]:
            if st.button("❌ Descartar", key=f"{key}_discard", use_container_width=True):
                if st.checkbox("Confirmar descarte de datos", key=f"{key}_confirm"):
                    operations.clear()
                    st.rerun()


# ============================================================
# HOOKS PARA INTEGRACIÓN AUTOMÁTICA
# ============================================================

def init_connection_monitor():
    """Inicializar monitoreo de conexión en la app."""
    monitor = get_connection_monitor()
    monitor.start()
    
    # Guardar en session_state para persistencia
    st.session_state["_connection_monitor"] = monitor


def check_connection_before_operation(operation_name: str = "operación") -> bool:
    """
    Verificar conexión antes de operación crítica.
    Muestra warning si está offline.
    
    Returns:
        True si se puede continuar
    """
    monitor = get_connection_monitor()
    status = monitor.get_status()
    
    if status.state == ConnectionState.OFFLINE:
        st.warning(f"⚠️ Sin conexión. La {operation_name} se guardará localmente y se sincronizará cuando haya conexión.")
        return False
    
    if status.state == ConnectionState.ERROR:
        st.error(f"❌ Error de conexión: {status.error_message}")
        return st.checkbox("Forzar operación de todos modos (guardar localmente)", key="force_offline")
    
    return True


# ============================================================
# DEMO
# ============================================================

def demo_connection_status():
    """Demo interactiva del sistema de conexión."""
    st.markdown("## 🌐 Demo de Estado de Conexión")
    
    # Simular estados
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.button("🟢 Online", key="demo_online")
        st.caption("Estado: Conectado")
    
    with col2:
        st.button("🔴 Offline", key="demo_offline")
        st.caption("Estado: Sin conexión")
    
    with col3:
        st.button("🔄 Syncing", key="demo_syncing")
        st.caption("Estado: Sincronizando")
    
    with col4:
        st.button("⚠️ Error", key="demo_error")
        st.caption("Estado: Error de conexión")
    
    with col5:
        st.button("⏳ Pending", key="demo_pending")
        st.caption("Estado: Datos pendientes")
    
    st.markdown("---")
    st.markdown("### Badge de Conexión")
    
    # Renderizar badge actual
    status = render_connection_badge(position="inline", show_details=True)
    
    st.json(status.to_dict())
    
    st.markdown("---")
    st.markdown("### Botón de Sincronización")
    render_sync_button(on_sync=lambda: time.sleep(1))
