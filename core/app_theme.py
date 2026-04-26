"""Tema visual global de MediCare PRO.

Inyecta CSS robusto sin depender de selectores data-testid para la navegación
principal. Mantiene compatibilidad visual en PC, tablet y móvil.
"""

import streamlit as st


def aplicar_css_base() -> None:
    """CSS general: fondo oscuro, inputs, métricas y navegación por clases propias."""
    st.markdown(
        """
        <style>
            /* =============================
               BASE VISUAL GENERAL
               ============================= */
            html, body, [data-testid="stAppViewContainer"] {
                background: #0f172a;
            }

            /* Inputs y selectores */
            div[data-testid="stTextInput"] input,
            div[data-baseweb="select"] > div {
                border-radius: 14px !important;
                border: 1px solid rgba(255, 255, 255, 0.10) !important;
                background-color: rgba(255, 255, 255, 0.035) !important;
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

            /* Botones genéricos (no navegación) */
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
                color: white !important;
            }
            div[data-testid="stButton"] > button p,
            div[data-testid="stButton"] > button div,
            div[data-testid="stButton"] > button span {
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

            /* =============================
               NAVEGACIÓN DE MÓDULOS (clases propias)
               ============================= */
            .mc-module-nav-wrap {
                width: 100%;
                margin: 8px 0 26px 0;
            }
            .mc-module-nav-grid {
                display: grid;
                grid-template-columns: repeat(auto-fill, minmax(150px, 150px));
                gap: 10px;
                justify-content: start;
                align-items: stretch;
            }
            .mc-module-card {
                height: 58px;
                padding: 0 13px;
                display: flex;
                align-items: center;
                justify-content: flex-start;
                gap: 8px;
                border-radius: 16px;
                border: 1px solid rgba(148, 163, 184, 0.32);
                background: rgba(15, 23, 42, 0.88);
                color: #ffffff !important;
                text-decoration: none !important;
                box-shadow: 0 4px 10px rgba(0,0,0,0.18);
                transition: all 0.16s ease;
                overflow: hidden;
            }
            .mc-module-card:hover {
                border-color: rgba(56, 189, 248, 0.85);
                background: rgba(30, 41, 59, 0.98);
                transform: translateY(-1px);
                box-shadow: 0 8px 20px rgba(14,165,233,0.14);
            }
            .mc-module-card.active {
                border-color: #38bdf8;
                background: linear-gradient(
                    135deg,
                    rgba(14,165,233,0.30),
                    rgba(15,23,42,0.95)
                );
                box-shadow:
                    0 0 0 1px rgba(56,189,248,0.35),
                    0 8px 22px rgba(14,165,233,0.12);
            }
            .mc-module-icon {
                font-size: 18px;
                line-height: 1;
                flex: 0 0 auto;
            }
            .mc-module-text {
                font-size: 13px;
                font-weight: 650;
                line-height: 1.2;
                white-space: nowrap;
                overflow: hidden;
                text-overflow: ellipsis;
                min-width: 0;
                color: #ffffff !important;
            }
            .mc-module-empty {
                color: rgba(226,232,240,0.75);
                font-size: 0.9rem;
                padding: 8px 0;
            }

            /* =============================
               BOTÓN FLOTANTE PACIENTES
               ============================= */
            #btn-flotante-pacientes {
                position: fixed;
                bottom: 40px;
                left: 0;
                z-index: 999999;
                background: rgba(14, 165, 233, 0.95) !important;
                backdrop-filter: blur(12px);
                -webkit-backdrop-filter: blur(12px);
                color: #ffffff !important;
                padding: 12px 18px 12px 12px;
                border-radius: 0 24px 24px 0;
                font-weight: 700 !important;
                font-size: 15px !important;
                box-shadow: 2px 4px 12px rgba(0,0,0,0.5);
                cursor: pointer;
                border: 1px solid rgba(255,255,255,0.4);
                border-left: none;
                display: none;
            }

            /* =============================
               MÓVIL
               ============================= */
            @media (max-width: 768px) {
                .mc-module-nav-grid {
                    grid-template-columns: repeat(3, minmax(0, 1fr));
                    gap: 8px;
                }
                .mc-module-card {
                    height: 68px;
                    padding: 7px 5px;
                    flex-direction: column;
                    justify-content: center;
                    text-align: center;
                    gap: 5px;
                    border-radius: 15px;
                }
                .mc-module-icon {
                    font-size: 18px;
                }
                .mc-module-text {
                    font-size: 10.5px;
                    max-width: 100%;
                }
                #btn-flotante-pacientes {
                    display: block;
                }
            }
            @media (min-width: 1200px) {
                .mc-module-nav-grid {
                    grid-template-columns: repeat(auto-fill, minmax(158px, 158px));
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
