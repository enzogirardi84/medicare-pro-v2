"""Redisenio cinetico de sliders para calculadora de dosis y triage.
Thumb expandido 24px, active grow effect 1.15x, carril 8px.
Optimizado para arrastre en ambulancias en movimiento.
"""
from __future__ import annotations

import streamlit as st


def inyectar_sliders_kinetic() -> None:
    """Inyecta CSS premium para sliders tactiles.

    Aplica a st.slider y st.select_slider de Streamlit.
    """
    st.markdown("""<style>
    /* ════════════════════════════════════════════════════════
       CARRIL (track) del slider
       ════════════════════════════════════════════════════════ */
    [data-testid="stSlider"] > div {
        padding: 12px 0 !important;
    }

    /* Carril de fondo */
    [data-testid="stSlider"] [role="slider"] {
        height: 8px !important;
        border-radius: 9999px !important;
        background: rgba(30,41,59,0.8) !important;
        border: 1px solid rgba(100,180,255,0.08) !important;
    }

    /* Carril activo (porcion llenada) */
    [data-testid="stSlider"] [role="slider"]::-webkit-slider-runnable-track {
        height: 8px !important;
        border-radius: 9999px !important;
        background: rgba(30,41,59,0.8) !important;
    }

    /* ════════════════════════════════════════════════════════
       THUMB (selector circular)
       ════════════════════════════════════════════════════════ */
    [data-testid="stSlider"] [role="slider"]::-webkit-slider-thumb {
        width: 24px !important;
        height: 24px !important;
        border-radius: 50% !important;
        background: radial-gradient(circle at 30% 30%, #38bdf8, #0ea5e9) !important;
        border: 2px solid rgba(255,255,255,0.25) !important;
        box-shadow:
            0 2px 8px rgba(0,0,0,0.3),
            0 0 0 4px rgba(14,165,233,0.1) !important;
        cursor: grab !important;
        transition: transform 0.15s ease, box-shadow 0.15s ease !important;
        will-change: transform !important;
        -webkit-appearance: none !important;
        appearance: none !important;
    }

    /* Firefox */
    [data-testid="stSlider"] [role="slider"]::-moz-range-thumb {
        width: 24px !important;
        height: 24px !important;
        border-radius: 50% !important;
        background: radial-gradient(circle at 30% 30%, #38bdf8, #0ea5e9) !important;
        border: 2px solid rgba(255,255,255,0.25) !important;
        box-shadow:
            0 2px 8px rgba(0,0,0,0.3),
            0 0 0 4px rgba(14,165,233,0.1) !important;
        cursor: grab !important;
    }

    /* ════════════════════════════════════════════════════════
       ACTIVE GROW EFFECT (al presionar)
       ════════════════════════════════════════════════════════ */
    [data-testid="stSlider"] [role="slider"]:active::-webkit-slider-thumb {
        transform: scale(1.15) !important;
        box-shadow:
            0 4px 16px rgba(14,165,233,0.35),
            0 0 0 6px rgba(14,165,233,0.12) !important;
        cursor: grabbing !important;
        transition-duration: 0.05s !important;
    }

    [data-testid="stSlider"] [role="slider"]:active::-moz-range-thumb {
        transform: scale(1.15) !important;
        box-shadow:
            0 4px 16px rgba(14,165,233,0.35),
            0 0 0 6px rgba(14,165,233,0.12) !important;
        cursor: grabbing !important;
    }

    /* ════════════════════════════════════════════════════════
       SELECT SLIDER (select_slider)
       ════════════════════════════════════════════════════════ */
    [data-testid="stSelectSlider"] > div {
        min-height: 52px !important;
    }

    /* Labels de opciones */
    [data-testid="stSelectSlider"] span {
        font-size: 0.85rem !important;
        font-weight: 600 !important;
        padding: 4px 8px !important;
        min-width: 32px !important;
        text-align: center !important;
    }

    /* ════════════════════════════════════════════════════════
       RANGO (st.slider con valor minimo y maximo)
       ════════════════════════════════════════════════════════ */
    [data-testid="stSlider"] [data-baseweb="input-slider"] {
        padding: 4px 0 !important;
    }

    /* ════════════════════════════════════════════════════════
       NUMERO DE VALOR (tooltip con valor exacto)
       ════════════════════════════════════════════════════════ */
    [data-testid="stSlider"] [role="slider"] + div {
        font-size: 0.9rem !important;
        font-weight: 700 !important;
        color: #38bdf8 !important;
        min-width: 36px !important;
        text-align: center !important;
    }

    /* ════════════════════════════════════════════════════════
       MOBILE: touch-friendly extra
       ════════════════════════════════════════════════════════ */
    @media (hover: none) and (pointer: coarse) {
        [data-testid="stSlider"] {
            padding: 8px 0 !important;
        }
        [data-testid="stSlider"] [role="slider"]::-webkit-slider-thumb {
            width: 28px !important;
            height: 28px !important;
            border-width: 3px !important;
        }
        [data-testid="stSlider"] [role="slider"]::-moz-range-thumb {
            width: 28px !important;
            height: 28px !important;
        }
    }
    </style>""", unsafe_allow_html=True)
