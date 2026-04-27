"""Tema visual global de MediCare PRO.

Inyecta CSS robusto sin depender de selectores data-testid para la navegación
principal. Mantiene compatibilidad visual en PC, tablet y móvil.
"""

import streamlit as st


def aplicar_css_base() -> None:
    """CSS general: fondo oscuro, loader premium, login y navegación."""
    st.markdown(
        """
        <style>
            /* =========================================================
               1. FONDO RAÍZ Y HEADER
               ========================================================= */
            .stApp {
                background-color: #0f172a !important;
            }
            .stApp > header {
                background-color: transparent !important;
                z-index: 999998 !important;
            }

            /* =========================================================
               2. LOADER PREMIUM (STATUS WIDGET Y SPINNER)
               ========================================================= */
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
            }
            div[data-testid="stStatusWidget"] label,
            div[data-testid="stStatusWidget"] div {
                color: #ffffff !important;
                font-weight: 500 !important;
            }
            .stSpinner > div > div {
                border-color: rgba(14, 165, 233, 0.2) !important;
                border-top-color: #0ea5e9 !important;
            }
            div[data-testid="stToastContainer"] {
                z-index: 999999 !important;
            }

            /* =========================================================
               3. DISEÑO PREMIUM DE LOGIN (Puerta de Ingreso)
               ========================================================= */
            /* Tarjeta del Formulario */
            div[data-testid="stForm"] {
                background: linear-gradient(145deg, #111827, #1f2937) !important;
                border: 1px solid rgba(255, 255, 255, 0.08) !important;
                border-radius: 24px !important;
                padding: 30px 20px !important;
                box-shadow: 0 20px 40px rgba(0, 0, 0, 0.5) !important;
            }
            /* Botón de Submit (Ingresar) */
            div[data-testid="stForm"] div[data-testid="stButton"] > button {
                background: linear-gradient(135deg, #0ea5e9, #2563eb) !important;
                border: none !important;
                border-radius: 50px !important;
                height: 50px !important;
                font-weight: 700 !important;
                letter-spacing: 0.5px !important;
                box-shadow: 0 4px 15px rgba(14, 165, 233, 0.3) !important;
            }
            div[data-testid="stForm"] div[data-testid="stButton"] > button:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 8px 25px rgba(14, 165, 233, 0.5) !important;
                filter: brightness(1.1);
            }

            /* =========================================================
               4. BASE VISUAL GENERAL (Inputs, Métricas, Botones)
               ========================================================= */
            html, body, [data-testid="stAppViewContainer"] {
                background: #0f172a;
            }

            /* Inputs y selectores generales */
            div[data-testid="stTextInput"] input,
            div[data-baseweb="select"] > div {
                border-radius: 14px !important;
                border: 1px solid rgba(255, 255, 255, 0.10) !important;
                background-color: rgba(0, 0, 0, 0.2) !important;
                color: #ffffff !important;
                transition: all 0.3s ease !important;
            }
            div[data-testid="stTextInput"] input:focus {
                border-color: #0ea5e9 !important;
                box-shadow: 0 0 0 3px rgba(14, 165, 233, 0.2) !important;
                background-color: rgba(0, 0, 0, 0.4) !important;
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

            /* Botones genéricos secundarios */
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
            }
            div[data-testid="stButton"] > button p,
            div[data-testid="stButton"] > button div {
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
