"""Tema visual global de MediCare PRO.

Inyecta CSS robusto sin depender de selectores data-testid para la navegación
principal. Mantiene compatibilidad visual en PC, tablet y móvil.
"""

import streamlit as st


def aplicar_css_base() -> None:
    """CSS general: fondo oscuro, inputs, métricas, navegación y loader premium."""
    st.markdown(
        """
        <style>
            /* =========================================================
               FONDO RAÍZ Y HEADER
               ========================================================= */
            .stApp {
                background-color: #0f172a !important;
            }
            .stApp > header {
                background-color: transparent !important;
                z-index: 999998 !important;
            }

            /* =========================================================
               MEJORA PREMIUM DEL LOADER (STATUS WIDGET Y SPINNER)
               ========================================================= */
            /* 1. La píldora superior derecha de "Running..." */
            div[data-testid="stStatusWidget"] {
                z-index: 999999 !important;
                visibility: visible !important;
                overflow: visible !important;
                background: rgba(15, 23, 42, 0.75) !important;
                backdrop-filter: blur(12px) !important;
                -webkit-backdrop-filter: blur(12px) !important;
                border: 1px solid rgba(14, 165, 233, 0.3) !important;
                border-radius: 50px !important;
                padding: 4px 16px !important;
                box-shadow: 0 4px 20px rgba(14, 165, 233, 0.15) !important;
                top: 15px !important;
                right: 15px !important;
                transition: all 0.3s ease !important;
            }

            /* 2. Forzar que el texto del loader sea blanco y elegante */
            div[data-testid="stStatusWidget"] label,
            div[data-testid="stStatusWidget"] div {
                color: #ffffff !important;
                font-weight: 500 !important;
                font-size: 0.9rem !important;
            }

            /* 3. Colorear la rueda circular de carga (Spinner) */
            .stSpinner > div > div {
                border-color: rgba(14, 165, 233, 0.2) !important;
                border-top-color: #0ea5e9 !important;
            }

            div[data-testid="stToastContainer"] {
                z-index: 999999 !important;
            }

            /* =============================
               BASE VISUAL GENERAL
               ============================= */
            html, body, [data-testid="stAppViewContainer"] {
                background: #0f172a;
            }

            /* Inputs y selectores */
            div[data-testid="stTextInput"] input,
            div[data-baseweb="select"] > div {
                border-radius: 14px !important;
                border: 1px solid rgba(255, 255, 255, 0.10) !important;
                background-color: rgba(255, 255, 255, 0.035) !important;
                color: #ffffff !important;
            }

            /* Métricas sidebar */
            div[data-testid="stMetric"] {
                background-color: rgba(255, 255, 255, 0.025) !important;
                border-radius: 16px !important;
                padding: 10px !important;
                border: 1px solid rgba(255, 255, 255, 0.055) !important;
            }
            [data-testid="stSidebar"] [data-testid="stMetricValue"] {
                font-size: 1.2rem !important;
            }
            [data-testid="stSidebar"] [data-testid="stMetricLabel"] {
                font-size: 0.8rem !important;
            }
            [data-testid="stSidebar"] div[data-testid="column"] {
                padding: 0 !important;
            }

            /* Botones genéricos (no navegación) */
            div[data-testid="stButton"] > button {
                border-radius: 18px !important;
                border: 1px solid rgba(14, 165, 233, 0.28) !important;
                background: rgba(15, 23, 42, 0.55) !important;
                box-shadow: 0 4px 8px rgba(0, 0, 0, 0.14) !important;
                transition: all 0.18s ease !important;
                padding: 0.5rem 1rem !important;
                color: #ffffff !important;
            }
            div[data-testid="stButton"] > button:hover {
                transform: translateY(-1px) !important;
                border-color: #0ea5e9 !important;
                box-shadow: 0 6px 15px rgba(14, 165, 233, 0.20) !important;
                color: white !important;
            }
            div[data-testid="stButton"] > button p,
            div[data-testid="stButton"] > button div,
            div[data-testid="stButton"] > button span {
                color: #ffffff !important;
                font-weight: 600 !important;
            }

            /* Contenedores con borde */
            div[data-testid="stVerticalBlockBorderWrapper"] {
                border-radius: 22px !important;
                border: 1px solid rgba(255, 255, 255, 0.06) !important;
                box-shadow: 0 10px 28px rgba(0, 0, 0, 0.18) !important;
                background-color: rgba(17, 24, 39, 0.90) !important;
                overflow: hidden !important;
            }

        </style>
        """,
        unsafe_allow_html=True,
    )
