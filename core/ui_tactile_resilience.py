"""Protocolo de interaccion tactil resiliente para entornos de alta vibracion.
Optimizado para ambulancias en movimiento, guantes de latex y
pantallas tactiles con precision motriz reducida.

Caracteristicas:
- Hitbox expandido: 16px de padding invisible en checkboxes, radios, selects
- Debounce tactil: 800ms en botones criticos (Firmar, Guardar, Emergencia)
- Anti-fatiga: previene dobles clicks accidentales
"""
from __future__ import annotations

import streamlit as st


def inyectar_protocolo_tactil() -> None:
    """Inyecta CSS + JS para resiliencia tactil en entornos de alta friccion.

    Debe llamarse UNA vez al inicio de la sesion.
    """
    st.markdown("""<style>
    /* ════════════════════════════════════════════════════════
       HITBOX EXPANDIDO (paddings invisibles perimetrales)
       ════════════════════════════════════════════════════════ */

    /* Checkboxes: area tactil 44x44 minima */
    [data-testid="stCheckbox"] label {
        min-height: 44px !important;
        padding: 14px 0 !important;
        display: flex !important;
        align-items: center !important;
    }
    [data-testid="stCheckbox"] label input {
        width: 24px !important;
        height: 24px !important;
        min-width: 24px !important;
    }

    /* Radio buttons */
    [data-testid="stRadio"] label {
        min-height: 48px !important;
        padding: 14px 12px !important;
        display: flex !important;
        align-items: center !important;
    }
    [data-testid="stRadio"] label input {
        width: 24px !important;
        height: 24px !important;
    }

    /* Selectores (dropdowns) */
    [data-baseweb="select"] > div {
        min-height: 52px !important;
        padding: 0 16px !important;
    }

    /* Inputs genericos */
    [data-testid="stTextInput"] input,
    [data-testid="stNumberInput"] input,
    [data-testid="stDateInput"] input,
    [data-testid="stTimeInput"] input {
        min-height: 48px !important;
        padding: 4px 14px !important;
    }

    /* Sliders */
    [data-testid="stSlider"] [role="slider"] {
        width: 32px !important;
        height: 32px !important;
        min-width: 32px !important;
        min-height: 32px !important;
    }

    /* Tabs */
    [data-testid="stTabs"] [role="tab"] {
        min-height: 48px !important;
        padding: 8px 20px !important;
    }

    /* Botones en general */
    [data-testid="stButton"] button,
    [data-testid="stFormSubmitButton"] button {
        min-height: 48px !important;
        padding: 0 24px !important;
    }

    /* ════════════════════════════════════════════════════════
       DEBOUNCE TACTIL (via CSS pointer-events + JS)
       ════════════════════════════════════════════════════════ */

    .mc-debounce-active {
        pointer-events: none !important;
        opacity: 0.7 !important;
        transition: opacity 0.3s ease !important;
    }

    /* Botones de accion critica con clase .mc-critical */
    [data-testid="stButton"] button.mc-critical:active {
        transform: scale(0.96) !important;
    }
    </style>

    <script>
    /* ─── Debounce tactil global (800ms) ─────────────────── */
    (function() {
        var DEBOUNCE_MS = 800;
        var debounceTimers = {};

        function isCriticalButton(el) {
            // Botones de acciones criticas: Firmar, Guardar, Emergencia, Despachar
            if (!el || !el.tagName) return false;
            var text = (el.textContent || el.innerText || '').toLowerCase();
            return text.indexOf('firmar') !== -1 ||
                   text.indexOf('guardar') !== -1 ||
                   text.indexOf('emergencia') !== -1 ||
                   text.indexOf('despachar') !== -1 ||
                   text.indexOf('enviar') !== -1 ||
                   text.indexOf('confirmar') !== -1;
        }

        document.addEventListener('click', function(e) {
            var btn = e.target.closest('button');
            if (!btn) return;

            if (isCriticalButton(btn)) {
                var key = btn.getAttribute('data-testid') || btn.id || btn.className || 'unknown';

                if (debounceTimers[key]) {
                    // Click dentro de la ventana de debounce: bloquear
                    e.preventDefault();
                    e.stopPropagation();
                    btn.classList.add('mc-debounce-active');
                    return;
                }

                // Primer click: permitir, iniciar timer
                btn.classList.remove('mc-debounce-active');
                debounceTimers[key] = setTimeout(function() {
                    delete debounceTimers[key];
                    btn.classList.remove('mc-debounce-active');
                }, DEBOUNCE_MS);
            }
        }, true);

        // Prevenir doble submit en formularios
        document.addEventListener('submit', function(e) {
            var form = e.target;
            var submitBtn = form.querySelector('button[type="submit"]');
            if (submitBtn && isCriticalButton(submitBtn)) {
                if (submitBtn.getAttribute('data-mc-submitted')) {
                    e.preventDefault();
                    return;
                }
                submitBtn.setAttribute('data-mc-submitted', 'true');
                setTimeout(function() {
                    submitBtn.removeAttribute('data-mc-submitted');
                }, DEBOUNCE_MS);
            }
        }, true);
    })();
    </script>
    """, unsafe_allow_html=True)
