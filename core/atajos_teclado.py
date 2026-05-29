"""Atajos de teclado globales para Medicare Pro."""

from __future__ import annotations

import streamlit as st


def inject_atajos_teclado():
    """Atajos de teclado: st.markdown no ejecuta <script>, se deja la ayuda visible."""
    pass


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
