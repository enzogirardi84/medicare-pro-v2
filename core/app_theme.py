"""Tema visual global de MediCare PRO.

Inyecta CSS robusto sin depender de selectores data-testid para la navegación
principal. Mantiene compatibilidad visual en PC, tablet y móvil.
"""

import streamlit as st


def aplicar_css_base() -> None:
    """CSS general: fondo oscuro, inputs, métricas y navegación por clases propias."""
    st.markdown(
        """
        <style>
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
