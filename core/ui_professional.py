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

import base64
import uuid
from typing import Any, Callable, Dict, List, Optional, Union
from functools import lru_cache

import streamlit as st

# ============================================================
# CONFIGURACIÓN DE TEMA Y CSS GLOBAL
# ============================================================

PROFESSIONAL_THEME = {
    "primaryColor": "#2563EB",  # Azul profesional
    "backgroundColor": "#F8FAFC",  # Gris muy claro
    "secondaryBackgroundColor": "#FFFFFF",  # Blanco
    "textColor": "#1E293B",  # Slate oscuro
    "font": "Inter",
    "baseFontSize": "16px",
}

CUSTOM_CSS = """
<style>
    /* Fuentes */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    /* Variables CSS */
    :root {
        --primary: #2563EB;
        --primary-dark: #1D4ED8;
        --primary-light: #DBEAFE;
        --secondary: #64748B;
        --success: #10B981;
        --warning: #F59E0B;
        --danger: #EF4444;
        --info: #06B6D4;
        --background: #F8FAFC;
        --surface: #FFFFFF;
        --text-primary: #1E293B;
        --text-secondary: #64748B;
        --border: #E2E8F0;
        --radius: 8px;
        --shadow-sm: 0 1px 2px 0 rgba(0, 0, 0, 0.05);
        --shadow: 0 1px 3px 0 rgba(0, 0, 0, 0.1), 0 1px 2px 0 rgba(0, 0, 0, 0.06);
        --shadow-lg: 0 10px 15px -3px rgba(0, 0, 0, 0.1), 0 4px 6px -2px rgba(0, 0, 0, 0.05);
    }
    
    /* Main container */
    .main .block-container {
        padding: 2rem 3rem;
        max-width: 1400px;
    }
    
    /* Headers */
    h1 {
        color: var(--text-primary);
        font-weight: 700;
        font-size: 2rem;
        margin-bottom: 0.5rem;
    }
    
    h2 {
        color: var(--text-primary);
        font-weight: 600;
        font-size: 1.5rem;
        margin-top: 1.5rem;
        margin-bottom: 0.75rem;
    }
    
    h3 {
        color: var(--text-primary);
        font-weight: 600;
        font-size: 1.25rem;
        margin-top: 1rem;
        margin-bottom: 0.5rem;
    }
    
    /* Cards */
    .card {
        background: var(--surface);
        border-radius: var(--radius);
        padding: 1.5rem;
        box-shadow: var(--shadow);
        border: 1px solid var(--border);
        margin-bottom: 1rem;
        transition: box-shadow 0.2s ease, transform 0.2s ease;
    }
    
    .card:hover {
        box-shadow: var(--shadow-lg);
    }
    
    .card-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        margin-bottom: 1rem;
        padding-bottom: 0.75rem;
        border-bottom: 1px solid var(--border);
    }
    
    .card-title {
        font-size: 1.125rem;
        font-weight: 600;
        color: var(--text-primary);
        margin: 0;
    }
    
    /* Metric cards */
    .metric-card {
        background: var(--surface);
        border-radius: var(--radius);
        padding: 1.25rem;
        box-shadow: var(--shadow);
        border-left: 4px solid var(--primary);
        transition: transform 0.2s ease;
    }
    
    .metric-card:hover {
        transform: translateY(-2px);
    }
    
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: var(--text-primary);
        line-height: 1;
    }
    
    .metric-label {
        font-size: 0.875rem;
        color: var(--text-secondary);
        margin-top: 0.25rem;
    }
    
    .metric-delta {
        font-size: 0.75rem;
        margin-top: 0.5rem;
    }
    
    .metric-delta.positive {
        color: var(--success);
    }
    
    .metric-delta.negative {
        color: var(--danger);
    }
    
    /* Status badges */
    .badge {
        display: inline-flex;
        align-items: center;
        padding: 0.25rem 0.75rem;
        border-radius: 9999px;
        font-size: 0.75rem;
        font-weight: 500;
    }
    
    .badge-success {
        background: #D1FAE5;
        color: #065F46;
    }
    
    .badge-warning {
        background: #FEF3C7;
        color: #92400E;
    }
    
    .badge-danger {
        background: #FEE2E2;
        color: #991B1B;
    }
    
    .badge-info {
        background: #CFFAFE;
        color: #155E75;
    }
    
    .badge-neutral {
        background: #F1F5F9;
        color: #475569;
    }
    
    /* =====================================================
       BUTTONS - GREEN THEME - USA data-testid MODERNO
       ===================================================== */

    /* BASE: todos los botones visibles */
    .stButton > button,
    [data-testid="stDownloadButton"] > button,
    [data-testid="stFormSubmitButton"] > button,
    .stButton button {
        opacity: 1 !important;
        visibility: visible !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        min-height: 2.5rem !important;
        font-family: system-ui, -apple-system, sans-serif !important;
    }

    /* PRIMARY - Verde con texto blanco (selector viejo + nuevo Streamlit) */
    .stButton > button[kind="primary"],
    [data-testid="baseButton-primary"],
    [data-testid="stBaseButton-primary"],
    [data-testid="stFormSubmitButton"] > button,
    button[type="submit"] {
        background: linear-gradient(135deg, #10B981 0%, #059669 100%) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: 2px solid #047857 !important;
        font-weight: 700 !important;
        font-size: 0.9rem !important;
        padding: 0.6rem 1.4rem !important;
        border-radius: 8px !important;
        box-shadow: 0 4px 6px -1px rgba(16,185,129,0.4) !important;
        letter-spacing: 0.3px !important;
    }
    .stButton > button[kind="primary"] p,
    .stButton > button[kind="primary"] span,
    [data-testid="baseButton-primary"] p,
    [data-testid="baseButton-primary"] span,
    [data-testid="stBaseButton-primary"] p,
    [data-testid="stBaseButton-primary"] span,
    [data-testid="stFormSubmitButton"] > button p,
    [data-testid="stFormSubmitButton"] > button span,
    button[type="submit"] p,
    button[type="submit"] span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* SECONDARY - Gris claro con texto oscuro legible */
    .stButton > button[kind="secondary"],
    [data-testid="baseButton-secondary"],
    [data-testid="stBaseButton-secondary"] {
        background: #E2F0E8 !important;
        color: #064E3B !important;
        -webkit-text-fill-color: #064E3B !important;
        border: 2px solid #34D399 !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
        padding: 0.5rem 1.1rem !important;
        border-radius: 8px !important;
    }
    .stButton > button[kind="secondary"] p,
    .stButton > button[kind="secondary"] span,
    [data-testid="baseButton-secondary"] p,
    [data-testid="baseButton-secondary"] span,
    [data-testid="stBaseButton-secondary"] p,
    [data-testid="stBaseButton-secondary"] span {
        color: #064E3B !important;
        -webkit-text-fill-color: #064E3B !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
    }
    
    /* TERTIARY/Link buttons - GREEN */
    button[kind="tertiary"] {
        color: #10B981 !important;
        background: transparent !important;
        border: 2px solid #10B981 !important;
        font-weight: 600 !important;
        padding: 0.5rem 1rem !important;
        border-radius: 6px !important;
    }
    
    /* DOWNLOAD BUTTON - Verde oscuro con texto blanco */
    [data-testid="stDownloadButton"] > button {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        border: 2px solid #065F46 !important;
        font-weight: 700 !important;
        border-radius: 8px !important;
    }
    [data-testid="stDownloadButton"] > button p,
    [data-testid="stDownloadButton"] > button span {
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        font-weight: 700 !important;
    }

    /* CATCH-ALL: cualquier boton que quede sin texto visible */
    .stButton > button p,
    .stButton > button span {
        opacity: 1 !important;
        visibility: visible !important;
        font-weight: 600 !important;
        font-size: 0.875rem !important;
    }

    /* Hover states */
    .stButton > button[kind="primary"]:hover,
    [data-testid="stBaseButton-primary"]:hover {
        background: linear-gradient(135deg, #059669 0%, #047857 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 8px -1px rgba(16,185,129,0.5) !important;
    }
    .stButton > button[kind="secondary"]:hover,
    [data-testid="stBaseButton-secondary"]:hover {
        background: #c6e8d4 !important;
        border-color: #10B981 !important;
    }

    /* Focus */
    .stButton > button:focus {
        outline: 2px solid #10B981 !important;
        outline-offset: 2px !important;
    }

    /* Sidebar buttons */
    [data-testid="stSidebar"] .stButton > button {
        width: 100% !important;
        margin-bottom: 0.5rem !important;
    }

    /* =====================================================
       SCROLL CONTAINERS INTERNOS
       ===================================================== */
    .mc-scroll-block {
        max-height: 220px;
        overflow-y: auto;
        overflow-x: hidden;
        background: rgba(30,41,59,0.5);
        border: 1px solid rgba(148,163,184,0.3);
        border-radius: 8px;
        padding: 10px 14px;
        font-size: 0.88rem;
        line-height: 1.6;
        color: #cbd5e1;
        white-space: pre-wrap;
        word-break: break-word;
        scrollbar-width: thin;
        scrollbar-color: #10B981 transparent;
        -webkit-overflow-scrolling: touch;
    }
    .mc-scroll-block::-webkit-scrollbar { width: 5px; }
    .mc-scroll-block::-webkit-scrollbar-thumb { background: #10B981; border-radius: 4px; }
    
    /* Tables */
    .data-table {
        width: 100%;
        border-collapse: collapse;
        background: var(--surface);
        border-radius: var(--radius);
        overflow: hidden;
        box-shadow: var(--shadow);
    }
    
    .data-table th {
        background: #F8FAFC;
        padding: 0.75rem 1rem;
        text-align: left;
        font-size: 0.75rem;
        font-weight: 600;
        color: var(--text-secondary);
        text-transform: uppercase;
        letter-spacing: 0.05em;
        border-bottom: 1px solid var(--border);
    }
    
    .data-table td {
        padding: 1rem;
        border-bottom: 1px solid var(--border);
        color: var(--text-primary);
        font-size: 0.875rem;
    }
    
    .data-table tr:last-child td {
        border-bottom: none;
    }
    
    .data-table tr:hover {
        background: #F8FAFC;
    }
    
    /* Sidebar */
    .css-1d391kg, .css-163ttbj {
        background: var(--surface);
    }
    
    /* Alerts */
    .alert {
        padding: 1rem 1.25rem;
        border-radius: var(--radius);
        margin-bottom: 1rem;
        display: flex;
        align-items: flex-start;
        gap: 0.75rem;
    }
    
    .alert-success {
        background: #D1FAE5;
        border: 1px solid #A7F3D0;
        color: #065F46;
    }
    
    .alert-warning {
        background: #FEF3C7;
        border: 1px solid #FDE68A;
        color: #92400E;
    }
    
    .alert-danger {
        background: #FEE2E2;
        border: 1px solid #FECACA;
        color: #991B1B;
    }
    
    .alert-info {
        background: #DBEAFE;
        border: 1px solid #BFDBFE;
        color: #1E40AF;
    }
    
    /* Forms */
    .stTextInput > div > div > input {
        border-radius: var(--radius);
        border: 1px solid var(--border);
        padding: 0.625rem 0.875rem;
        font-size: 0.875rem;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    
    .stTextInput > div > div > input:focus {
        border-color: var(--primary);
        box-shadow: 0 0 0 3px rgba(37, 99, 235, 0.1);
    }
    
    /* Select boxes */
    .stSelectbox > div > div > div {
        border-radius: var(--radius);
        border: 1px solid var(--border);
    }
    
    /* Progress bar */
    .stProgress > div > div > div > div {
        background: var(--primary);
    }
    
    /* Spinner */
    .stSpinner > div {
        border-color: var(--primary) transparent transparent transparent;
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        border-bottom: 1px solid var(--border);
    }
    
    .stTabs [data-baseweb="tab"] {
        padding: 0.75rem 1.25rem;
        font-weight: 500;
        color: var(--text-secondary);
        border-bottom: 2px solid transparent;
    }
    
    .stTabs [data-baseweb="tab"][aria-selected="true"] {
        color: var(--primary);
        border-bottom-color: var(--primary);
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        font-weight: 500;
        color: var(--text-primary);
    }
    
    /* Tooltips */
    [data-testid="stTooltipIcon"] {
        color: var(--text-secondary);
    }
    
    /* Dividers */
    hr {
        border: none;
        border-top: 1px solid var(--border);
        margin: 1.5rem 0;
    }
    
    /* Avatar */
    .avatar {
        width: 40px;
        height: 40px;
        border-radius: 50%;
        background: linear-gradient(135deg, var(--primary), var(--primary-dark));
        display: flex;
        align-items: center;
        justify-content: center;
        color: white;
        font-weight: 600;
        font-size: 0.875rem;
    }
    
    /* Animations */
    @keyframes fadeIn {
        from { opacity: 0; transform: translateY(10px); }
        to { opacity: 1; transform: translateY(0); }
    }
    
    .animate-fade-in {
        animation: fadeIn 0.3s ease-out;
    }
    
    /* Loading skeleton */
    .skeleton {
        background: linear-gradient(90deg, #f0f0f0 25%, #e0e0e0 50%, #f0f0f0 75%);
        background-size: 200% 100%;
        animation: loading 1.5s infinite;
        border-radius: var(--radius);
    }
    
    @keyframes loading {
        0% { background-position: 200% 0; }
        100% { background-position: -200% 0; }
    }
    
    /* Hide default elements */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* Custom scrollbar */
    ::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    
    ::-webkit-scrollbar-track {
        background: var(--background);
    }
    
    ::-webkit-scrollbar-thumb {
        background: var(--border);
        border-radius: 4px;
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: var(--text-secondary);
    }
</style>
"""


def apply_professional_theme():
    """Aplica el tema profesional a la aplicación."""
    st.markdown(CUSTOM_CSS, unsafe_allow_html=True)


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
