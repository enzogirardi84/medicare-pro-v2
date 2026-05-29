"""Tema profesional premium MediCare PRO - Alto rendimiento."""

from __future__ import annotations

import streamlit as st


def aplicar_css_base() -> None:
    # Solo injectar UNA vez por sesion para evitar bloqueo en movil
    if st.session_state.get("_css_base_injected"):
        return
    st.session_state["_css_base_injected"] = True

    # Restore persistent theme on first load
    if "_theme_restored_v1" not in st.session_state:
        st.session_state["_theme_restored_v1"] = True
        _saved = st.session_state.get("settings_db", {}).get("app_theme", "")
        if _saved and "theme" not in st.session_state:
            st.session_state["theme"] = _saved

    st.markdown("""
        <style>
            :root {
                --mc-accent: #0ea5e9;
                --mc-accent-glow: rgba(14,165,233,0.12);
                --mc-teal: #14b8a6;
                --mc-border: rgba(100,180,255,0.07);
                --mc-border-hover: rgba(14,165,233,0.2);
                --mc-text: #e2e8f0;
                --mc-muted: #94a3b8;
                --mc-card-bg: rgba(255,255,255,0.02);
                --mc-input-bg: rgba(0,0,0,0.15);
            }

            .stApp, [data-testid="stAppViewContainer"] {
                contain: layout style !important;
            }

            /* ── Fondo premium profundo ─────────────────── */
            .stApp {
                background: linear-gradient(160deg, #08101e 0%, #0c1929 35%, #0f1f35 65%, #070e18 100%) !important;
            }
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, rgba(8,16,30,0.98) 0%, rgba(12,25,41,0.96) 50%, rgba(8,18,30,0.98) 100%) !important;
                border-right: 1px solid rgba(100,180,255,0.06) !important;
            }
            [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
                color: #c8d8e8 !important;
            }

            /* ── Cards con borde sutil y hover elevado ─── */
            div[data-testid="stForm"],
            div[data-testid="stMetric"],
            div[data-testid="stDataFrame"],
            div[data-testid="stTable"],
            .stAlert, .streamlit-expanderHeader {
                background: var(--mc-card-bg) !important;
                border: 1px solid var(--mc-border) !important;
                border-radius: 14px !important;
                box-shadow: 0 2px 16px rgba(0,0,0,0.12), inset 0 1px 0 rgba(255,255,255,0.03) !important;
                transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
            }
            div[data-testid="stMetric"]:hover {
                border-color: var(--mc-border-hover) !important;
                box-shadow: 0 6px 28px var(--mc-accent-glow) !important;
            }

            /* ── Botones mas premium ────────────────────── */
            div[data-testid="stButton"] > button {
                border-radius: 12px !important;
                font-weight: 600 !important;
                letter-spacing: 0.01em !important;
                transition: all 0.18s cubic-bezier(0.4,0,0.2,1) !important;
                border: 1px solid var(--mc-border) !important;
                background: rgba(255,255,255,0.03) !important;
                min-height: 40px !important;
                color: var(--mc-text) !important;
            }
            div[data-testid="stButton"] > button:hover {
                border-color: var(--mc-border-hover) !important;
                box-shadow: 0 4px 16px var(--mc-accent-glow) !important;
            }
            div[data-testid="stButton"] > button:active {
                transform: scale(0.98) !important;
            }
            div[data-testid="stButton"] > button[kind="primary"] {
                background: linear-gradient(135deg, #1d4ed8, #0ea5e9) !important;
                border: none !important;
                box-shadow: 0 4px 18px rgba(14,165,233,0.18) !important;
                color: #fff !important;
            }
            div[data-testid="stButton"] > button[kind="primary"]:hover {
                box-shadow: 0 6px 24px rgba(14,165,233,0.28) !important;
                filter: brightness(1.04) !important;
            }
            div[data-testid="stButton"] > button[kind="secondary"] {
                background: rgba(30,41,59,0.6) !important;
                border: 1px solid rgba(100,180,255,0.1) !important;
            }

            /* ── Inputs con focus glow ──────────────────── */
            input, select, textarea, div[data-baseweb="select"] > div {
                border-radius: 10px !important;
                border: 1px solid rgba(100,180,255,0.1) !important;
                background: var(--mc-input-bg) !important;
                color: var(--mc-text) !important;
                transition: border-color 0.2s ease, box-shadow 0.2s ease !important;
            }
            input:focus, select:focus, textarea:focus,
            div[data-baseweb="select"]:focus-within > div {
                border-color: var(--mc-accent) !important;
                box-shadow: 0 0 0 3px var(--mc-accent-glow) !important;
            }

            /* ── Metricas con gradiente ─────────────────── */
            [data-testid="stMetricValue"] {
                background: linear-gradient(135deg, #38bdf8, #818cf8) !important;
                -webkit-background-clip: text !important;
                -webkit-text-fill-color: transparent !important;
                font-weight: 800 !important;
                font-size: clamp(1.2rem, 2vw, 1.8rem) !important;
            }
            [data-testid="stMetricLabel"] {
                color: var(--mc-muted) !important;
                font-size: 0.78rem !important;
                font-weight: 600 !important;
                text-transform: uppercase !important;
                letter-spacing: 0.04em !important;
            }

            /* ── Tabs mejorados ─────────────────────────── */
            [data-testid="stTabs"] [role="tab"] {
                border-radius: 8px 8px 0 0 !important;
                padding: 8px 18px !important;
                transition: all 0.18s ease !important;
                color: var(--mc-muted) !important;
                font-weight: 600 !important;
            }
            [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
                background: rgba(14,165,233,0.08) !important;
                color: #38bdf8 !important;
                border-bottom: 2px solid var(--mc-accent) !important;
            }
            [data-testid="stTabs"] [role="tab"]:hover {
                color: var(--mc-text) !important;
                background: rgba(255,255,255,0.03) !important;
            }

            /* ── Headers ─────────────────────────────────── */
            h1, h2, h3, h4 {
                color: var(--mc-text) !important;
                font-weight: 700 !important;
                letter-spacing: -0.02em !important;
            }
            h1 { font-size: 1.45rem !important; }
            h2 { font-size: 1.25rem !important; }
            h3 { font-size: 1.05rem !important; }

            /* ── Expander y divisores ────────────────────── */
            .streamlit-expanderHeader {
                border-radius: 10px !important;
                padding: 10px 14px !important;
                font-weight: 600 !important;
            }
            hr {
                border-color: rgba(100,180,255,0.05) !important;
                margin: 0.5rem 0 !important;
            }

            /* ── Scrollbar sutil ─────────────────────────── */
            ::-webkit-scrollbar { width: 5px !important; height: 5px !important; }
            ::-webkit-scrollbar-track { background: transparent !important; }
            ::-webkit-scrollbar-thumb {
                background: rgba(14,165,233,0.12) !important;
                border-radius: 10px !important;
            }
            ::-webkit-scrollbar-thumb:hover { background: rgba(14,165,233,0.25) !important; }

            /* ── Tablas mejoradas ────────────────────────── */
            .stDataFrame { border-radius: 12px !important; }
            div[data-testid="stDataFrame"] table { font-size: 0.85rem !important; }
            div[data-testid="stDataFrame"] thead th {
                background: rgba(14,165,233,0.04) !important;
                border-bottom: 1px solid rgba(100,180,255,0.08) !important;
                padding: 10px 12px !important;
                font-weight: 700 !important;
                color: #c0d8e8 !important;
            }

            /* ── Fade-in sutil ───────────────────────────── */
            .stApp {
                animation: mcFadeIn 0.15s ease-out;
            }
            @keyframes mcFadeIn {
                from { opacity: 0.92; }
                to { opacity: 1; }
            }

            /* ── Spinner ─────────────────────────────────── */
            .stSpinner > div > div {
                border-width: 2.5px !important;
                border-color: rgba(14,165,233,0.06) !important;
                border-top-color: var(--mc-accent) !important;
            }

            /* ── Alerts ──────────────────────────────────── */
            .stAlert { padding: 12px 16px !important; }
            .stAlert > div { gap: 10px !important; }

            /* ── Responsive ──────────────────────────────── */
            @media (max-width: 768px) {
                .stButton > button { min-height: 44px !important; font-size: 0.85rem !important; }
                [data-testid="stMetric"] { min-height: 60px !important; }
                [data-testid="stMetricValue"] { font-size: 1.1rem !important; }
                .block-container { padding: 0.3rem 0.5rem !important; }
                [data-testid="stHorizontalBlock"] { gap: 0.3rem !important; }
                h1 { font-size: 1.15rem !important; }
                h2 { font-size: 1.05rem !important; }
                h3 { font-size: 0.92rem !important; }
            }
            @media (min-width: 769px) and (max-width: 1024px) {
                .block-container { padding: 0.6rem 0.8rem !important; }
            }
        </style>
    """, unsafe_allow_html=True)
