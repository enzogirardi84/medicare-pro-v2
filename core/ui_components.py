"""
Helper functions para usar los componentes UI médicos en Streamlit.
Facilita la aplicación de clases CSS mc-* sin escribir HTML manualmente.
"""
from typing import List, Optional, Dict, Any
import html

import streamlit as st


def tooltip(text: str, tooltip_text: str, position: str = "top") -> str:
    """
    Generar HTML para tooltip médico.
    
    Args:
        text: Texto visible
        tooltip_text: Texto del tooltip
        position: "top" o "right"
    
    Returns:
        HTML string
    """
    position_class = f"mc-tooltip-{position}" if position != "top" else ""
    return f'''
    <span class="mc-tooltip {position_class}">
        {html.escape(text)}
        <span class="mc-tooltip-text">{html.escape(tooltip_text)}</span>
    </span>
    '''


def render_tooltip(text: str, tooltip_text: str, position: str = "top"):
    """Renderizar tooltip directamente en Streamlit."""
    st.markdown(tooltip(text, tooltip_text, position), unsafe_allow_html=True)


def badge(label: str, variant: str = "info") -> str:
    """
    Generar badge clínico.
    
    Variantes: critical, warning, success, info, neutral, alergia, urgencia
    """
    valid_variants = ["critical", "warning", "success", "info", "neutral", "alergia", "urgencia"]
    variant = variant if variant in valid_variants else "info"
    
    return f'<span class="mc-badge mc-badge-{variant}">{html.escape(label)}</span>'


def render_badge(label: str, variant: str = "info"):
    """Renderizar badge directamente."""
    st.markdown(badge(label, variant), unsafe_allow_html=True)


def status_dot(status: str = "active") -> str:
    """
    Generar indicador de estado (dot).
    Estados: active, warning, critical
    """
    return f'<span class="mc-status-dot {status}"></span>'


def render_status_dot(status: str = "active"):
    """Renderizar status dot."""
    st.markdown(status_dot(status), unsafe_allow_html=True)


def medical_card(
    title: str,
    content: str,
    is_critical: bool = False,
    animation: str = "fade-up",
    stagger: Optional[int] = None
) -> str:
    """
    Generar card médica con animación.
    
    Args:
        title: Título de la card
        content: Contenido HTML o texto
        is_critical: Si es crítica (barra roja)
        animation: fade-up, fade-left, scale, slide-right
        stagger: Delay para animación secuencial (1-5)
    """
    critical_class = "critica" if is_critical else ""
    animation_class = f"mc-animate-{animation.replace('-', '')}"
    stagger_class = f"mc-stagger-{stagger}" if stagger else ""
    
    return f'''
    <div class="mc-medical-card {critical_class} {animation_class} {stagger_class}">
        <div class="mc-medical-card-header">
            <div class="mc-medical-card-title">{html.escape(title)}</div>
        </div>
        <div class="mc-medical-card-content">{content}</div>
    </div>
    '''


def render_medical_card(
    title: str,
    content: str,
    is_critical: bool = False,
    animation: str = "fade-up",
    stagger: Optional[int] = None
):
    """Renderizar card médica directamente."""
    st.markdown(
        medical_card(title, content, is_critical, animation, stagger),
        unsafe_allow_html=True
    )


def timeline_item(
    date: str,
    title: str,
    content: str,
    status: str = "normal",  # normal, critico, mejora
) -> str:
    """
    Generar item de timeline clínico.
    
    Args:
        date: Fecha/hora del evento
        title: Título del evento
        content: Descripción
        status: normal, critico, mejora
    """
    status_class = status if status in ["critico", "mejora"] else ""
    
    return f'''
    <div class="mc-timeline-item {status_class}">
        <div class="mc-timeline-header">
            <span class="mc-timeline-date">{html.escape(date)}</span>
            <h4 class="mc-timeline-title">{html.escape(title)}</h4>
        </div>
        <div class="mc-timeline-content">{html.escape(content)}</div>
    </div>
    '''


def timeline(items: List[Dict[str, str]]) -> str:
    """
    Generar timeline completo desde lista de items.
    
    Args:
        items: Lista de dicts con keys: date, title, content, status
    """
    items_html = "\n".join([
        timeline_item(
            item.get("date", ""),
            item.get("title", ""),
            item.get("content", ""),
            item.get("status", "normal")
        )
        for item in items
    ])
    
    return f'<div class="mc-timeline">{items_html}</div>'


def render_timeline(items: List[Dict[str, str]]):
    """Renderizar timeline directamente."""
    st.markdown(timeline(items), unsafe_allow_html=True)


def text_gradient(text: str) -> str:
    """Texto con gradiente azul-verde."""
    return f'<span class="mc-text-gradient">{html.escape(text)}</span>'


def render_text_gradient(text: str):
    """Renderizar texto con gradiente."""
    st.markdown(text_gradient(text), unsafe_allow_html=True)


def glass_container(content: str, border: bool = False) -> str:
    """
    Contenedor con efecto glassmorphism.
    
    Args:
        content: HTML content
        border: Si tiene borde gradiente
    """
    if border:
        return f'<div class="mc-border-gradient">{content}</div>'
    return f'<div class="mc-glass" style="padding:1rem;border-radius:12px;">{content}</div>'


def render_glass_container(content: str, border: bool = False):
    """Renderizar contenedor glass."""
    st.markdown(glass_container(content, border), unsafe_allow_html=True)


# ============================================================
# COMPONENTES COMPUESTOS ESPECÍFICOS
# ============================================================

def patient_header_card(
    nombre: str,
    dni: str,
    edad: Optional[int] = None,
    obra_social: Optional[str] = None,
    estado: str = "Activo",
    alertas: Optional[List[str]] = None
) -> str:
    """
    Card de encabezado de paciente con badges.
    """
    estado_badge = badge(estado, "success" if estado == "Activo" else "warning")
    
    alertas_html = ""
    if alertas:
        alertas_badges = " ".join([badge(a, "alergia") for a in alertas])
        alertas_html = f'<div style="margin-top:0.5rem;">{alertas_badges}</div>'
    
    info_extra = []
    if edad:
        info_extra.append(f"{edad} años")
    if obra_social:
        info_extra.append(html.escape(obra_social))
    
    info_line = " | ".join(info_extra) if info_extra else ""
    
    content = f'''
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <div>
            <h3 style="margin:0;font-size:1.25rem;">{html.escape(nombre)}</h3>
            <p style="margin:0.25rem 0;color:#94a3b8;font-size:0.9rem;">
                DNI: {html.escape(dni)} {f"• {info_line}" if info_line else ""}
            </p>
        </div>
        <div>{estado_badge}</div>
    </div>
    {alertas_html}
    '''
    
    return medical_card("", content, is_critical=bool(alertas))


def render_patient_header_card(
    nombre: str,
    dni: str,
    edad: Optional[int] = None,
    obra_social: Optional[str] = None,
    estado: str = "Activo",
    alertas: Optional[List[str]] = None
):
    """Renderizar header de paciente."""
    st.markdown(
        patient_header_card(nombre, dni, edad, obra_social, estado, alertas),
        unsafe_allow_html=True
    )


def vital_sign_badge(tipo: str, valor: str, unidad: str, es_normal: bool = True) -> str:
    """
    Badge para signo vital con indicador de estado.
    """
    status = "success" if es_normal else "critical"
    icono = {"presion": "cardiology", "frecuencia": "monitor_heart", "temperatura": "thermometer", "saturacion": "air"}.get(tipo, "monitoring")
    
    return f'''
    <div style="display:inline-flex;align-items:center;gap:0.5rem;padding:0.5rem 1rem;
                background:rgba(30,41,59,0.6);border-radius:8px;margin:0.25rem;">
        <span style="font-family:'Material Symbols Rounded',sans-serif;font-size:1.15rem;opacity:0.9;">{icono}</span>
        <span style="font-weight:600;">{html.escape(valor)} {html.escape(unidad)}</span>
        {status_dot(status)}
    </div>
    '''


def render_vital_sign_badge(tipo: str, valor: str, unidad: str, es_normal: bool = True):
    """Renderizar badge de signo vital."""
    st.markdown(vital_sign_badge(tipo, valor, unidad, es_normal), unsafe_allow_html=True)


# ============================================================
# ANIMACIÓN DE CARGA
# ============================================================

def loading_pulse(text: str = "Cargando...") -> str:
    """Indicador de carga animado."""
    return f'''
    <div style="display:flex;align-items:center;gap:0.75rem;padding:1rem;">
        <span class="mc-status-dot active" style="width:12px;height:12px;"></span>
        <span style="color:#94a3b8;">{html.escape(text)}</span>
    </div>
    '''


def render_loading_pulse(text: str = "Cargando..."):
    """Renderizar loading."""
    st.markdown(loading_pulse(text), unsafe_allow_html=True)


# ============================================================
# BOTONES ESTILIZADOS
# ============================================================

def styled_button(
    label: str,
    icon: str = "",
    variant: str = "primary"  # primary, secondary, danger
) -> str:
    """
    Botón estilizado con icono.
    Nota: Para usar con st.button(), envolver el output en markdown.
    """
    icons = {
        "primary": "play_arrow",
        "secondary": "settings",
        "danger": "warning",
        "save": "save",
        "download": "download",
        "view": "visibility",
    }
    
    icon_str = icon or icons.get(variant, "")
    
    colors = {
        "primary": "#3b82f6",
        "secondary": "#64748b",
        "danger": "#ef4444",
    }
    
    color = colors.get(variant, "#3b82f6")
    
    return f'''
    <button class="mc-btn-hover" style="
        background:{color};
        color:white;
        border:none;
        padding:0.75rem 1.5rem;
        border-radius:8px;
        font-weight:600;
        cursor:pointer;
        display:inline-flex;
        align-items:center;
        gap:0.5rem;
    ">
        {icon_str} {html.escape(label)}
    </button>
    '''


# ============================================================
# USO EN STREAMLIT
# ============================================================

def demo_all_components():
    """Demo de todos los componentes disponibles."""
    st.markdown("## 🎨 Demo de Componentes UI Médicos")
    
    # Badges
    st.markdown("### Badges Clínicos")
    cols = st.columns(4)
    with cols[0]:
        render_badge("CRÍTICO", "critical")
    with cols[1]:
        render_badge("ADVERTENCIA", "warning")
    with cols[2]:
        render_badge("ESTABLE", "success")
    with cols[3]:
        render_badge("ALERGIA", "alergia")
    
    # Status dots
    st.markdown("### Indicadores de Estado")
    cols = st.columns(3)
    with cols[0]:
        st.markdown("Activo:")
        render_status_dot("active")
    with cols[1]:
        st.markdown("Advertencia:")
        render_status_dot("warning")
    with cols[2]:
        st.markdown("Crítico:")
        render_status_dot("critical")
    
    # Timeline
    st.markdown("### Timeline Clínico")
    timeline_items = [
        {
            "date": "24/04/2026 14:30",
            "title": "Ingreso a UTI",
            "content": "Paciente ingresa por dificultad respiratoria severa",
            "status": "critico"
        },
        {
            "date": "24/04/2026 18:00",
            "title": "Inicio de antibióticos",
            "content": "Se inicia tratamiento con Ceftriaxona 2g IV",
            "status": "normal"
        },
        {
            "date": "25/04/2026 08:00",
            "title": "Mejoría clínica",
            "content": "SATO2 al 96% sin oxígeno suplementario",
            "status": "mejora"
        }
    ]
    render_timeline(timeline_items)
    
    # Cards
    st.markdown("### Cards Médicas")
    render_medical_card(
        "🫁 Auscultación",
        "Murmullo vesicular conservado bilateralmente. No se detectan estertores ni sibilancias.",
        animation="fade-up",
        stagger=1
    )
    
    render_medical_card(
        "⚠️ Alerta de Laboratorio",
        "Creatinina: 2.8 mg/dL (elevada). Considerar ajuste de dosis de antibióticos.",
        is_critical=True,
        animation="fade-up",
        stagger=2
    )
    
    # Patient header
    st.markdown("### Header de Paciente")
    render_patient_header_card(
        nombre="María González",
        dni="28.456.123",
        edad=67,
        obra_social="OSDE",
        estado="Internado",
        alertas=["Penicilina", "Yodo"]
    )
