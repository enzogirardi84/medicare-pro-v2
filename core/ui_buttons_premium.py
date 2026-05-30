"""Micro-interacciones premium para botones: hover glow, loading spinner
cromatico y ripple tactil. Transiciones aceleradas por hardware GPU.
"""
from __future__ import annotations

import streamlit as st


def inyectar_buttons_premium() -> None:
    """Inyecta CSS premium para todos los botones de la app.

    Efectos:
    - Hover con inset glow + elevacion -1px
    - Spinner cromatico con colores corporativos
    - Ripple tactil al hacer click
    - Transiciones cubic-bezier aceleradas por GPU
    """
    st.markdown("""<style>
    /* ════════════════════════════════════════════════════════
       BASE: Transiciones GPU aceleradas
       ════════════════════════════════════════════════════════ */
    [data-testid="stButton"] button,
    [data-testid="stFormSubmitButton"] button,
    .stDownloadButton button {
        transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1) !important;
        will-change: transform, box-shadow !important;
        position: relative !important;
        overflow: hidden !important;
    }

    /* ════════════════════════════════════════════════════════
       HOVER PREMIUM: inset glow + elevacion
       ════════════════════════════════════════════════════════ */
    @media (hover: hover) {
        [data-testid="stButton"] button:hover,
        [data-testid="stFormSubmitButton"] button:hover {
            transform: translateY(-1px) !important;
            border-color: rgba(14,165,233,0.25) !important;
            box-shadow:
                0 6px 24px rgba(14,165,233,0.12),
                inset 0 1px 0 rgba(255,255,255,0.08) !important;
        }

        [data-testid="stButton"] button[kind="primary"]:hover {
            box-shadow:
                0 8px 28px rgba(14,165,233,0.22),
                inset 0 1px 0 rgba(255,255,255,0.12) !important;
            filter: brightness(1.06) !important;
        }

        [data-testid="stButton"] button[kind="secondary"]:hover {
            background: rgba(30,41,59,0.8) !important;
            border-color: rgba(14,165,233,0.15) !important;
        }
    }

    /* ════════════════════════════════════════════════════════
       ESTADO ACTIVE: escala táctil
       ════════════════════════════════════════════════════════ */
    [data-testid="stButton"] button:active,
    [data-testid="stFormSubmitButton"] button:active {
        transform: scale(0.97) !important;
        transition-duration: 0.05s !important;
    }

    /* ════════════════════════════════════════════════════════
       RIPPLE TACTIL (destello en el borde)
       ════════════════════════════════════════════════════════ */
    [data-testid="stButton"] button::after,
    [data-testid="stFormSubmitButton"] button::after {
        content: '' !important;
        position: absolute !important;
        inset: 0 !important;
        border-radius: inherit !important;
        background: rgba(14,165,233,0.08) !important;
        opacity: 0 !important;
        transition: opacity 0.3s ease !important;
        pointer-events: none !important;
    }

    [data-testid="stButton"] button:active::after,
    [data-testid="stFormSubmitButton"] button:active::after {
        opacity: 1 !important;
        transition-duration: 0.1s !important;
    }

    /* ════════════════════════════════════════════════════════
       SPINNER CROMATICO (animacion de anillo)
       ════════════════════════════════════════════════════════ */
    @keyframes mc-spinner-rotate {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
    }

    .stSpinner > div > div {
        width: 28px !important;
        height: 28px !important;
        border-width: 3px !important;
        border-style: solid !important;
        border-color: rgba(14,165,233,0.08) !important;
        border-top-color: #0ea5e9 !important;
        border-right-color: #14b8a6 !important;
        border-bottom-color: #818cf8 !important;
        border-radius: 50% !important;
        animation: mc-spinner-rotate 0.8s linear infinite !important;
        will-change: transform !important;
    }

    /* ─── Boton deshabilitado ────────────────────────────── */
    [data-testid="stButton"] button:disabled,
    [data-testid="stFormSubmitButton"] button:disabled {
        opacity: 0.4 !important;
        cursor: not-allowed !important;
        transform: none !important;
    }
    </style>""", unsafe_allow_html=True)
