"""Sistema centralizado de inyeccion de CSS corporativo para MediCare PRO.
Usa exclusivamente selectores de atributos nativos [data-testid] para
evitar conflictos con Emotion CSS de Streamlit. Optimizado para GPU movil.
"""
from __future__ import annotations

import streamlit as st

CSS_INYECTADO_KEY = "_ui_css_inyectado"


def inyectar_interfaz_corporativa() -> None:
    """Inyecta el CSS corporativo UNA vez por sesion.

    Debe llamarse al inicio de main_medicare.py, antes de cualquier
    widget de Streamlit para evitar flickering.
    """
    if st.session_state.get(CSS_INYECTADO_KEY):
        return
    st.session_state[CSS_INYECTADO_KEY] = True

    st.markdown(f"""<style>
    /* ─── 0. RESET BASE ─────────────────────────────── */
    .stApp, [data-testid="stAppViewContainer"] {{
        contain: layout style !important;
    }}

    /* ─── 1. FONDO CORPORATIVO 4 CAPAS ─────────────── */
    .stApp {{
        background: linear-gradient(160deg, #08101e 0%, #0c1929 35%, #0f1f35 65%, #070e18 100%) !important;
    }}
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, rgba(8,16,30,0.98) 0%, rgba(12,25,41,0.96) 50%, rgba(8,18,30,0.98) 100%) !important;
        border-right: 1px solid rgba(100,180,255,0.06) !important;
    }}

    /* ─── 2. INPUTS CON FOCUS GLOW ─────────────────── */
    input, select, textarea,
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input,
    [data-testid="stTimeInput"] input {{
        border-radius: 10px !important;
        border: 1px solid rgba(100,180,255,0.1) !important;
        background: rgba(0,0,0,0.15) !important;
        color: #e2e8f0 !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }}
    input:focus, select:focus, textarea:focus,
    [data-testid="stTextInput"] input:focus {{
        border-color: #0ea5e9 !important;
        box-shadow: 0 0 0 3px rgba(14,165,233,0.12) !important;
    }}

    /* ─── 3. BOTONES CORPORATIVOS ──────────────────── */
    [data-testid="stButton"] button {{
        border-radius: 12px !important;
        font-weight: 600 !important;
        letter-spacing: 0.01em !important;
        transition: all 0.18s cubic-bezier(0.4,0,0.2,1) !important;
        border: 1px solid rgba(100,180,255,0.08) !important;
        background: rgba(255,255,255,0.03) !important;
        min-height: 40px !important;
        color: #e2e8f0 !important;
    }}
    [data-testid="stButton"] button:hover {{
        border-color: rgba(14,165,233,0.2) !important;
        box-shadow: 0 4px 16px rgba(14,165,233,0.1) !important;
    }}
    [data-testid="stButton"] button:active {{
        transform: scale(0.98) !important;
    }}
    [data-testid="stButton"] button[kind="primary"] {{
        background: linear-gradient(135deg, #1d4ed8, #0ea5e9) !important;
        border: none !important;
        box-shadow: 0 4px 18px rgba(14,165,233,0.18) !important;
        color: #fff !important;
    }}
    [data-testid="stButton"] button[kind="primary"]:hover {{
        box-shadow: 0 6px 24px rgba(14,165,233,0.28) !important;
        filter: brightness(1.04) !important;
    }}
    [data-testid="stButton"] button[kind="secondary"] {{
        background: rgba(30,41,59,0.6) !important;
        border: 1px solid rgba(100,180,255,0.1) !important;
    }}

    /* ─── 4. TARJETAS Y FORMULARIOS ────────────────── */
    div[data-testid="stForm"],
    div[data-testid="stMetric"],
    div[data-testid="stDataFrame"],
    div[data-testid="stTable"],
    .stAlert, .streamlit-expanderHeader {{
        background: rgba(255,255,255,0.02) !important;
        border: 1px solid rgba(100,180,255,0.06) !important;
        border-radius: 14px !important;
        box-shadow: 0 2px 16px rgba(0,0,0,0.12), inset 0 1px 0 rgba(255,255,255,0.03) !important;
        transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
    }}

    /* ─── 5. METRICAS ───────────────────────────────── */
    [data-testid="stMetricValue"] {{
        background: linear-gradient(135deg, #38bdf8, #818cf8) !important;
        -webkit-background-clip: text !important;
        -webkit-text-fill-color: transparent !important;
        font-weight: 800 !important;
        font-size: clamp(1.2rem, 2vw, 1.8rem) !important;
    }}
    [data-testid="stMetricLabel"] {{
        color: #94a3b8 !important;
        font-size: 0.78rem !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
    }}

    /* ─── 6. TABS ────────────────────────────────────── */
    [data-testid="stTabs"] [role="tab"] {{
        border-radius: 8px 8px 0 0 !important;
        padding: 8px 18px !important;
        transition: all 0.18s ease !important;
        color: #94a3b8 !important;
        font-weight: 600 !important;
    }}
    [data-testid="stTabs"] [role="tab"][aria-selected="true"] {{
        background: rgba(14,165,233,0.08) !important;
        color: #38bdf8 !important;
        border-bottom: 2px solid #0ea5e9 !important;
    }}
    [data-testid="stTabs"] [role="tab"]:hover {{
        color: #e2e8f0 !important;
        background: rgba(255,255,255,0.03) !important;
    }}

    /* ─── 7. SCROLLBAR SUTIL ────────────────────────── */
    ::-webkit-scrollbar {{ width: 5px !important; height: 5px !important; }}
    ::-webkit-scrollbar-track {{ background: transparent !important; }}
    ::-webkit-scrollbar-thumb {{
        background: rgba(14,165,233,0.12) !important;
        border-radius: 10px !important;
    }}
    ::-webkit-scrollbar-thumb:hover {{ background: rgba(14,165,233,0.25) !important; }}

    /* ─── 8. TABLAS ──────────────────────────────────── */
    .stDataFrame {{ border-radius: 12px !important; }}
    div[data-testid="stDataFrame"] table {{ font-size: 0.85rem !important; }}
    div[data-testid="stDataFrame"] thead th {{
        background: rgba(14,165,233,0.04) !important;
        border-bottom: 1px solid rgba(100,180,255,0.08) !important;
        padding: 10px 12px !important;
        font-weight: 700 !important;
        color: #c0d8e8 !important;
    }}

    /* ─── 9. SPINNER ─────────────────────────────────── */
    .stSpinner > div > div {{
        border-width: 2.5px !important;
        border-color: rgba(14,165,233,0.06) !important;
        border-top-color: #0ea5e9 !important;
    }}

    /* ─── 10. MOBILE: GPU-SAFE OVERRIDES ────────────── */
    @media (hover: none) and (pointer: coarse) {{
        *, *::before, *::after {{
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
        }}
        input, textarea, select {{
            font-size: 16px !important;
        }}
        [data-testid="stButton"] button {{
            min-height: 44px !important;
        }}
        [data-testid="stButton"], [data-testid="stFormSubmitButton"],
        .stDownloadButton {{
            width: 100% !important;
        }}
        [data-testid="stMetric"] {{
            transform: none !important;
            will-change: auto !important;
        }}
        div[data-testid="stForm"],
        div[data-testid="stMetric"],
        div[data-testid="stDataFrame"] {{
            box-shadow: none !important;
        }}
    }}
    </style>""", unsafe_allow_html=True)
