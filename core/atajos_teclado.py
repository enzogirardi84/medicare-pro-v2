"""Atajos de teclado globales para Medicare Pro."""
import streamlit as st

from core.app_logging import log_event


def inject_atajos_teclado():
    """Inyecta atajos de teclado via JavaScript."""
    st.markdown("""
    <script>
    document.addEventListener('keydown', function(e) {
        // Ctrl+Shift+H = Ir a Historial
        if (e.ctrlKey && e.shiftKey && e.key === 'H') {
            e.preventDefault();
            window.parent.location.href = window.parent.location.pathname + '?modulo=Historial';
        }
        // Ctrl+Shift+D = Ir a Dashboard
        if (e.ctrlKey && e.shiftKey && e.key === 'D') {
            e.preventDefault();
            window.parent.location.href = window.parent.location.pathname + '?modulo=Dashboard';
        }
        // Ctrl+Shift+A = Ir a Admision
        if (e.ctrlKey && e.shiftKey && e.key === 'A') {
            e.preventDefault();
            window.parent.location.href = window.parent.location.pathname + '?modulo=Admision';
        }
        // Ctrl+Shift+E = Ir a Evolucion
        if (e.ctrlKey && e.shiftKey && e.key === 'E') {
            e.preventDefault();
            window.parent.location.href = window.parent.location.pathname + '?modulo=Evolucion';
        }
        // Escape = Cerrar expanders
        if (e.key === 'Escape') {
            var details = document.querySelectorAll('details[open]');
            details.forEach(function(d) { d.removeAttribute('open'); });
        }
    });
    </script>
    """, unsafe_allow_html=True)


def render_ayuda_atajos():
    """Muestra ayuda de atajos de teclado."""
    with st.expander("Atajos de teclado", expanded=False):
        st.markdown("""
        | Atajo | Accion |
        |-------|--------|
        | Ctrl+Shift+H | Ir a Historial |
        | Ctrl+Shift+D | Ir a Dashboard |
        | Ctrl+Shift+A | Ir a Admision |
        | Ctrl+Shift+E | Ir a Evolucion |
        | Escape | Cerrar ventanas |
        """)
