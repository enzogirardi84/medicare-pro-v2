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
                background-color: #1a1a2e !important;
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
            }
            /* Botón primario (type="primary") - más visible */
            div[data-testid="stButton"] > button[kind="primary"] {
                background: linear-gradient(135deg, #0ea5e9, #2563eb) !important;
                border: none !important;
                font-weight: 600 !important;
                box-shadow: 0 4px 15px rgba(14, 165, 233, 0.35) !important;
            }
            div[data-testid="stButton"] > button[kind="primary"]:hover {
                transform: translateY(-2px) !important;
                box-shadow: 0 8px 25px rgba(14, 165, 233, 0.5) !important;
            }
            /* Botón secundario */
            div[data-testid="stButton"] > button[kind="secondary"] {
                background: rgba(30, 41, 59, 0.8) !important;
                border: 1px solid rgba(100, 120, 140, 0.3) !important;
            }
            /* disabled buttons */
            div[data-testid="stButton"] > button:disabled {
                opacity: 0.5 !important;
                cursor: not-allowed !important;
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

            /* =========================================================
               8. DATA TABLES
               ========================================================= */
            .mc-data-table {
                width: 100%;
                border-collapse: collapse;
                font-size: 0.9rem;
                margin-top: 1rem;
            }
            .mc-data-table th {
                background: rgba(30, 41, 59, 0.8);
                color: #f1f5f9;
                font-weight: 600;
                padding: 0.75rem;
                text-align: left;
                border-bottom: 2px solid rgba(148, 163, 184, 0.2);
                cursor: pointer;
                user-select: none;
                white-space: nowrap;
            }
            .mc-data-table th:hover {
                background: rgba(30, 41, 59, 1);
            }
            .mc-data-table th.sortable::after {
                content: " ⇅";
                opacity: 0.5;
                font-size: 0.75rem;
            }
            .mc-data-table th.sort-asc::after {
                content: " ▲";
                opacity: 1;
                color: #3b82f6;
            }
            .mc-data-table th.sort-desc::after {
                content: " ▼";
                opacity: 1;
                color: #3b82f6;
            }
            .mc-data-table td {
                padding: 0.75rem;
                border-bottom: 1px solid rgba(148, 163, 184, 0.1);
                color: #cbd5e1;
            }
            .mc-data-table tr:hover td {
                background: rgba(30, 41, 59, 0.4);
            }
            .mc-data-table tr.selected td {
                background: rgba(59, 130, 246, 0.15);
            }
            .mc-table-filter {
                background: rgba(15, 23, 42, 0.6);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 8px;
                padding: 1rem;
                margin-bottom: 1rem;
            }
            .mc-pagination {
                display: flex;
                justify-content: center;
                align-items: center;
                gap: 0.5rem;
                margin-top: 1rem;
                padding: 0.75rem;
            }
            .mc-page-btn {
                min-width: 36px;
                height: 36px;
                border-radius: 6px;
                border: 1px solid rgba(148, 163, 184, 0.2);
                background: rgba(15, 23, 42, 0.6);
                color: #94a3b8;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .mc-page-btn:hover {
                background: rgba(30, 41, 59, 0.8);
                color: #f1f5f9;
            }
            .mc-page-btn.active {
                background: #3b82f6;
                color: white;
                border-color: #3b82f6;
            }
            .mc-page-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .mc-table-checkbox {
                width: 18px;
                height: 18px;
                cursor: pointer;
            }

            /* =========================================================
               9. FLOATING ACTION BUTTON (FAB)
               ========================================================= */
            .mc-fab-container {
                position: fixed;
                z-index: 999998;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 0.75rem;
            }
            .mc-fab-main {
                width: 56px;
                height: 56px;
                border-radius: 50%;
                border: none;
                cursor: pointer;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.5rem;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
                transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
                position: relative;
                overflow: hidden;
            }
            .mc-fab-main:hover {
                transform: scale(1.1);
                box-shadow: 0 6px 30px rgba(0, 0, 0, 0.4);
            }
            .mc-fab-main:active {
                transform: scale(0.95);
            }
            .mc-fab-main.open {
                transform: rotate(45deg);
            }
            .mc-fab-main::before {
                content: "";
                position: absolute;
                inset: 0;
                background: linear-gradient(135deg, rgba(255,255,255,0.2) 0%, transparent 50%);
                border-radius: 50%;
            }
            .mc-fab-actions {
                display: flex;
                flex-direction: column-reverse;
                gap: 0.75rem;
                margin-bottom: 0.5rem;
                animation: fab-actions-in 0.3s ease-out;
            }
            @keyframes fab-actions-in {
                from { opacity: 0; transform: translateY(20px); }
                to { opacity: 1; transform: translateY(0); }
            }
            .mc-fab-action {
                display: flex;
                align-items: center;
                gap: 0.75rem;
                cursor: pointer;
                transition: all 0.2s ease;
            }
            .mc-fab-action:hover {
                transform: translateX(-5px);
            }
            .mc-fab-action-btn {
                width: 48px;
                height: 48px;
                border-radius: 50%;
                border: none;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.25rem;
                box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
                transition: all 0.2s ease;
                position: relative;
            }
            .mc-fab-action-btn:hover {
                transform: scale(1.1);
            }
            .mc-fab-action-btn:disabled {
                opacity: 0.5;
                cursor: not-allowed;
            }
            .mc-fab-action-label {
                background: rgba(15, 23, 42, 0.9);
                color: #f1f5f9;
                padding: 0.5rem 0.75rem;
                border-radius: 6px;
                font-size: 0.875rem;
                white-space: nowrap;
                backdrop-filter: blur(8px);
                border: 1px solid rgba(148, 163, 184, 0.2);
                box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
            }
            .mc-fab-badge {
                position: absolute;
                top: -4px;
                right: -4px;
                background: #ef4444;
                color: white;
                font-size: 0.65rem;
                font-weight: 600;
                min-width: 18px;
                height: 18px;
                border-radius: 50%;
                display: flex;
                align-items: center;
                justify-content: center;
                border: 2px solid #0f172a;
                box-shadow: 0 2px 4px rgba(0, 0, 0, 0.2);
            }
            .mc-fab-overlay {
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(2, 6, 23, 0.5);
                z-index: 999997;
                backdrop-filter: blur(2px);
            }
            .mc-fab-ripple {
                position: absolute;
                border-radius: 50%;
                background: rgba(255, 255, 255, 0.4);
                transform: scale(0);
                animation: ripple 0.6s linear;
                pointer-events: none;
            }
            @keyframes ripple {
                to { transform: scale(4); opacity: 0; }
            }
            @media (max-width: 768px) {
                .mc-fab-container {
                    bottom: 1rem !important;
                    right: 1rem !important;
                    left: auto !important;
                    transform: none !important;
                }
                .mc-fab-main {
                    width: 48px;
                    height: 48px;
                    font-size: 1.25rem;
                }
                .mc-fab-action-btn {
                    width: 40px;
                    height: 40px;
                    font-size: 1rem;
                }
                .mc-fab-action-label {
                    display: none;
                }
            }
            .mc-quick-actions-bar {
                display: flex;
                gap: 0.5rem;
                padding: 0.75rem;
                background: rgba(30, 41, 59, 0.8);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 12px;
                backdrop-filter: blur(8px);
                position: sticky;
                bottom: 1rem;
                z-index: 99999;
                margin-top: 2rem;
                justify-content: center;
                flex-wrap: wrap;
            }
            .mc-quick-action-btn {
                display: flex;
                align-items: center;
                gap: 0.5rem;
                padding: 0.625rem 1rem;
                border-radius: 8px;
                border: 1px solid transparent;
                cursor: pointer;
                transition: all 0.2s ease;
                font-size: 0.9rem;
                font-weight: 500;
            }
            .mc-quick-action-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            }
            @media (max-width: 768px) {
                .mc-quick-actions-bar {
                    gap: 0.375rem;
                    padding: 0.5rem;
                }
                .mc-quick-action-btn {
                    padding: 0.5rem 0.75rem;
                    font-size: 0.8rem;
                }
                .mc-quick-action-btn span {
                    display: none;
                }
            }

            /* =========================================================
               10. AUTH OVERLAY / LOGIN LOADER
               ========================================================= */
            .mc-auth-overlay {
                position: fixed;
                inset: 0;
                background: rgba(3,6,15,0.82);
                backdrop-filter: blur(10px);
                -webkit-backdrop-filter: blur(10px);
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                z-index: 9999999;
                gap: 16px;
                padding: 1rem;
                text-align: center;
                animation: mc-auth-fadeout 0.4s ease 4s forwards;
            }
            .mc-auth-spinner {
                display: block;
                flex: 0 0 auto;
                width: 46px;
                height: 46px;
                border: 3px solid rgba(255,255,255,0.08);
                border-left-color: #14b8a6;
                border-top-color: #60a5fa;
                border-radius: 50%;
                animation: mc-auth-spin 0.9s linear infinite;
                -webkit-animation: mc-auth-spin 0.9s linear infinite;
                transform-origin: center center;
                will-change: transform;
                backface-visibility: hidden;
                -webkit-backface-visibility: hidden;
            }
            .mc-auth-title {
                color: #f1f5f9;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 18px;
                font-weight: 700;
                letter-spacing: 0.2px;
                margin: 0;
            }
            .mc-auth-sub {
                color: #94a3b8;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
                font-size: 13px;
                font-weight: 500;
                letter-spacing: 0.25px;
                margin: 0;
            }
            @keyframes mc-auth-spin {
                to { transform: rotate(360deg); }
            }
            @-webkit-keyframes mc-auth-spin {
                to { transform: rotate(360deg); }
            }
            @keyframes mc-auth-fadeout {
                from { opacity: 1; }
                to { opacity: 0; pointer-events: none; visibility: hidden; }
            }
            @media (max-width: 767px) {
                .mc-auth-overlay {
                    gap: 14px;
                    padding: 0.9rem;
                    background: rgba(3,6,15,0.9);
                }
                .mc-auth-spinner {
                    width: 42px;
                    height: 42px;
                }
                .mc-auth-title {
                    font-size: 16px;
                }
                .mc-auth-sub {
                    font-size: 12px;
                }
            }

            /* =========================================================
    @supports selector(:has(*)) {
               11. NAVIGATION BUTTONS (desktop grid)
               ========================================================= */
            div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(4)) button[kind="secondary"],
            div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(4)) button[kind="primary"] {
                background-color: #1e293b !important;
                border: 1px solid rgba(255,255,255,0.15) !important;
                border-radius: 14px !important;
                transition: all 0.2s ease !important;
                height: 52px !important;
            }
            div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(4)) button[kind="secondary"] p,
            div[data-testid="stHorizontalBlock"]:has(> div[data-testid="column"]:nth-child(4)) button[kind="primary"] p {
                color: #ffffff !important;
                white-space: nowrap !important;
                overflow: hidden !important;
                text-overflow: ellipsis !important;
            }
    } /* end @supports :has() */
            /* Solo ocultar boton colapsar sidebar en desktop; en mobile debe ser visible */
            @media (min-width: 769px) {
                [data-testid="stSidebar"] [aria-label="Collapse sidebar"],
                [data-testid="stSidebar"] button[kind="headerNoPadding"] {
                    display: none !important;
                }
            }

            /* =========================================================
               12. COMMAND PALETTE OVERLAY
               ========================================================= */
            .cmd-palette-overlay {
                position: fixed;
                top: 0; left: 0; right: 0; bottom: 0;
                background: rgba(2, 6, 23, 0.8);
                backdrop-filter: blur(4px);
                z-index: 999999;
                display: flex;
                align-items: flex-start;
                justify-content: center;
                padding-top: 15vh;
            }
            .cmd-palette-container {
                background: linear-gradient(135deg, rgba(30, 41, 59, 0.95) 0%, rgba(15, 23, 42, 0.98) 100%);
                border: 1px solid rgba(148, 163, 184, 0.2);
                border-radius: 12px;
                width: 100%;
                max-width: 600px;
                max-height: 60vh;
                overflow: hidden;
                box-shadow: 0 25px 50px rgba(2, 6, 23, 0.5);
            }
            .cmd-palette-input {
                width: 100%;
                padding: 1rem 1.25rem;
                background: transparent;
                border: none;
                border-bottom: 1px solid rgba(148, 163, 184, 0.2);
                color: #f1f5f9;
                font-size: 1.1rem;
                outline: none;
            }
            .cmd-palette-input::placeholder { color: #64748b; }
            .cmd-palette-list {
                max-height: calc(60vh - 80px);
                overflow-y: auto;
            }
            .cmd-palette-item {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 0.75rem 1.25rem;
                cursor: pointer;
                transition: all 0.15s ease;
                border-left: 3px solid transparent;
            }
            .cmd-palette-item:hover, .cmd-palette-item.selected {
                background: rgba(59, 130, 246, 0.1);
                border-left-color: #3b82f6;
            }
            .cmd-palette-item-title { color: #f1f5f9; font-size: 0.95rem; }
            .cmd-palette-item-desc { color: #64748b; font-size: 0.8rem; margin-top: 0.125rem; }
            .cmd-palette-shortcut { display: flex; align-items: center; gap: 0.375rem; }
            .cmd-palette-kbd {
                background: rgba(15, 23, 42, 0.8);
                border: 1px solid rgba(148, 163, 184, 0.3);
                border-radius: 4px;
                padding: 0.25rem 0.5rem;
                font-family: monospace;
                font-size: 0.75rem;
                color: #94a3b8;
            }

            /* =========================================================
               13. PATIENT ALERT PULSE (red critical)
               ========================================================= */
            @keyframes mc-pulse-red {
                0%, 100% { box-shadow: 0 0 0 1px rgba(248,113,113,0.35), 0 8px 24px rgba(0,0,0,0.35); }
                50%   { box-shadow: 0 0 0 3px rgba(248,113,113,0.55), 0 10px 28px rgba(220,38,38,0.25); }
            }

            /* =========================================================
               14. METRIC LABELS — evitar truncamiento de texto
               ========================================================= */
            [data-testid="stMetricLabel"] {
                white-space: normal !important;
                overflow: visible !important;
                text-overflow: initial !important;
                word-wrap: break-word !important;
                font-size: 0.85rem !important;
                line-height: 1.2 !important;
                min-height: auto !important;
            }
            [data-testid="stMetricLabel"] > div {
                overflow: visible !important;
            }

            /* =========================================================
               15. OPTIMIZACIÓN DE CARGA - Progressive loading
               ========================================================= */
            .stApp {
                opacity: 1;
                transition: opacity 0.2s ease-in-out;
            }
            /* Skeleton loading para tablas */
            .stDataFrame {
                animation: mc-fade-in 0.3s ease-in;
            }
            @keyframes mc-fade-in {
                from { opacity: 0.7; }
                to { opacity: 1; }
            }
            /* Botones más responsivos */
            .stButton > button {
                cursor: pointer;
                transition: all 0.15s ease;
            }
            .stButton > button:active {
                transform: scale(0.97);
            }
            /* Sidebar más fluida */
            [data-testid="stSidebar"] {
                transition: width 0.2s ease;
            }
            /* Spinner más visible */
            .stSpinner {
                min-height: 60px;
            }

            /* =========================================================
               16. TEMA PROFESIONAL V2 - Glassmorphism + Diseño moderno
               ========================================================= */
            /* Fondo con sutiles gradientes */
            .stApp {
                background: linear-gradient(135deg, #0f0c29 0%, #1a1a3e 50%, #16213e 100%) !important;
            }
            
            /* Tarjetas con efecto glassmorphism */
            div[data-testid="stForm"], 
            div[data-testid="stMetric"],
            div[data-testid="stDataFrame"],
            div[data-testid="stTable"],
            div.stAlert {
                background: rgba(255, 255, 255, 0.03) !important;
                backdrop-filter: blur(10px) !important;
                -webkit-backdrop-filter: blur(10px) !important;
                border: 1px solid rgba(255, 255, 255, 0.06) !important;
                border-radius: 16px !important;
                box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2) !important;
            }
            
            /* Metric hover effect */
            div[data-testid="stMetric"]:hover {
                transform: translateY(-2px) !important;
                border-color: rgba(14, 165, 233, 0.2) !important;
                box-shadow: 0 12px 40px rgba(14, 165, 233, 0.1) !important;
            }
            
            /* Sidebar mejorado */
            [data-testid="stSidebar"] {
                background: linear-gradient(180deg, rgba(15, 12, 41, 0.95) 0%, rgba(26, 26, 62, 0.98) 100%) !important;
                border-right: 1px solid rgba(255, 255, 255, 0.05) !important;
            }
            
            /* Cards del modulo grid */
            div[data-testid="column"] > div[data-testid="stButton"] > button {
                border-radius: 14px !important;
                border: 1px solid rgba(255, 255, 255, 0.06) !important;
                background: rgba(255, 255, 255, 0.03) !important;
                transition: all 0.25s ease !important;
                min-height: 48px !important;
            }
            div[data-testid="column"] > div[data-testid="stButton"] > button:hover {
                transform: translateY(-3px) !important;
                border-color: rgba(14, 165, 233, 0.3) !important;
                box-shadow: 0 8px 25px rgba(14, 165, 233, 0.15) !important;
                background: rgba(14, 165, 233, 0.08) !important;
            }
            
            /* Tabs elegantes */
            [data-testid="stTabs"] [role="tab"] {
                border-radius: 10px 10px 0 0 !important;
                padding: 8px 20px !important;
                transition: all 0.2s ease !important;
            }
            [data-testid="stTabs"] [role="tab"][aria-selected="true"] {
                background: rgba(14, 165, 233, 0.1) !important;
                border-bottom: 2px solid #0ea5e9 !important;
            }
            
            /* Headers con gradiente */
            h1, h2, h3, h4 {
                background: linear-gradient(135deg, #fff 0%, #94a3b8 100%) !important;
                -webkit-background-clip: text !important;
                -webkit-text-fill-color: transparent !important;
                background-clip: text !important;
                font-weight: 700 !important;
            }
            
            /* Metric values con color accent */
            [data-testid="stMetricValue"] {
                background: linear-gradient(135deg, #0ea5e9, #38bdf8) !important;
                -webkit-background-clip: text !important;
                -webkit-text-fill-color: transparent !important;
                font-weight: 800 !important;
                font-size: clamp(1.3rem, 2vw, 2rem) !important;
            }
            
            /* DataFrames con bordes redondeados */
            .stDataFrame {
                border-radius: 12px !important;
                overflow: hidden !important;
            }
            
            /* Scrollbar elegante */
            ::-webkit-scrollbar {
                width: 6px !important;
                height: 6px !important;
            }
            ::-webkit-scrollbar-track {
                background: rgba(255, 255, 255, 0.02) !important;
            }
            ::-webkit-scrollbar-thumb {
                background: rgba(14, 165, 233, 0.3) !important;
                border-radius: 10px !important;
            }
            ::-webkit-scrollbar-thumb:hover {
                background: rgba(14, 165, 233, 0.5) !important;
            }
            
            /* Botones primarios con glow */
            button[kind="primary"] {
                box-shadow: 0 0 20px rgba(14, 165, 233, 0.15) !important;
            }
            button[kind="primary"]:hover {
                box-shadow: 0 0 30px rgba(14, 165, 233, 0.3) !important;
            }
            
            /* Expanders con estilo */
            .streamlit-expanderHeader {
                border-radius: 12px !important;
                background: rgba(255, 255, 255, 0.02) !important;
            }
            
            /* Loading spinner premium */
            .stSpinner > div > div {
                border-width: 3px !important;
                border-color: rgba(14, 165, 233, 0.1) !important;
                border-top-color: #0ea5e9 !important;
            }

            /* =========================================================
               17. MODULO NAV - Tarjetas premium responsivas
               ========================================================= */
            /* Contenedor de botones del modulo nav */
            div[data-testid="column"] > div[data-testid="stButton"] {
                width: 100% !important;
            }
            div[data-testid="column"] > div[data-testid="stButton"] > button {
                width: 100% !important;
                min-height: 52px !important;
                border-radius: 14px !important;
                font-size: 0.9rem !important;
                font-weight: 500 !important;
                transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
                border: 1px solid rgba(255, 255, 255, 0.06) !important;
                background: rgba(255, 255, 255, 0.03) !important;
                backdrop-filter: blur(4px) !important;
                letter-spacing: 0.3px !important;
            }
            div[data-testid="column"] > div[data-testid="stButton"] > button:hover {
                transform: translateY(-4px) !important;
                border-color: rgba(14, 165, 233, 0.35) !important;
                box-shadow: 0 12px 28px rgba(14, 165, 233, 0.15) !important;
                background: rgba(14, 165, 233, 0.08) !important;
            }
            div[data-testid="column"] > div[data-testid="stButton"] > button:active {
                transform: translateY(-1px) !important;
            }
            /* Boton activo */
            div[data-testid="column"] > div[data-testid="stButton"] > button[kind="primary"] {
                background: linear-gradient(135deg, rgba(14, 165, 233, 0.2), rgba(37, 99, 235, 0.2)) !important;
                border-color: rgba(14, 165, 233, 0.4) !important;
                box-shadow: 0 0 20px rgba(14, 165, 233, 0.1) !important;
            }
            div[data-testid="column"] > div[data-testid="stButton"] > button[kind="primary"]:hover {
                box-shadow: 0 0 30px rgba(14, 165, 233, 0.25) !important;
            }

            /* =========================================================
               18. SKELETON LOADING - shimmer effect
               ========================================================= */
            @keyframes mc-shimmer {
                0% { background-position: -200% 0; }
                100% { background-position: 200% 0; }
            }
            .mc-skeleton {
                background: linear-gradient(90deg, rgba(255,255,255,0.02) 25%, rgba(255,255,255,0.06) 50%, rgba(255,255,255,0.02) 75%) !important;
                background-size: 200% 100% !important;
                animation: mc-shimmer 1.5s ease-in-out infinite !important;
                border-radius: 8px !important;
                min-height: 20px !important;
            }

            /* Block container spacing */
            .block-container {
                max-width: 1480px !important;
                padding-top: 0.9rem !important;
                padding-bottom: 1.25rem !important;
            }
            div[data-testid="stHorizontalBlock"] {
                gap: 0.65rem !important;
            }
            @media (max-width: 768px) {
                .block-container {
                    padding-left: 0.85rem !important;
                    padding-right: 0.85rem !important;
                }
                [data-testid="column"] {
                    min-width: min(100%, 240px) !important;
                }
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
