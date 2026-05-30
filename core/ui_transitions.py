"""Transiciones suaves entre paginas y componentes mediante keyframes CSS.
Fade + slide up (250ms) optimizado para GPU. Sin caidas de FPS.
"""
from __future__ import annotations

import streamlit as st


def inyectar_transiciones() -> None:
    """Inyecta animaciones de transicion entre modulos.

    - Fade In + Slide Up al cargar una vista nueva
    - Solo se aplica a contenedores maestros (stVerticalBlock)
    - 250ms de duracion, aceleracion suave
    - Optimizado para GPU: solo opacity + transform
    - No interfiere con formularios activos
    """
    st.markdown("""<style>
    /* ════════════════════════════════════════════════════════
       KEYFRAME: Fade + Slide Up
       ════════════════════════════════════════════════════════ */
    @keyframes mc-fade-slide-in {
        from {
            opacity: 0;
            transform: translateY(8px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }

    /* ════════════════════════════════════════════════════════
       APLICAR A CONTENEDORES PRINCIPALES
       Solo a los bloques verticales del area principal,
       no al sidebar ni headers.
       ════════════════════════════════════════════════════════ */
    section[data-testid="stAppViewContainer"] [data-testid="stVerticalBlock"] > div {
        animation: mc-fade-slide-in 0.25s ease-out !important;
        will-change: opacity, transform !important;
    }

    /* No animar bloques anidados (solo el primer nivel) */
    section[data-testid="stAppViewContainer"]
    [data-testid="stVerticalBlock"]
    [data-testid="stVerticalBlock"] > div {
        animation: none !important;
    }

    /* No animar el sidebar */
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] > div {
        animation: none !important;
    }

    /* ════════════════════════════════════════════════════════
       FADE-IN SUTIL PARA LA APP COMPLETA
       ════════════════════════════════════════════════════════ */
    @keyframes mc-fade-in {
        from { opacity: 0.92; }
        to { opacity: 1; }
    }

    .stApp {
        animation: mc-fade-in 0.15s ease-out !important;
    }

    /* ════════════════════════════════════════════════════════
       TRANSICION DE METRICAS (st.metric)
       ════════════════════════════════════════════════════════ */
    @keyframes mc-metric-count {
        from { opacity: 0; transform: scale(0.95); }
        to { opacity: 1; transform: scale(1); }
    }

    [data-testid="stMetric"] {
        animation: mc-metric-count 0.3s ease-out !important;
    }

    /* ════════════════════════════════════════════════════════
       REDUCED MOTION: respetar preferencias del usuario
       ════════════════════════════════════════════════════════ */
    @media (prefers-reduced-motion: reduce) {
        section[data-testid="stAppViewContainer"] [data-testid="stVerticalBlock"] > div {
            animation: none !important;
        }
        [data-testid="stMetric"] {
            animation: none !important;
        }
        .stApp {
            animation: none !important;
        }
    }

    /* ════════════════════════════════════════════════════════
       MOBILE: animaciones mas ligeras
       ════════════════════════════════════════════════════════ */
    @media (hover: none) and (pointer: coarse) {
        section[data-testid="stAppViewContainer"] [data-testid="stVerticalBlock"] > div {
            animation-duration: 0.18s !important;
        }
    }
    </style>""", unsafe_allow_html=True)
