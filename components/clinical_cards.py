"""Componentes visuales reutilizables para el Asistente Clínico 360°.

Diseño minimalista, estilo médico moderno, con badges, alertas y timeline.
"""

import streamlit as st


def inyectar_css():
    st.markdown(
        """
    <style>
        .main-title { font-size: 28px; font-weight: 800; color: #0F172A; margin-bottom: 4px; }
        .subtitle { font-size: 15px; color: #64748B; margin-bottom: 24px; }

        .clinical-card { background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 16px; margin-bottom: 16px; box-shadow: 0 2px 4px rgba(15,23,42,0.03); }
        .card-title { font-size: 16px; font-weight: 700; color: #1E293B; margin-bottom: 8px; border-bottom: 1px solid #F1F5F9; padding-bottom: 5px;}
        .card-text { font-size: 14px; color: #334155; line-height: 1.5; }

        .badge-ok { background: #DCFCE7; color: #166534; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; }
        .badge-warning { background: #FEF3C7; color: #92400E; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; }
        .badge-danger { background: #FEE2E2; color: #991B1B; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; }
        .badge-info { background: #E0F2FE; color: #075985; padding: 4px 8px; border-radius: 6px; font-size: 12px; font-weight: 600; }

        .alert-box { padding: 12px 16px; border-radius: 8px; font-size: 14px; margin-bottom: 12px; border-left: 4px solid; }
        .alert-info { background: #EFF6FF; border-color: #3B82F6; color: #1E3A8A; }
        .alert-warning { background: #FFF7ED; border-color: #F97316; color: #9A3412; }
        .alert-danger { background: #FEF2F2; border-color: #EF4444; color: #991B1B; }
        .alert-ok { background: #F0FDF4; border-color: #22C55E; color: #166534; }

        .timeline-item { border-left: 2px solid #CBD5E1; padding-left: 15px; margin-bottom: 15px; position: relative; }
        .timeline-dot { position: absolute; left: -6px; top: 0; width: 10px; height: 10px; border-radius: 50%; background: #3B82F6; }
        .timeline-date { font-size: 12px; color: #64748B; font-weight: 600; }
        .timeline-content { font-size: 14px; color: #334155; margin-top: 4px;}
    </style>
    """,
        unsafe_allow_html=True,
    )


def card_clinica(titulo, contenido, badge_text=None, badge_type="ok"):
    badge_html = f'<span class="badge-{badge_type}">{badge_text}</span>' if badge_text else ""
    st.markdown(
        f"""
    <div class="clinical-card">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
            <div class="card-title" style="margin: 0;">{titulo}</div>
            {badge_html}
        </div>
        <div class="card-text">{contenido}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def alerta_caja(titulo, detalle, nivel="info"):
    clase = f"alert-{nivel}"
    st.markdown(
        f"""
    <div class="alert-box {clase}">
        <strong>{titulo}</strong><br>{detalle}
    </div>
    """,
        unsafe_allow_html=True,
    )


def timeline_event(fecha, titulo, detalle, color_dot="#3B82F6"):
    st.markdown(
        f"""
    <div class="timeline-item">
        <div class="timeline-dot" style="background: {color_dot};"></div>
        <div class="timeline-date">{fecha} - <b>{titulo}</b></div>
        <div class="timeline-content">{detalle}</div>
    </div>
    """,
        unsafe_allow_html=True,
    )


def metrica_clinica(label, valor, delta=None, tendencia=None):
    """Muestra una métrica con indicador de tendencia opcional."""
    delta_color = "normal"
    if tendencia == "up":
        delta_color = "inverse"
    elif tendencia == "down":
        delta_color = "normal"
    st.metric(label=label, value=valor, delta=delta, delta_color=delta_color)
