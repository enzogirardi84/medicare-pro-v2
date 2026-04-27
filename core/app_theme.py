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

            /* =========================================================
               5. TOUR / ONBOARDING
               ========================================================= */
            .mc-tour-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(2, 6, 23, 0.7);
                z-index: 999998;
                backdrop-filter: blur(3px);
            }
            .mc-tour-tooltip {
                background: linear-gradient(135deg, rgba(30, 41, 59, 0.98) 0%, rgba(15, 23, 42, 0.99) 100%);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 16px;
                padding: 1.5rem;
                max-width: 450px;
                width: 90%;
                z-index: 999999;
                box-shadow: 0 25px 50px rgba(2, 6, 23, 0.5);
                backdrop-filter: blur(20px);
            }
            .mc-tour-header {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                margin-bottom: 1rem;
            }
            .mc-tour-badge {
                background: linear-gradient(135deg, #3b82f6, #22c55e);
                color: white;
                padding: 0.25rem 0.75rem;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 600;
            }
            .mc-tour-title {
                margin: 0;
                font-size: 1.25rem;
                font-weight: 600;
                color: #f8fafc;
            }
            .mc-tour-content {
                color: #94a3b8;
                line-height: 1.6;
                margin-bottom: 1.5rem;
                font-size: 0.95rem;
            }
            .mc-tour-progress {
                height: 4px;
                background: rgba(148, 163, 184, 0.2);
                border-radius: 2px;
                overflow: hidden;
                margin-bottom: 1.5rem;
            }
            .mc-tour-progress-bar {
                height: 100%;
                background: linear-gradient(90deg, #3b82f6, #22c55e);
                border-radius: 2px;
                transition: width 0.3s ease;
            }
            .mc-checklist-container {
                background: linear-gradient(135deg, rgba(30, 41, 59, 0.8) 0%, rgba(15, 23, 42, 0.9) 100%);
                border: 1px solid rgba(148, 163, 184, 0.15);
                border-radius: 12px;
                padding: 1.25rem;
                margin-bottom: 1.5rem;
            }
            .mc-checklist-header {
                display: flex;
                justify-content: space-between;
                align-items: center;
                margin-bottom: 1rem;
            }
            .mc-checklist-header h4 {
                margin: 0;
                font-size: 1.1rem;
                color: #f8fafc;
            }
            .mc-checklist-counter {
                background: rgba(59, 130, 246, 0.2);
                color: #3b82f6;
                padding: 0.375rem 0.875rem;
                border-radius: 9999px;
                font-size: 0.875rem;
                font-weight: 600;
            }
            .mc-checklist-progress-track {
                height: 6px;
                background: rgba(148, 163, 184, 0.2);
                border-radius: 3px;
                overflow: hidden;
            }
            .mc-checklist-progress-fill {
                height: 100%;
                background: linear-gradient(90deg, #3b82f6, #22c55e);
                border-radius: 3px;
                transition: width 0.3s ease;
            }
            .mc-checklist-icon {
                width: 28px;
                height: 28px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 0.875rem;
            }

            /* =========================================================
               6. SMART SEARCH
               ========================================================= */
            .mc-search-container {
                position: relative;
                margin-bottom: 1rem;
            }
            .mc-search-input-wrapper {
                position: relative;
                display: flex;
                align-items: center;
            }
            .mc-search-icon {
                position: absolute;
                left: 1rem;
                color: #64748b;
                font-size: 1.1rem;
                z-index: 10;
                pointer-events: none;
            }
            .mc-search-input {
                width: 100%;
                padding: 0.875rem 1rem 0.875rem 2.75rem;
                border: 2px solid rgba(148, 163, 184, 0.2);
                border-radius: 12px;
                background: rgba(15, 23, 42, 0.6);
                color: #f1f5f9;
                font-size: 1rem;
                transition: all 0.25s ease;
                backdrop-filter: blur(8px);
            }
            .mc-search-input:focus {
                outline: none;
                border-color: #3b82f6;
                box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.15);
                background: rgba(15, 23, 42, 0.8);
            }
            .mc-search-input::placeholder {
                color: #64748b;
            }
            .mc-search-badges {
                display: flex;
                gap: 0.5rem;
                margin-top: 0.75rem;
                flex-wrap: wrap;
            }
            .mc-search-badge {
                padding: 0.375rem 0.875rem;
                border-radius: 9999px;
                font-size: 0.75rem;
                font-weight: 600;
                cursor: pointer;
                transition: all 0.2s ease;
                border: 1px solid transparent;
                text-transform: uppercase;
                letter-spacing: 0.025em;
            }
            .mc-search-badge:hover {
                transform: translateY(-1px);
            }
            .mc-search-badge.active {
                background: rgba(59, 130, 246, 0.2);
                color: #3b82f6;
                border-color: rgba(59, 130, 246, 0.4);
            }
            .mc-search-badge.inactive {
                background: rgba(30, 41, 59, 0.5);
                color: #64748b;
                border-color: rgba(148, 163, 184, 0.2);
            }
            .mc-search-results-count {
                font-size: 0.875rem;
                color: #64748b;
                margin-top: 0.5rem;
            }
            .mc-sidebar-search {
                margin-bottom: 1rem;
            }
            .mc-sidebar-search input {
                background: rgba(15, 23, 42, 0.6) !important;
                border: 1px solid rgba(148, 163, 184, 0.2) !important;
                border-radius: 8px !important;
                color: #f1f5f9 !important;
                padding: 0.625rem 0.875rem !important;
            }
            .mc-sidebar-search input:focus {
                border-color: #3b82f6 !important;
                box-shadow: 0 0 0 2px rgba(59, 130, 246, 0.15) !important;
            }
            .mc-result-card {
                background: linear-gradient(135deg, rgba(30,41,59,0.6) 0%, rgba(15,23,42,0.8) 100%);
                border: 1px solid rgba(148,163,184,0.1);
                border-radius: 12px;
                padding: 1rem;
                margin-bottom: 0.75rem;
                cursor: pointer;
                transition: all 0.25s ease;
                position: relative;
                overflow: hidden;
            }
            .mc-result-card:hover {
                transform: translateY(-2px);
                border-color: rgba(148,163,184,0.2);
                box-shadow: 0 8px 30px rgba(2,6,23,0.25);
            }
            .mc-result-card:hover .mc-result-bar {
                opacity: 1;
            }
            .mc-result-bar {
                position: absolute;
                bottom: 0;
                left: 0;
                right: 0;
                height: 3px;
                background: linear-gradient(90deg,#3b82f6,#22c55e);
                opacity: 0;
                transition: opacity 0.3s ease;
            }

            /* =========================================================
               7. TELEMEDICINA
               ========================================================= */
            .mc-waiting-empty {
                background: rgba(30, 41, 59, 0.5);
                border: 2px dashed rgba(148, 163, 184, 0.3);
                border-radius: 16px;
                padding: 60px 20px;
                text-align: center;
                margin-top: 20px;
            }
            .mc-waiting-empty h3 {
                color: #64748b;
                margin: 0;
            }
            .mc-waiting-empty p {
                color: #94a3b8;
            }
            .mc-video-placeholder {
                background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%);
                border-radius: 12px;
                height: 400px;
                display: flex;
                align-items: center;
                justify-content: center;
                border: 2px solid #334155;
            }
            .mc-video-placeholder-inner {
                text-align: center;
                color: #64748b;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
