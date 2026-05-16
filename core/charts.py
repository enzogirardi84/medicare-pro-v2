"""Gráficos reutilizables para Medicare Pro - Altair y Plotly."""
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from core.view_helpers import bloque_estado_vacio


# Paleta semántica unificada
COLOR_PRIMARY = "#2563eb"
COLOR_SECONDARY = "#64748b"
COLOR_SUCCESS = "#10b981"
COLOR_WARNING = "#f59e0b"
COLOR_DANGER = "#ef4444"
COLOR_INFO = "#06b6d4"

COLORS_CATEGORICAL = ["#2563eb", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6", "#ec4899", "#06b6d4", "#f97316"]


def chart_barras(df, x, y, color=None, titulo_x="", titulo_y="", altura=200):
    """Gráfico de barras horizontal con Altair."""
    if df is None or df.empty:
        return None
    base = alt.Chart(df).encode(
        x=alt.X(f"{y}:Q", title=titulo_y or y),
        y=alt.Y(f"{x}:O", sort="-x", title=titulo_x or x),
        tooltip=[alt.Tooltip(f"{x}:N"), alt.Tooltip(f"{y}:Q", format=",")],
    )
    if color:
        base = base.encode(color=alt.Color(f"{color}:N", scale=alt.Scale(range=COLORS_CATEGORICAL), legend=None))
    return base.mark_bar(cornerRadiusEnd=4, height=altura).configure_axis(labelFontSize=11, titleFontSize=12).configure_view(strokeWidth=0)


def chart_linea(df, x, y, color=None, titulo_x="", titulo_y="", altura=200):
    """Gráfico de línea con Altair."""
    if df is None or df.empty:
        return None
    base = alt.Chart(df).encode(
        x=alt.X(f"{x}:T", title=titulo_x or x),
        y=alt.Y(f"{y}:Q", title=titulo_y or y),
        tooltip=[alt.Tooltip(f"{x}:T"), alt.Tooltip(f"{y}:Q", format=",")],
    )
    if color:
        base = base.encode(color=alt.Color(f"{color}:N", scale=alt.Scale(range=COLORS_CATEGORICAL)))
    return base.mark_line(point=True, strokeWidth=2, height=altura).configure_axis(labelFontSize=11, titleFontSize=12).configure_view(strokeWidth=0)


def chart_area(df, x, y, color=COLOR_PRIMARY, titulo_x="", titulo_y="", altura=200):
    """Gráfico de área con Altair."""
    if df is None or df.empty:
        return None
    return alt.Chart(df).mark_area(opacity=0.3, line={"color": color, "width": 2}, point=True).encode(
        x=alt.X(f"{x}:T", title=titulo_x or x),
        y=alt.Y(f"{y}:Q", title=titulo_y or y),
        tooltip=[alt.Tooltip(f"{x}:T"), alt.Tooltip(f"{y}:Q", format=",")],
    ).configure_axis(labelFontSize=11, titleFontSize=12).configure_view(strokeWidth=0)


def render_metric_card(valor, etiqueta, delta=None, icono=None, color=COLOR_PRIMARY):
    """Renderiza una métrica profesional con icono."""
    icon_html = f'<span style="font-size:1.3rem;margin-right:6px;">{icono}</span>' if icono else ""
    delta_html = f'<div style="font-size:0.75rem;color:{"#10b981" if delta and delta > 0 else "#ef4444" if delta and delta < 0 else "#94a3b8"};margin-top:2px;">{delta:+.1f}%</div>' if delta is not None else ""
    st.markdown(f"""
        <div style="background:rgba(30,41,59,0.7);border-radius:12px;padding:16px;border:1px solid rgba(148,163,184,0.1);border-left:4px solid {color};">
            <div style="display:flex;align-items:center;gap:8px;">
                {icon_html}
                <div style="font-size:1.6rem;font-weight:700;color:#e2e8f0;">{valor}</div>
            </div>
            <div style="font-size:0.8rem;color:#94a3b8;margin-top:4px;">{etiqueta}</div>
            {delta_html}
        </div>
    """, unsafe_allow_html=True)


def render_chart_card(titulo, chart, height=300):
    """Renderiza un chart dentro de una card."""
    if chart is None:
        return
    with st.container():
        st.markdown(f'<div style="font-size:0.9rem;font-weight:600;color:#e2e8f0;margin-bottom:4px;">{titulo}</div>', unsafe_allow_html=True)
        st.altair_chart(chart, use_container_width=True)


def render_kpi_row(metrics, cols=4):
    """Renderiza fila de KPIs. metrics = [(valor, etiqueta, delta, icono, color), ...]"""
    for i in range(0, len(metrics), cols):
        with st.columns(cols) as row:
            for j, (valor, etiqueta, delta, icono, color) in enumerate(metrics[i:i+cols]):
                with row[j]:
                    render_metric_card(valor, etiqueta, delta, icono, color)


def placeholder_chart(altura=200):
    """Placeholder visual para datos no disponibles."""
    return f'<div style="height:{altura}px;background:rgba(30,41,59,0.3);border-radius:12px;border:1px dashed rgba(148,163,184,0.15);display:flex;align-items:center;justify-content:center;color:#64748b;font-size:0.85rem;">Sin datos suficientes</div>'


# ─── Plotly charts (interactivos) ─────────────────────────────

def _try_plotly():
    """Importa plotly express si está disponible."""
    try:
        import plotly.express as _px
        return _px
    except ImportError:
        return None


def plotly_chart_barras(df, x, y, color=None, titulo="", altura=400):
    """Gráfico de barras interactivo con Plotly."""
    px = _try_plotly()
    if px is None or df is None or df.empty:
        return None
    fig = px.bar(df, x=x, y=y, color=color, title=titulo,
                 template="plotly_dark", height=altura)
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10),
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#e2e8f0"))
    fig.update_xaxes(gridcolor="rgba(148,163,184,0.15)")
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.15)")
    return fig


def plotly_chart_linea(df, x, y, color=None, titulo="", altura=400):
    """Gráfico de líneas interactivo con Plotly."""
    px = _try_plotly()
    if px is None or df is None or df.empty:
        return None
    fig = px.line(df, x=x, y=y, color=color, title=titulo,
                  template="plotly_dark", height=altura,
                  markers=True)
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10),
                      paper_bgcolor="rgba(0,0,0,0)",
                      plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#e2e8f0"))
    fig.update_xaxes(gridcolor="rgba(148,163,184,0.15)")
    fig.update_yaxes(gridcolor="rgba(148,163,184,0.15)")
    return fig


def plotly_chart_donut(df, names, values, titulo="", altura=400):
    """Gráfico de donut interactivo con Plotly."""
    px = _try_plotly()
    if px is None or df is None or df.empty:
        return None
    fig = px.pie(df, names=names, values=values, title=titulo,
                 hole=0.4, template="plotly_dark", height=altura)
    fig.update_layout(margin=dict(l=10, r=10, t=40, b=10),
                      paper_bgcolor="rgba(0,0,0,0)",
                      font=dict(color="#e2e8f0"),
                      showlegend=True,
                      legend=dict(font=dict(color="#e2e8f0")))
    fig.update_traces(textposition="inside", textinfo="percent+label",
                      marker=dict(line=dict(color="#0f172a", width=1)))
    return fig


def render_plotly_chart(fig, use_container_width=True):
    """Renderiza un gráfico Plotly en Streamlit con manejo de error."""
    if fig is None:
        st.caption("Plotly no está instalado. `pip install plotly` para gráficos interactivos.")
        return
    try:
        st.plotly_chart(fig, use_container_width=use_container_width)
    except Exception:
        st.caption("Error al renderizar gráfico Plotly.")
