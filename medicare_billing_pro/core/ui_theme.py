"""Tema visual compacto y consistente para Medicare Billing Pro."""
from __future__ import annotations

import streamlit as st


def aplicar_tema_billing() -> None:
    """Inyecta CSS global para evitar textos cortados y paginas infinitas."""
    st.markdown(
        """
        <style>
        :root {
            --mbp-bg: #070b14;
            --mbp-panel: #0f172a;
            --mbp-panel-2: #111827;
            --mbp-line: #273449;
            --mbp-text: #f8fafc;
            --mbp-muted: #94a3b8;
            --mbp-teal: #14b8a6;
            --mbp-blue: #2563eb;
            --mbp-danger: #ef4444;
        }

        .stApp,
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(ellipse 70% 45% at 100% 0%, rgba(20, 184, 166, 0.10), transparent 55%),
                linear-gradient(180deg, var(--mbp-bg) 0%, #050814 100%) !important;
            color: var(--mbp-text) !important;
        }

        .block-container {
            max-width: 1420px !important;
            padding-top: 1rem !important;
            padding-bottom: 1.25rem !important;
        }

        [data-testid="stSidebar"] {
            background: #0b1220 !important;
            border-right: 1px solid var(--mbp-line) !important;
        }

        h1, h2, h3 {
            letter-spacing: 0 !important;
            line-height: 1.16 !important;
        }

        p, span, label, div {
            letter-spacing: 0 !important;
        }

        div[data-testid="stButton"] > button,
        div[data-testid="stDownloadButton"] > button,
        div[data-testid="stFormSubmitButton"] > button {
            min-height: 44px !important;
            height: auto !important;
            width: 100% !important;
            border-radius: 8px !important;
            white-space: normal !important;
            word-break: normal !important;
            overflow-wrap: anywhere !important;
            line-height: 1.18 !important;
            padding: 0.58rem 0.75rem !important;
            background: #111827 !important;
            border: 1px solid #334155 !important;
            color: var(--mbp-text) !important;
            box-shadow: none !important;
        }

        div[data-testid="stButton"] > button p,
        div[data-testid="stDownloadButton"] > button p,
        div[data-testid="stFormSubmitButton"] > button p {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            line-height: 1.18 !important;
            color: inherit !important;
        }

        div[data-testid="stButton"] > button[kind="primary"],
        div[data-testid="stFormSubmitButton"] > button {
            background: linear-gradient(135deg, var(--mbp-teal), var(--mbp-blue)) !important;
            border: 1px solid rgba(94, 234, 212, 0.38) !important;
            font-weight: 700 !important;
        }

        div[data-testid="stButton"] > button:hover,
        div[data-testid="stDownloadButton"] > button:hover {
            border-color: var(--mbp-teal) !important;
            filter: brightness(1.08);
        }

        div[data-testid="stMetric"] {
            min-height: 84px !important;
            padding: 0.8rem 0.9rem !important;
            border-radius: 10px !important;
            border: 1px solid var(--mbp-line) !important;
            background: rgba(15, 23, 42, 0.72) !important;
        }

        [data-testid="stMetricLabel"],
        [data-testid="stMetricLabel"] * {
            white-space: normal !important;
            overflow: visible !important;
            text-overflow: clip !important;
            color: var(--mbp-muted) !important;
            line-height: 1.15 !important;
        }

        [data-testid="stMetricValue"] {
            font-size: clamp(1.2rem, 2vw, 1.85rem) !important;
            line-height: 1.1 !important;
        }

        [data-testid="stTabs"] [role="tablist"] {
            overflow-x: auto !important;
            gap: 0.25rem !important;
            border-bottom: 1px solid var(--mbp-line) !important;
        }

        [data-testid="stTabs"] [role="tab"] {
            min-width: max-content !important;
            white-space: nowrap !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 10px !important;
            border: 1px solid var(--mbp-line) !important;
            background: rgba(15, 23, 42, 0.68) !important;
        }

        [data-testid="stVerticalBlockBorderWrapper"] [data-testid="stVerticalBlockBorderWrapper"] {
            border-radius: 8px !important;
        }

        div[data-testid="stTextInput"] input,
        div[data-testid="stNumberInput"] input,
        div[data-testid="stDateInput"] input,
        textarea,
        div[data-baseweb="select"] > div {
            min-height: 42px !important;
            border-radius: 8px !important;
            border: 1px solid #334155 !important;
            background: #111827 !important;
            color: var(--mbp-text) !important;
        }

        div[data-testid="stDataFrame"],
        div[data-testid="stTable"] {
            max-height: 62vh !important;
            overflow: auto !important;
            border: 1px solid var(--mbp-line) !important;
            border-radius: 8px !important;
        }

        [data-testid="stExpander"] details {
            border-radius: 8px !important;
            border: 1px solid var(--mbp-line) !important;
            background: rgba(15, 23, 42, 0.62) !important;
        }

        @media (max-width: 900px) {
            .block-container {
                padding-left: 0.85rem !important;
                padding-right: 0.85rem !important;
            }

            [data-testid="column"] {
                min-width: min(100%, 260px) !important;
            }

            div[data-testid="stMetric"] {
                min-height: 72px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
