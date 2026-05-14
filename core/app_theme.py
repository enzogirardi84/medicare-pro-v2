"""Tema visual de MediCare PRO. Version minimal."""
import streamlit as st


def aplicar_css_base() -> None:
    """CSS minimo para evitar problemas de renderizado."""
    st.markdown(
        """
        <style>
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
        </style>
        """,
        unsafe_allow_html=True,
    )
