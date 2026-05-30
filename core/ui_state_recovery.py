"""Recuperacion asincrona de estado de formularios via SessionStorage.
Preserva el texto de inputs y text_areas ante cortes de conexion o refrescos.
"""
from __future__ import annotations

import json
import streamlit as st
from core.app_logging import log_event

STORAGE_KEY = "_ui_recovered_state"


def inyectar_state_recovery() -> None:
    """Inyecta JS que persiste el estado de formularios en SessionStorage.

    Escucha eventos input/change en st.text_input, st.text_area,
    st.number_input, st.selectbox, etc. Serializa en SessionStorage
    indexado por usuario.
    """
    st.markdown("""<script>
(function() {
    var USER_ID = 'unknown';
    try {
        // Intentar obtener ID del usuario desde session_state (set via Python)
        USER_ID = document.querySelector('meta[name="mc-user"]')?.content || 'unknown';
    } catch(e) {}

    var STORAGE_KEY = 'mc_form_state_' + USER_ID;

    // ─── Auto-save on input change ─────────────────────
    function saveFormState() {
        try {
            var state = {};
            var inputs = document.querySelectorAll(
                'input[type="text"], input[type="number"], input[type="date"], ' +
                'input[type="time"], textarea, select'
            );
            inputs.forEach(function(el) {
                if (el.id || el.name || el.placeholder) {
                    var key = el.id || el.name || el.placeholder;
                    state[key] = el.value;
                }
            });
            sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
        } catch(e) {}
    }

    // Auto-save cada 2 segundos o en cada cambio
    document.addEventListener('input', saveFormState);
    document.addEventListener('change', saveFormState);
    setInterval(saveFormState, 2000);

    // ─── Restore on load ───────────────────────────────
    try {
        var saved = sessionStorage.getItem(STORAGE_KEY);
        if (saved) {
            var state = JSON.parse(saved);
            Object.keys(state).forEach(function(key) {
                var el = document.getElementById(key) ||
                         document.querySelector('[placeholder="' + key + '"]');
                if (el && !el.value) {
                    el.value = state[key];
                    // Dispatchear evento input para que Streamlit detecte el cambio
                    el.dispatchEvent(new Event('input', { bubbles: true }));
                }
            });
        }
    } catch(e) {}
})();
</script>""", unsafe_allow_html=True)


def set_user_id_meta(usuario: str) -> None:
    """Establece el meta tag con el ID del usuario para SessionStorage."""
    st.markdown(
        f'<meta name="mc-user" content="{usuario}">',
        unsafe_allow_html=True,
    )


def limpiar_estado_recuperado(usuario: str) -> None:
    """Limpia el estado guardado en SessionStorage del usuario.

    Llamar despues de un guardado exitoso.
    """
    st.markdown(f"""<script>
    try {{
        sessionStorage.removeItem('mc_form_state_{usuario}');
    }} catch(e) {{}}
    </script>""", unsafe_allow_html=True)
