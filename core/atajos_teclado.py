"""Atajos de teclado globales para Medicare Pro."""

from __future__ import annotations

import streamlit as st


def inject_atajos_teclado():
    """Inyecta atajos de teclado via JavaScript (1 vez por sesion)."""
    if st.session_state.get("_atajos_injected"):
        return
    st.session_state["_atajos_injected"] = True
    st.markdown("""
    <script>
    document.addEventListener('keydown', function(e) {
        // Skip if typing in an input/textarea
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {
            // Allow Ctrl+G even in inputs (save)
            if (!(e.ctrlKey && e.key === 'g')) return;
        }
        // Ctrl+E = Evolucion
        if (e.ctrlKey && !e.shiftKey && e.key === 'e') {
            e.preventDefault();
            window.parent.location.href = updateQueryParam('modulo', 'Evolucion');
        }
        // Ctrl+R = Recetas
        if (e.ctrlKey && !e.shiftKey && e.key === 'r') {
            e.preventDefault();
            window.parent.location.href = updateQueryParam('modulo', 'Recetas');
        }
        // Ctrl+G = Guardar
        if (e.ctrlKey && !e.shiftKey && e.key === 'g') {
            e.preventDefault();
            // Click the first save button found
            var btns = document.querySelectorAll('button[kind="primary"]');
            for (var i = 0; i < btns.length; i++) {
                if (btns[i].textContent.includes('Guardar') || btns[i].textContent.includes('guardar')) {
                    btns[i].click();
                    break;
                }
            }
        }
        // Ctrl+D = Dashboard
        if (e.ctrlKey && !e.shiftKey && e.key === 'd') {
            e.preventDefault();
            window.parent.location.href = updateQueryParam('modulo', 'Dashboard');
        }
        // Ctrl+F = Focus search
        if (e.ctrlKey && !e.shiftKey && e.key === 'f') {
            e.preventDefault();
            var searchInput = document.querySelector('input[placeholder*="paciente" i]');
            if (searchInput) searchInput.focus();
        }
        function updateQueryParam(key, value) {
            var url = new URL(window.parent.location.href);
            url.searchParams.set(key, value);
            return url.toString();
        }
    });
    </script>
    """, unsafe_allow_html=True)


def render_ayuda_atajos():
    """Muestra ayuda de atajos de teclado."""
    with st.expander("Atajos de teclado", expanded=False):
        st.markdown("""
        | Atajo | Acción |
        |-------|--------|
        | Ctrl+E | Ir a Evolución |
        | Ctrl+R | Ir a Recetas |
        | Ctrl+G | Guardar cambios |
        | Ctrl+D | Ir a Dashboard |
        | Ctrl+F | Buscar paciente |
        | Escape | Cerrar ventanas |
        """)
