"""
UI Professional - Sistema de interfaz moderna y profesional para Medicare Pro.

Características:
- Tema moderno con CSS personalizado
- Componentes reutilizables
- Animaciones suaves
- Responsive design
- Optimizado para millones de usuarios (lazy loading)
"""

from __future__ import annotations

import uuid
from typing import Any, Callable, Dict, List, Optional, Union

import streamlit as st

from core._ui_professional_css import CUSTOM_CSS, PROFESSIONAL_THEME



def apply_professional_theme():
    """Aplica el tema profesional a la aplicación."""
    st.html(CUSTOM_CSS)


# ============================================================
# COMPONENTES REUTILIZABLES
# ============================================================

def card(title: str, content: str, key: Optional[str] = None) -> str:
    """Genera HTML para una card profesional."""
    html = f"""
    <div class="card" id="{key or uuid.uuid4()}">
        <div class="card-header">
            <h4 class="card-title">{title}</h4>
        </div>
        <div class="card-body">
            {content}
        </div>
    </div>
    """
    return html


def metric_card(
    value: Union[int, float, str],
    label: str,
    delta: Optional[str] = None,
    delta_type: str = "neutral",
    icon: Optional[str] = None
) -> str:
    """Genera HTML para una métrica tipo KPI."""
    delta_class = "positive" if delta_type == "positive" else "negative" if delta_type == "negative" else "neutral"
    delta_html = f'<div class="metric-delta {delta_class}">{delta}</div>' if delta else ""
    icon_html = f"{icon} " if icon else ""
    
    html = f"""
    <div class="metric-card">
        <div class="metric-value">{icon_html}{value}</div>
        <div class="metric-label">{label}</div>
        {delta_html}
    </div>
    """
    return html


def badge(text: str, type_: str = "neutral") -> str:
    """Genera un badge de estado."""
    type_class = f"badge-{type_}"
    return f'<span class="badge {type_class}">{text}</span>'


def alert(message: str, type_: str = "info", icon: Optional[str] = None) -> str:
    """Genera una alerta."""
    icons = {
        "success": "✓",
        "warning": "⚠",
        "danger": "✕",
        "info": "ℹ"
    }
    icon_display = icon or icons.get(type_, "ℹ")
    
    return f"""
    <div class="alert alert-{type_}">
        <span style="font-size: 1.25rem;">{icon_display}</span>
        <div>{message}</div>
    </div>
    """


def data_table(headers: List[str], rows: List[List[Any]]) -> str:
    """Genera una tabla de datos profesional."""
    header_html = "".join([f"<th>{h}</th>" for h in headers])
    rows_html = ""
    for row in rows:
        cells = "".join([f"<td>{cell}</td>" for cell in row])
        rows_html += f"<tr>{cells}</tr>"
    
    return f"""
    <table class="data-table">
        <thead><tr>{header_html}</tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    """


def avatar(name: str) -> str:
    """Genera un avatar con las iniciales."""
    initials = "".join([n[0].upper() for n in name.split()[:2]])
    return f'<div class="avatar">{initials}</div>'


# ============================================================
# LAYOUT HELPERS
# ============================================================

def render_metrics_row(metrics: List[Dict[str, Any]]):
    """Renderiza una fila de métricas."""
    cols = st.columns(len(metrics))
    for i, metric in enumerate(metrics):
        with cols[i]:
            st.markdown(metric_card(**metric), unsafe_allow_html=True)


def render_card(title: str, content_func: Callable, key: Optional[str] = None):
    """Renderiza una card con contenido dinámico."""
    st.markdown(f"""
    <div class="card" id="{key or uuid.uuid4()}">
        <div class="card-header">
            <h4 class="card-title">{title}</h4>
        </div>
    </div>
    """, unsafe_allow_html=True)
    content_func()


def render_alert(message: str, type_: str = "info"):
    """Renderiza una alerta."""
    st.markdown(alert(message, type_), unsafe_allow_html=True)


def render_badge(text: str, type_: str = "neutral"):
    """Renderiza un badge."""
    st.markdown(badge(text, type_), unsafe_allow_html=True)


# ============================================================
# PAGE CONFIGURATION
# ============================================================

def configure_professional_page(
    title: str,
    icon: str = "🏥",
    layout: str = "wide",
    initial_sidebar_state: str = "expanded"
):
    """Configura la página con configuración profesional."""
    st.set_page_config(
        page_title=f"{icon} {title}",
        page_icon=icon,
        layout=layout,
        initial_sidebar_state=initial_sidebar_state,
        menu_items={
            'Get Help': 'https://github.com/enzogirardi84/medicare-pro-v2',
            'Report a bug': 'https://github.com/enzogirardi84/medicare-pro-v2/issues',
            'About': '## Medicare Pro\nSistema médico enterprise v2.0'
        }
    )
    
    # Aplicar tema CSS
    apply_professional_theme()
    
    # Configurar tema en session state
    st.session_state['ui_theme'] = 'professional'


# ============================================================
# NAVIGATION COMPONENTS
# ============================================================

def render_sidebar_nav(items: List[Dict[str, Any]], active: Optional[str] = None):
    """Renderiza navegación en sidebar."""
    st.sidebar.markdown("""
    <div style="padding: 1rem 0; border-bottom: 1px solid #E2E8F0; margin-bottom: 1rem;">
        <h3 style="margin: 0; color: #1E293B; font-size: 1.125rem;">📋 Menú</h3>
    </div>
    """, unsafe_allow_html=True)
    
    for item in items:
        is_active = item.get('id') == active
        bg_color = "#DBEAFE" if is_active else "transparent"
        text_color = "#2563EB" if is_active else "#64748B"
        
        st.sidebar.markdown(f"""
        <div style="
            padding: 0.5rem 0.75rem;
            border-radius: 8px;
            background: {bg_color};
            color: {text_color};
            font-weight: 500;
            cursor: pointer;
            margin-bottom: 0.25rem;
            transition: all 0.2s;
        ">
            {item.get('icon', '•')} {item.get('label', 'Item')}
        </div>
        """, unsafe_allow_html=True)


def render_page_header(title: str, subtitle: Optional[str] = None, actions: Optional[List] = None):
    """Renderiza el encabezado de página profesional."""
    col1, col2 = st.columns([3, 1])
    
    with col1:
        st.markdown(f"<h1>{title}</h1>", unsafe_allow_html=True)
        if subtitle:
            st.markdown(f"<p style='color: #64748B; font-size: 1.125rem; margin-top: -0.5rem;'>{subtitle}</p>", unsafe_allow_html=True)
    
    with col2:
        if actions:
            for action in actions:
                if st.button(action['label'], key=action.get('key'), type=action.get('type', 'secondary')):
                    action['callback']()


# ============================================================
# FORM COMPONENTS
# ============================================================

def form_input(label: str, key: str, type_: str = "text", **kwargs) -> Any:
    """Input de formulario consistente."""
    if type_ == "text":
        return st.text_input(label, key=key, **kwargs)
    elif type_ == "number":
        return st.number_input(label, key=key, **kwargs)
    elif type_ == "select":
        return st.selectbox(label, key=key, **kwargs)
    elif type_ == "date":
        return st.date_input(label, key=key, **kwargs)
    elif type_ == "textarea":
        return st.text_area(label, key=key, **kwargs)
    return None


def form_section(title: str, columns: int = 2):
    """Crea una sección de formulario con múltiples columnas."""
    st.markdown(f"<h3 style='margin-top: 1.5rem;'>{title}</h3>", unsafe_allow_html=True)
    return st.columns(columns)


# ============================================================
# LOADING & STATES
# ============================================================

def show_loading_skeleton(height: int = 100):
    """Muestra un skeleton de carga."""
    st.markdown(f'<div class="skeleton" style="height: {height}px;"></div>', unsafe_allow_html=True)


def show_spinner(text: str = "Cargando..."):
    """Wrapper para spinner con estilo consistente."""
    return st.spinner(text)


# ============================================================
# UTILITIES
# ============================================================

def get_initial_color(name: str) -> str:
    """Genera un color consistente basado en el nombre."""
    colors = [
        "#2563EB", "#7C3AED", "#DB2777", "#DC2626",
        "#EA580C", "#D97706", "#059669", "#0891B2"
    ]
    return colors[hash(name) % len(colors)]


def truncate_text(text: str, max_length: int = 50) -> str:
    """Trunca texto con ellipsis."""
    if len(text) <= max_length:
        return text
    return text[:max_length - 3] + "..."


def format_number(num: Union[int, float]) -> str:
    """Formatea números grandes."""
    if num >= 1_000_000:
        return f"{num / 1_000_000:.1f}M"
    elif num >= 1_000:
        return f"{num / 1_000:.1f}K"
    return str(num)


# ============================================================
# EJEMPLO DE USO
# ============================================================

if __name__ == "__main__":
    configure_professional_page("Demo UI", icon="🎨")
    
    render_page_header(
        "Dashboard Profesional",
        "Sistema de gestión médica Medicare Pro"
    )
    
    # Métricas
    render_metrics_row([
        {"value": "1,234", "label": "Pacientes", "delta": "+12%", "delta_type": "positive", "icon": "👥"},
        {"value": "89", "label": "Consultas hoy", "delta": "+5%", "delta_type": "positive", "icon": "📅"},
        {"value": "15", "label": "Urgencias", "delta": "-3%", "delta_type": "negative", "icon": "🚨"},
    ])
    
    # Alerta
    render_alert("Sistema funcionando correctamente. Último backup: hace 2 horas.", "success")
    
    # Card con tabla
    st.markdown(card("Últimos Pacientes", data_table(
        ["Nombre", "DNI", "Estado"],
        [
            ["Juan Pérez", "37.108.100", badge("Activo", "success")],
            ["María García", "29.456.789", badge("Pendiente", "warning")],
        ]
    )), unsafe_allow_html=True)