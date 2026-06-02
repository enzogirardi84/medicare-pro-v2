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


def aplicar_layout_compacto_final() -> None:
    """Override final de layout para evitar sidebar cortado y UI sobredimensionada."""
    if st.session_state.get("_mc_layout_compacto_final_v1"):
        return
    st.session_state["_mc_layout_compacto_final_v1"] = True

    st.markdown(
        """
        <style>
            :root {
                --mc-layout-sidebar-desktop: min(280px, 22vw);
                --mc-layout-sidebar-tablet: min(260px, 35vw);
                --mc-layout-content-max: 1280px;
            }

            html {
                overflow-x: hidden !important;
                width: 100% !important;
            }
            body {
                width: 100% !important;
                position: relative !important;
            }
            *, *::before, *::after {
                box-sizing: border-box !important;
            }
            .block-container, [data-testid="stMain"], section.main, main {
                max-width: 100vw !important;
            }
            img, video, canvas, svg, iframe {
                max-width: 100% !important;
                height: auto !important;
            }
            table, .stDataFrame, [data-testid="stDataFrame"] {
                max-width: 100% !important;
                overflow-x: auto !important;
            }

            [data-testid="stMain"] .block-container,
            section.main .block-container,
            .block-container {
                max-width: min(100%, var(--mc-layout-content-max)) !important;
                width: 100% !important;
                padding-top: 0.55rem !important;
                padding-bottom: 0.75rem !important;
                padding-left: 1rem !important;
                padding-right: 1rem !important;
                overflow-x: hidden !important;
            }

            [data-testid="stVerticalBlock"] {
                gap: 0.45rem !important;
            }

            [data-testid="stHorizontalBlock"] {
                gap: 0.65rem !important;
                align-items: stretch !important;
            }

            [data-testid="stElementContainer"],
            .element-container {
                margin-bottom: 0.28rem !important;
            }

            h1 { font-size: 1.35rem !important; line-height: 1.2 !important; }
            h2 { font-size: 1.16rem !important; line-height: 1.25 !important; }
            h3 { font-size: 1rem !important; line-height: 1.25 !important; }
            p, li, label, [data-testid="stMarkdownContainer"] {
                font-size: 0.92rem !important;
                line-height: 1.42 !important;
            }

            [data-testid="stMetricValue"] {
                font-size: 1.25rem !important;
                line-height: 1.12 !important;
            }

            [data-testid="stMetricLabel"],
            [data-testid="stCaptionContainer"] {
                font-size: 0.76rem !important;
                line-height: 1.3 !important;
            }

            div[data-testid="stForm"],
            [data-testid="stExpander"] details,
            [data-testid="stMetric"],
            [data-testid="stAlert"],
            [data-testid="stDataFrame"],
            [data-testid="stDataEditor"],
            [data-testid="stTable"] {
                border-radius: 10px !important;
                box-shadow: none !important;
            }

            div[data-testid="stForm"] {
                padding: 0.65rem 0.75rem 0.55rem !important;
                max-width: 100% !important;
            }

            [data-testid="stExpander"] details summary {
                min-height: 38px !important;
                padding: 0.48rem 0.65rem !important;
            }

            [data-testid="stExpander"] details > div {
                padding-top: 0.45rem !important;
            }

            [data-testid="stMetric"] {
                padding: 0.55rem 0.65rem !important;
                min-height: 0 !important;
            }

            [data-testid="stAlert"] > div {
                padding: 0.55rem 0.7rem !important;
            }

            [data-testid="stTabs"] [role="tablist"] {
                gap: 0.22rem !important;
                margin-bottom: 0.45rem !important;
                overflow-x: auto !important;
                scrollbar-width: thin !important;
            }

            [data-testid="stTabs"] [role="tab"] {
                min-height: 34px !important;
                padding: 0.35rem 0.65rem !important;
                font-size: 0.82rem !important;
                white-space: nowrap !important;
            }

            [data-testid="stDataFrame"],
            [data-testid="stDataEditor"],
            [data-testid="stTable"] {
                max-width: 100% !important;
                overflow-x: auto !important;
            }

            [data-testid="stDataFrame"] table,
            [data-testid="stTable"] table {
                font-size: 0.82rem !important;
            }

            [data-testid="stButton"] button,
            [data-testid="stFormSubmitButton"] button,
            [data-testid="stDownloadButton"] button {
                min-height: 36px !important;
                padding: 0.38rem 0.65rem !important;
                font-size: 0.84rem !important;
                line-height: 1.2 !important;
                white-space: normal !important;
            }

            [data-baseweb="input"] > div,
            [data-baseweb="select"] > div,
            input,
            textarea {
                min-height: 36px !important;
                font-size: 0.9rem !important;
            }

            textarea {
                min-height: 76px !important;
            }

            [data-testid="stSelectbox"],
            [data-testid="stTextInput"],
            [data-testid="stTextArea"],
            [data-testid="stNumberInput"],
            [data-testid="stDateInput"],
            [data-testid="stTimeInput"],
            [data-testid="stMultiSelect"],
            [data-testid="stFileUploader"] {
                max-width: 100% !important;
            }

            @media (min-width: 1025px) {
                [data-testid="stSidebar"],
                section[data-testid="stSidebar"],
                section[data-testid="stSidebar"][aria-expanded="true"],
                section[data-testid="stSidebar"][aria-expanded="false"] {
                    width: var(--mc-layout-sidebar-desktop) !important;
                    min-width: var(--mc-layout-sidebar-desktop) !important;
                    max-width: var(--mc-layout-sidebar-desktop) !important;
                    flex: 0 0 var(--mc-layout-sidebar-desktop) !important;
                    overflow-y: auto !important;
                    overflow-x: hidden !important;
                    visibility: visible !important;
                    opacity: 1 !important;
                    pointer-events: auto !important;
                }
            }

            @media (min-width: 768px) and (max-width: 1024px) {
                [data-testid="stSidebar"],
                section[data-testid="stSidebar"],
                section[data-testid="stSidebar"][aria-expanded="true"],
                section[data-testid="stSidebar"][aria-expanded="false"] {
                    width: var(--mc-layout-sidebar-tablet) !important;
                    min-width: var(--mc-layout-sidebar-tablet) !important;
                    max-width: var(--mc-layout-sidebar-tablet) !important;
                    flex: 0 0 var(--mc-layout-sidebar-tablet) !important;
                    overflow: hidden !important;
                }

                [data-testid="stMain"] .block-container,
                .block-container {
                    padding-left: 0.85rem !important;
                    padding-right: 0.85rem !important;
                }
            }

            @media (min-width: 768px) {
                [data-testid="stSidebar"] > div:first-child,
                [data-testid="stSidebarContent"] {
                    max-height: 100vh !important;
                    max-height: 100dvh !important;
                    overflow-y: auto !important;
                    overflow-x: hidden !important;
                    overscroll-behavior: contain !important;
                    -webkit-overflow-scrolling: touch !important;
                }

                [data-testid="stSidebar"] .block-container {
                    padding: 0.45rem 0.55rem 0.65rem !important;
                    max-width: 100% !important;
                }

                [data-testid="stSidebar"] [data-testid="stButton"] button,
                [data-testid="stSidebar"] button {
                    min-height: 34px !important;
                    padding: 0.32rem 0.5rem !important;
                    font-size: 0.8rem !important;
                    line-height: 1.18 !important;
                    text-align: left !important;
                    justify-content: flex-start !important;
                    overflow-wrap: anywhere !important;
                }

                [data-testid="stSidebar"] p,
                [data-testid="stSidebar"] label,
                [data-testid="stSidebar"] span,
                [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] {
                    font-size: 0.8rem !important;
                    line-height: 1.28 !important;
                    overflow-wrap: anywhere !important;
                }

                [data-testid="stSidebar"] h1,
                [data-testid="stSidebar"] h2,
                [data-testid="stSidebar"] h3 {
                    font-size: 0.95rem !important;
                    line-height: 1.2 !important;
                    margin-bottom: 0.35rem !important;
                }

                [data-testid="stSidebar"] img {
                    max-width: 100% !important;
                    height: auto !important;
                }

                [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
                    gap: 0.28rem !important;
                }
            }

            @media (max-width: 767px) {
                html {
                    overflow-x: hidden !important;
                    width: 100% !important;
                }
                body {
                    width: 100% !important;
                    position: relative !important;
                }
                [data-testid="stAppViewContainer"],
                [data-testid="stMain"],
                section.main,
                main {
                    width: 100% !important;
                    max-width: 100vw !important;
                    margin-left: 0 !important;
                    padding-left: 0 !important;
                    padding-right: 0 !important;
                    overflow-x: hidden !important;
                }

                [data-testid="stMain"] .block-container,
                .block-container {
                    width: 100% !important;
                    max-width: 100vw !important;
                    padding: 0.55rem 0.5rem 1rem !important;
                }

                h1 { font-size: 1.15rem !important; }
                h2 { font-size: 1.02rem !important; }
                h3 { font-size: 0.94rem !important; }

                [data-testid="stButton"] button,
                [data-testid="stFormSubmitButton"] button,
                [data-testid="stDownloadButton"] button {
                    min-height: 40px !important;
                    font-size: 0.82rem !important;
                }

                [data-testid="stHorizontalBlock"] {
                    gap: 0.45rem !important;
                }

                [data-testid="stHorizontalBlock"] > div,
                [data-testid="stHorizontalBlock"] > [data-testid="column"],
                [data-testid="column"],
                div[data-testid="column"] {
                    min-width: min(100%, 9.5rem) !important;
                }

                [data-testid="stMetric"] {
                    padding: 0.45rem 0.5rem !important;
                }

                [data-testid="stTabs"] [role="tab"] {
                    min-height: 38px !important;
                    padding: 0.35rem 0.55rem !important;
                    font-size: 0.78rem !important;
                }

                div[data-testid="stForm"] {
                    padding: 0.55rem 0.6rem 0.5rem !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
