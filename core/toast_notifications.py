"""
Sistema de notificaciones Toast moderno para MediCare.
Notificaciones visuales temporales con animaciones suaves.
"""
import html
from typing import Optional
from dataclasses import dataclass
from datetime import datetime

import streamlit as st


@dataclass
class Toast:
    """Representa una notificación toast."""
    id: str
    message: str
    type: str  # success, error, warning, info
    title: Optional[str] = None
    duration: int = 5000  # ms
    created_at: str = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now().isoformat()


class ToastType:
    """Tipos de toast con sus estilos."""
    SUCCESS = {
        "icon": "✅",
        "title": "Éxito",
        "gradient": "linear-gradient(135deg, #22c55e 0%, #16a34a 100%)",
        "bg": "rgba(34, 197, 94, 0.15)",
        "border": "rgba(34, 197, 94, 0.3)",
        "text": "#86efac",
    }
    ERROR = {
        "icon": "❌",
        "title": "Error",
        "gradient": "linear-gradient(135deg, #ef4444 0%, #dc2626 100%)",
        "bg": "rgba(239, 68, 68, 0.15)",
        "border": "rgba(239, 68, 68, 0.3)",
        "text": "#fca5a5",
    }
    WARNING = {
        "icon": "⚠️",
        "title": "Advertencia",
        "gradient": "linear-gradient(135deg, #f59e0b 0%, #d97706 100%)",
        "bg": "rgba(245, 158, 11, 0.15)",
        "border": "rgba(245, 158, 11, 0.3)",
        "text": "#fcd34d",
    }
    INFO = {
        "icon": "ℹ️",
        "title": "Información",
        "gradient": "linear-gradient(135deg, #3b82f6 0%, #2563eb 100%)",
        "bg": "rgba(59, 130, 246, 0.15)",
        "border": "rgba(59, 130, 246, 0.3)",
        "text": "#93c5fd",
    }


def get_toast_styles(toast_type: str) -> dict:
    """Obtener estilos para un tipo de toast."""
    styles = {
        "success": ToastType.SUCCESS,
        "error": ToastType.ERROR,
        "warning": ToastType.WARNING,
        "info": ToastType.INFO,
    }
    return styles.get(toast_type, ToastType.INFO)


def generate_toast_html(
    message: str,
    toast_type: str = "info",
    title: Optional[str] = None,
    toast_id: Optional[str] = None,
) -> str:
    """
    Generar HTML para un toast notification.
    
    Args:
        message: Mensaje principal
        toast_type: success, error, warning, info
        title: Título opcional (si no, usa el default del tipo)
        toast_id: ID único para el toast
    
    Returns:
        HTML string del toast
    """
    styles = get_toast_styles(toast_type)
    display_title = title or styles["title"]
    toast_id = toast_id or f"toast_{hash(message + datetime.now().isoformat())}"
    
    return f"""
    <div id="{toast_id}" class="mc-toast mc-toast-{toast_type}">
        <div class="mc-toast-icon">{styles["icon"]}</div>
        <div class="mc-toast-content">
            <div class="mc-toast-title">{html.escape(display_title)}</div>
            <div class="mc-toast-message">{html.escape(message)}</div>
        </div>
        <button class="mc-toast-close" onclick="this.parentElement.remove()">×</button>
    </div>
    """


def inject_toast_css():
    """Inyectar CSS necesario para los toasts."""
    css = """
    <style>
    /* Toast Container */
    .mc-toast-container {
        position: fixed;
        top: 1rem;
        right: 1rem;
        z-index: 999999;
        display: flex;
        flex-direction: column;
        gap: 0.75rem;
        max-width: 400px;
        pointer-events: none;
    }
    
    /* Toast Individual */
    .mc-toast {
        display: flex;
        align-items: flex-start;
        gap: 0.875rem;
        padding: 1rem 1.25rem;
        border-radius: 12px;
        backdrop-filter: blur(12px);
        box-shadow: 0 10px 40px rgba(2, 6, 23, 0.4);
        pointer-events: auto;
        animation: mc-toast-in 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards,
                   mc-toast-out 0.3s ease-in 4.7s forwards;
        position: relative;
        overflow: hidden;
    }
    
    .mc-toast::before {
        content: "";
        position: absolute;
        left: 0;
        top: 0;
        bottom: 0;
        width: 4px;
    }
    
    /* Toast Types */
    .mc-toast-success {
        background: linear-gradient(135deg, rgba(34, 197, 94, 0.15) 0%, rgba(22, 163, 74, 0.1) 100%);
        border: 1px solid rgba(34, 197, 94, 0.25);
    }
    .mc-toast-success::before {
        background: linear-gradient(180deg, #22c55e 0%, #16a34a 100%);
    }
    .mc-toast-success .mc-toast-icon {
        background: rgba(34, 197, 94, 0.2);
        color: #86efac;
    }
    .mc-toast-success .mc-toast-title {
        color: #86efac;
    }
    
    .mc-toast-error {
        background: linear-gradient(135deg, rgba(239, 68, 68, 0.15) 0%, rgba(220, 38, 38, 0.1) 100%);
        border: 1px solid rgba(239, 68, 68, 0.25);
    }
    .mc-toast-error::before {
        background: linear-gradient(180deg, #ef4444 0%, #dc2626 100%);
    }
    .mc-toast-error .mc-toast-icon {
        background: rgba(239, 68, 68, 0.2);
        color: #fca5a5;
    }
    .mc-toast-error .mc-toast-title {
        color: #fca5a5;
    }
    
    .mc-toast-warning {
        background: linear-gradient(135deg, rgba(245, 158, 11, 0.15) 0%, rgba(217, 119, 6, 0.1) 100%);
        border: 1px solid rgba(245, 158, 11, 0.25);
    }
    .mc-toast-warning::before {
        background: linear-gradient(180deg, #f59e0b 0%, #d97706 100%);
    }
    .mc-toast-warning .mc-toast-icon {
        background: rgba(245, 158, 11, 0.2);
        color: #fcd34d;
    }
    .mc-toast-warning .mc-toast-title {
        color: #fcd34d;
    }
    
    .mc-toast-info {
        background: linear-gradient(135deg, rgba(59, 130, 246, 0.15) 0%, rgba(37, 99, 235, 0.1) 100%);
        border: 1px solid rgba(59, 130, 246, 0.25);
    }
    .mc-toast-info::before {
        background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
    }
    .mc-toast-info .mc-toast-icon {
        background: rgba(59, 130, 246, 0.2);
        color: #93c5fd;
    }
    .mc-toast-info .mc-toast-title {
        color: #93c5fd;
    }
    
    /* Toast Elements */
    .mc-toast-icon {
        width: 40px;
        height: 40px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 1.25rem;
        flex-shrink: 0;
    }
    
    .mc-toast-content {
        flex: 1;
        min-width: 0;
    }
    
    .mc-toast-title {
        font-weight: 600;
        font-size: 0.95rem;
        margin-bottom: 0.25rem;
    }
    
    .mc-toast-message {
        color: #cbd5e1;
        font-size: 0.875rem;
        line-height: 1.5;
        word-wrap: break-word;
    }
    
    .mc-toast-close {
        background: none;
        border: none;
        color: #64748b;
        font-size: 1.5rem;
        cursor: pointer;
        padding: 0;
        width: 28px;
        height: 28px;
        display: flex;
        align-items: center;
        justify-content: center;
        border-radius: 6px;
        transition: all 0.2s ease;
        flex-shrink: 0;
        margin-top: -0.25rem;
        margin-right: -0.25rem;
    }
    
    .mc-toast-close:hover {
        background: rgba(255, 255, 255, 0.1);
        color: #f1f5f9;
    }
    
    /* Animations */
    @keyframes mc-toast-in {
        0% {
            opacity: 0;
            transform: translateX(100px) scale(0.9);
        }
        100% {
            opacity: 1;
            transform: translateX(0) scale(1);
        }
    }
    
    @keyframes mc-toast-out {
        0% {
            opacity: 1;
            transform: translateX(0) scale(1);
        }
        100% {
            opacity: 0;
            transform: translateX(50px) scale(0.95);
        }
    }
    
    /* Progress bar */
    .mc-toast::after {
        content: "";
        position: absolute;
        bottom: 0;
        left: 0;
        height: 3px;
        background: rgba(255, 255, 255, 0.3);
        animation: mc-toast-progress 5s linear forwards;
        border-radius: 0 0 0 12px;
    }
    
    @keyframes mc-toast-progress {
        0% { width: 100%; }
        100% { width: 0%; }
    }
    
    /* Mobile */
    @media (max-width: 640px) {
        .mc-toast-container {
            top: auto;
            bottom: 1rem;
            left: 1rem;
            right: 1rem;
            max-width: none;
        }
        
        .mc-toast {
            animation: mc-toast-in-mobile 0.4s cubic-bezier(0.175, 0.885, 0.32, 1.275) forwards,
                       mc-toast-out-mobile 0.3s ease-in 4.7s forwards;
        }
        
        @keyframes mc-toast-in-mobile {
            0% {
                opacity: 0;
                transform: translateY(50px) scale(0.9);
            }
            100% {
                opacity: 1;
                transform: translateY(0) scale(1);
            }
        }
        
        @keyframes mc-toast-out-mobile {
            0% {
                opacity: 1;
                transform: translateY(0) scale(1);
            }
            100% {
                opacity: 0;
                transform: translateY(20px) scale(0.95);
            }
        }
    }
    
    /* Reduced motion */
    @media (prefers-reduced-motion: reduce) {
        .mc-toast {
            animation: none;
        }
        .mc-toast::after {
            animation: none;
        }
    }
    </style>
    """
    st.markdown(css, unsafe_allow_html=True)


def show_toast(
    message: str,
    toast_type: str = "info",
    title: Optional[str] = None,
):
    """
    Mostrar un toast notification.
    
    Args:
        message: Mensaje del toast
        toast_type: success, error, warning, info
        title: Título opcional
    """
    # Inyectar CSS si no está
    inject_toast_css()
    
    # Generar HTML del toast
    toast_html = generate_toast_html(message, toast_type, title)
    
    # Crear container y mostrar
    st.markdown(
        f'<div class="mc-toast-container">{toast_html}</div>',
        unsafe_allow_html=True
    )


# Funciones de conveniencia
def toast_success(message: str, title: Optional[str] = None):
    """Toast de éxito."""
    show_toast(message, "success", title)


def toast_error(message: str, title: Optional[str] = None):
    """Toast de error."""
    show_toast(message, "error", title)


def toast_warning(message: str, title: Optional[str] = None):
    """Toast de advertencia."""
    show_toast(message, "warning", title)


def toast_info(message: str, title: Optional[str] = None):
    """Toast de información."""
    show_toast(message, "info", title)


# ============================================================
# QUEUE DE TOASTS (múltiples notificaciones)
# ============================================================

def queue_toast(
    message: str,
    toast_type: str = "info",
    title: Optional[str] = None,
):
    """
    Agregar toast a una cola para mostrar múltiples notificaciones.
    Útil cuando se realizan varias acciones seguidas.
    """
    if "_toast_queue" not in st.session_state:
        st.session_state._toast_queue = []
    
    st.session_state._toast_queue.append({
        "message": message,
        "type": toast_type,
        "title": title,
    })


def render_queued_toasts():
    """Renderizar todos los toasts en la cola."""
    inject_toast_css()
    
    if "_toast_queue" not in st.session_state:
        return
    
    queue = st.session_state._toast_queue
    if not queue:
        return
    
    # Generar HTML de todos los toasts
    toasts_html = []
    for item in queue:
        toast = generate_toast_html(
            item["message"],
            item["type"],
            item["title"]
        )
        toasts_html.append(toast)
    
    # Mostrar container con todos
    st.markdown(
        f'<div class="mc-toast-container">{ "".join(toasts_html) }</div>',
        unsafe_allow_html=True
    )
    
    # Limpiar cola
    st.session_state._toast_queue = []


# ============================================================
# INTEGRACIÓN CON ACCIONES COMUNES
# ============================================================

def toast_guardado_exitoso(entidad: str = "Registro"):
    """Toast estándar para guardado exitoso."""
    toast_success(f"{entidad} guardado correctamente", "Guardado")


def toast_error_guardando(error: str):
    """Toast estándar para error al guardar."""
    toast_error(f"Error al guardar: {error}", "Error")


def toast_eliminado_exitoso(entidad: str = "Registro"):
    """Toast estándar para eliminación."""
    toast_success(f"{entidad} eliminado correctamente", "Eliminado")


def toast_backup_generado(filename: str):
    """Toast para backup generado."""
    toast_success(f"Backup generado: {filename}", "Backup Completo")


def toast_pdf_generado(filename: str):
    """Toast para PDF generado."""
    toast_success(f"PDF generado: {filename}", "Documento Listo")


def toast_sesion_expirada():
    """Toast para sesión expirada."""
    toast_warning("Tu sesión ha expirado. Por favor, inicia sesión nuevamente.", "Sesión Expirada")


def toast_datos_actualizados():
    """Toast para datos sincronizados."""
    toast_info("Datos sincronizados con el servidor", "Sincronización")


def toast_validacion_errores(errores: list):
    """Toast para errores de validación."""
    errores_str = "; ".join(errores[:3])  # Max 3 errores
    if len(errores) > 3:
        errores_str += f" y {len(errores) - 3} más"
    toast_error(errores_str, "Errores de Validación")


# ============================================================
# DEMO
# ============================================================

def demo_toasts():
    """Demo interactiva de todos los tipos de toast."""
    st.markdown("## 🔔 Demo de Toast Notifications")
    st.caption("Sistema de notificaciones moderno con animaciones suaves")
    
    cols = st.columns(4)
    
    with cols[0]:
        if st.button("✅ Éxito", width='stretch'):
            toast_success("Operación completada exitosamente", "Guardado")
    
    with cols[1]:
        if st.button("❌ Error", width='stretch'):
            toast_error("No se pudo conectar con el servidor", "Error de Conexión")
    
    with cols[2]:
        if st.button("⚠️ Advertencia", width='stretch'):
            toast_warning("Algunos campos están incompletos", "Atención")
    
    with cols[3]:
        if st.button("ℹ️ Info", width='stretch'):
            toast_info("Sincronización completada", "Actualización")
    
    st.markdown("---")
    st.markdown("### Múltiples Toasts")
    
    if st.button("🎬 Mostrar múltiples notificaciones"):
        queue_toast("Paciente actualizado", "success", "Éxito")
        queue_toast("Sincronizando con Supabase...", "info", "Sincronización")
        queue_toast("Se detectaron 3 registros pendientes", "warning", "Pendientes")
        render_queued_toasts()
    
    st.markdown("---")
    st.markdown("### Toasts de Acciones Comunes")
    
    cols2 = st.columns(3)
    
    with cols2[0]:
        if st.button("💾 Guardar", width='stretch'):
            toast_guardado_exitoso("Evolución")
    
    with cols2[1]:
        if st.button("🗑️ Eliminar", width='stretch'):
            toast_eliminado_exitoso("Registro")
    
    with cols2[2]:
        if st.button("📄 Generar PDF", width='stretch'):
            toast_pdf_generado("historia_clinica_001.pdf")
