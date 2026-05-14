"""Tema visual de MediCare PRO. Version minimal."""
import streamlit as st


def aplicar_css_base() -> None:
    """CSS minimo para evitar problemas de renderizado."""
    st.markdown(
        """
        <style>
            /* =========================================================
               0. OPTIMIZACIONES DE RENDIMIENTO
               ========================================================= */
            /* Evitar reflows */
            .stApp, [data-testid="stAppViewContainer"] {
                contain: layout style !important;
            }
            /* Aceleracion hardware en animaciones */
            .stButton > button, div[data-testid="stMetric"] {
                transform: translateZ(0) !important;
                will-change: transform, opacity !important;
            }
            
            /* Fondo oscuro */
            .stApp {
                background-color: #0f172a !important;
            }
            .stApp > header {
                background-color: transparent !important;
            }
            /* Botones */
            div[data-testid="stButton"] > button {
                border-radius: 14px !important;
                transition: all 0.2s ease !important;
            }
            div[data-testid="stButton"] > button[kind="primary"] {
                background: linear-gradient(135deg, #0ea5e9, #2563eb) !important;
                border: none !important;
            }
            /* Inputs */
            div[data-testid="stTextInput"] input {
                border-radius: 12px !important;
            }
            /* Tarjetas metricas */
            div[data-testid="stMetric"] {
                background: rgba(255,255,255,0.03) !important;
                border-radius: 12px !important;
                padding: 10px !important;
                border: 1px solid rgba(255,255,255,0.06) !important;
            }
            [data-testid="stMetricValue"] {
                color: #0ea5e9 !important;
                font-size: 1.3rem !important;
            }
            /* Sidebar */
            [data-testid="stSidebar"] {
                background: rgba(15, 12, 41, 0.95) !important;
            }
            /* Tablas */
            .stDataFrame {
                border-radius: 10px !important;
                overflow: auto !important;
            }
            /* Animacion fade-in */
            .stApp {
                animation: fadeIn 0.3s ease-in;
            }
            @keyframes fadeIn {
                from { opacity: 0.8; }
                to { opacity: 1; }
            }

            /* =========================================================
               18. OPTIMIZACION MOVIL Y TABLET
               ========================================================= */
            @media (max-width: 768px) {
                .stButton > button { min-height: 44px !important; font-size: 0.85rem !important; }
                [data-testid="stMetric"] { min-height: 64px !important; }
                [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
                .block-container { padding: 0.5rem 0.6rem !important; }
                div[data-testid="column"] { min-width: 100% !important; padding: 0 !important; }
                [data-testid="stHorizontalBlock"] { gap: 0.4rem !important; }
                h1 { font-size: 1.3rem !important; }
                h2 { font-size: 1.1rem !important; }
                h3 { font-size: 1rem !important; }
                .stDataFrame { max-height: 50vh !important; }
            }
            @media (min-width: 769px) and (max-width: 1024px) {
                div[data-testid="column"] { min-width: 48% !important; }
                .block-container { padding: 0.8rem 1rem !important; }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
