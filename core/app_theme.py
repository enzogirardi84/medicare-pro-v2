"""Tema profesional premium MediCare PRO - Alto rendimiento."""
import streamlit as st


def aplicar_css_base() -> None:
    st.markdown("""
        <style>
            /* =========================================================
               OPTIMIZACIONES DE RENDIMIENTO
               ========================================================= */
            .stApp, [data-testid="stAppViewContainer"] {
                contain: layout style !important;
            }
            .stButton > button, [data-testid="stMetric"] {
                transform: translateZ(0) !important;
                will-change: transform, opacity !important;
            }

            /* =========================================================
               FONDO PROFESIONAL - gradiente sutil
               ========================================================= */
            .stApp {
                background: linear-gradient(145deg, #0c1929 0%, #112240 40%, #0a1628 100%) !important;
            }
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, rgba(12,25,41,0.98) 0%, rgba(17,34,64,0.95) 100%) !important;
                border-right: 1px solid rgba(100,180,255,0.06) !important;
            }

            /* =========================================================
               TARJETAS - glassmorphism premium
               ========================================================= */
            div[data-testid="stForm"],
            div[data-testid="stMetric"],
            div[data-testid="stDataFrame"],
            div[data-testid="stTable"],
            .stAlert, .streamlit-expanderHeader {
                background: rgba(255,255,255,0.02) !important;
                backdrop-filter: blur(8px) !important;
                -webkit-backdrop-filter: blur(8px) !important;
                border: 1px solid rgba(100,180,255,0.06) !important;
                border-radius: 14px !important;
                box-shadow: 0 4px 24px rgba(0,0,0,0.15), inset 0 1px 0 rgba(255,255,255,0.03) !important;
                transition: all 0.2s ease !important;
            }
            div[data-testid="stMetric"]:hover {
                border-color: rgba(14,165,233,0.15) !important;
                box-shadow: 0 8px 32px rgba(14,165,233,0.06) !important;
                transform: translateY(-1px) !important;
            }

            /* =========================================================
               BOTONES - modernos con glow sutil
               ========================================================= */
            div[data-testid="stButton"] > button {
                border-radius: 12px !important;
                font-weight: 500 !important;
                letter-spacing: 0.2px !important;
                transition: all 0.2s cubic-bezier(0.4,0,0.2,1) !important;
                border: 1px solid rgba(100,180,255,0.08) !important;
                background: rgba(255,255,255,0.03) !important;
                min-height: 40px !important;
            }
            div[data-testid="stButton"] > button:hover {
                transform: translateY(-2px) !important;
                border-color: rgba(14,165,233,0.2) !important;
                box-shadow: 0 6px 20px rgba(14,165,233,0.1) !important;
            }
            div[data-testid="stButton"] > button[kind="primary"] {
                background: linear-gradient(135deg, #2563eb, #0ea5e9) !important;
                border: none !important;
                box-shadow: 0 4px 16px rgba(14,165,233,0.15) !important;
            }
            div[data-testid="stButton"] > button[kind="primary"]:hover {
                box-shadow: 0 8px 28px rgba(14,165,233,0.25) !important;
                transform: translateY(-2px) !important;
            }
            div[data-testid="stButton"] > button[kind="secondary"] {
                background: rgba(30,41,59,0.6) !important;
                border: 1px solid rgba(100,180,255,0.1) !important;
            }

            /* =========================================================
               INPUTS Y SELECTORES
               ========================================================= */
            input, select, textarea, div[data-baseweb="select"] > div {
                border-radius: 10px !important;
                border: 1px solid rgba(100,180,255,0.1) !important;
                background: rgba(0,0,0,0.15) !important;
                color: #e2e8f0 !important;
                transition: all 0.2s ease !important;
            }
            input:focus, select:focus, textarea:focus {
                border-color: #0ea5e9 !important;
                box-shadow: 0 0 0 2px rgba(14,165,233,0.1) !important;
            }

            /* =========================================================
               METRICAS - valores destacados
               ========================================================= */
            [data-testid="stMetricValue"] {
                background: linear-gradient(135deg, #38bdf8, #818cf8) !important;
                -webkit-background-clip: text !important;
                -webkit-text-fill-color: transparent !important;
                font-weight: 700 !important;
                font-size: clamp(1.2rem, 2vw, 1.8rem) !important;
            }
            [data-testid="stMetricLabel"] {
                color: #94a3b8 !important;
                font-size: 0.8rem !important;
            }

            /* =========================================================
               TABS - navegacion elegante
               ========================================================= */
            [data-testid="stTabs"] [role="tab"] {
                border-radius: 8px 8px 0 0 !important;
                padding: 6px 18px !important;
                transition: all 0.2s ease !important;
                color: #94a3b8 !important;
            }
            [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
                background: rgba(14,165,233,0.08) !important;
                color: #38bdf8 !important;
                border-bottom: 2px solid #0ea5e9 !important;
            }
            [data-testid="stTabs"] [role="tab"]:hover {
                color: #e2e8f0 !important;
                background: rgba(255,255,255,0.03) !important;
            }

            /* =========================================================
               HEADERS - con gradiente sutil
               ========================================================= */
            h1, h2, h3, h4 {
                background: linear-gradient(135deg, #f1f5f9 0%, #94a3b8 100%) !important;
                -webkit-background-clip: text !important;
                -webkit-text-fill-color: transparent !important;
                font-weight: 600 !important;
            }

            /* =========================================================
               EXPANDERS Y DIVISORES
               ========================================================= */
            .streamlit-expanderHeader {
                border-radius: 10px !important;
                padding: 8px 12px !important;
            }
            hr {
                border-color: rgba(100,180,255,0.06) !important;
            }

            /* =========================================================
               SCROLLBAR PERSONALIZADO
               ========================================================= */
            ::-webkit-scrollbar { width: 5px !important; height: 5px !important; }
            ::-webkit-scrollbar-track { background: transparent !important; }
            ::-webkit-scrollbar-thumb {
                background: rgba(14,165,233,0.15) !important;
                border-radius: 10px !important;
            }
            ::-webkit-scrollbar-thumb:hover { background: rgba(14,165,233,0.3) !important; }

            /* =========================================================
               DATAFRAMES Y TABLAS
               ========================================================= */
            .stDataFrame {
                border-radius: 10px !important;
                overflow: hidden !important;
            }
            div[data-testid="stDataFrame"] table {
                font-size: 0.85rem !important;
            }

            /* =========================================================
               ANIMACION FADE-IN
               ========================================================= */
            .stApp {
                animation: mcFadeIn 0.2s ease-out;
            }
            @keyframes mcFadeIn {
                from { opacity: 0.9; }
                to { opacity: 1; }
            }

            /* =========================================================
               SPINNER PREMIUM
               ========================================================= */
            .stSpinner > div > div {
                border-width: 2px !important;
                border-color: rgba(14,165,233,0.08) !important;
                border-top-color: #0ea5e9 !important;
            }

            /* =========================================================
               RESPONSIVE MOVIL Y TABLET
               ========================================================= */
            @media (max-width: 768px) {
                .stButton > button { min-height: 44px !important; font-size: 0.85rem !important; }
                [data-testid="stMetric"] { min-height: 60px !important; }
                [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
                .block-container { padding: 0.4rem 0.6rem !important; }
                [data-testid="stHorizontalBlock"] { gap: 0.3rem !important; }
                h1 { font-size: 1.2rem !important; }
                h2 { font-size: 1.1rem !important; }
                h3 { font-size: 0.95rem !important; }
            }
            @media (min-width: 769px) and (max-width: 1024px) {
                .block-container { padding: 0.7rem 1rem !important; }
            }
        </style>
    """, unsafe_allow_html=True)
