"""Atajos de teclado globales para Medicare Pro."""

from __future__ import annotations

import streamlit as st


def inject_atajos_teclado():
    """Inyecta atajos de teclado via st.html() (si ejecuta <script> en Streamlit 1.35+)."""
    if st.session_state.get("_atajos_injected"):
        return
    st.session_state["_atajos_injected"] = True
    st.html("""<span style="display:none"></span>
<script>
document.addEventListener('keydown', function(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA' || e.target.isContentEditable) {
        if (!(e.ctrlKey && e.key === 'g')) return;
    }
    function qp(key, value) {
        var url = new URL(window.location.href);
        url.searchParams.set(key, value);
        window.location.href = url.toString();
    }
    if (e.ctrlKey && !e.shiftKey && e.key === 'e') { e.preventDefault(); qp('modulo', 'Evolucion'); }
    if (e.ctrlKey && !e.shiftKey && e.key === 'r') { e.preventDefault(); qp('modulo', 'Recetas'); }
    if (e.ctrlKey && !e.shiftKey && e.key === 'd') { e.preventDefault(); qp('modulo', 'Dashboard'); }
    if (e.ctrlKey && !e.shiftKey && e.key === 'f') { e.preventDefault(); qp('modulo', 'Buscar'); }
});
</script>""")


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
