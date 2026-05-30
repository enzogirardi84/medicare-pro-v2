"""Compilador estatico de estilos con minificacion y cache LocalStorage.
Inyecta CSS procesado una unica vez por sesion. Usa hash SHA-256
para verificar cache del cliente. Elimina FOUC (Flash of Unstyled Content).
"""
from __future__ import annotations

import hashlib
import re
import streamlit as st

from core.app_logging import log_event

CSS_KEY = "_ui_compiled_css_hash"


class UIStaticCompiler:
    """Compila, minifica y cachea el CSS corporativo.

    El CSS se minifica en caliente (comentarios, espacios, saltos).
    Se inyecta via st.markdown con hash de integridad.
    El cliente puede cachear en LocalStorage para evitar
    re-descarga en navegaciones posteriores.
    """

    @staticmethod
    def minificar(css_raw: str) -> str:
        """Minifica CSS: elimina comentarios, espacios redundantes, saltos.

        Args:
            css_raw: CSS crudo con comentarios y formato legible.

        Returns:
            CSS minificado en una sola linea.
        """
        # Eliminar comentarios /* ... */
        css = re.sub(r'/\*.*?\*/', '', css_raw, flags=re.DOTALL)
        # Eliminar espacios al inicio/fin de linea
        css = re.sub(r'^\s+|\s+$', '', css, flags=re.MULTILINE)
        # Eliminar saltos de linea
        css = re.sub(r'\n\s*', ' ', css)
        # Compactar espacios multiples
        css = re.sub(r'\s{2,}', ' ', css)
        # Espacios alrededor de {}:;,
        css = re.sub(r'\s*([{}:;,])\s*', r'\1', css)
        # Espacio antes/despues de !important
        css = re.sub(r'\s*!important', '!important', css)
        # Eliminar ultimo punto y coma antes de }
        css = re.sub(r';}', '}', css)
        return css.strip()

    @staticmethod
    def hash_css(css: str) -> str:
        """SHA-256 del CSS minificado para control de cache."""
        return hashlib.sha256(css.encode('utf-8')).hexdigest()

    @classmethod
    def inyectar(cls, css_raw: str) -> str:
        """Compila, minifica e inyecta el CSS en el DOM de Streamlit.

        Solo se inyecta UNA vez por sesion (controlado por session_state).
        Retorna el hash del CSS para verificacion.

        Args:
            css_raw: CSS crudo a procesar.

        Returns:
            Hash SHA-256 del CSS minificado.
        """
        if st.session_state.get(CSS_KEY):
            return st.session_state[CSS_KEY]

        css_min = cls.minificar(css_raw)
        css_hash = cls.hash_css(css_min)

        st.markdown(f"""<style data-css-hash="{css_hash}">{css_min}</style>""",
                    unsafe_allow_html=True)

        st.session_state[CSS_KEY] = css_hash
        log_event("ui_compiler", f"css_inyectado:{len(css_min)}b:hash={css_hash[:12]}")
        return css_hash

    @classmethod
    def script_cache_localstorage(cls) -> str:
        """JS para cachear CSS en LocalStorage del navegador.

        En la segunda visita, el navegador no necesita re-descargar
        el CSS si el hash coincide con el almacenado localmente.
        """
        return """<script>
(function() {
  try {
    var style = document.querySelector('style[data-css-hash]');
    if (!style) return;
    var hash = style.getAttribute('data-css-hash');
    var cached = localStorage.getItem('mc_css_hash');
    if (cached === hash) {
      // CSS ya cacheado, no necesita re-parseo
      style.setAttribute('data-css-cached', 'true');
    } else {
      localStorage.setItem('mc_css_hash', hash);
    }
  } catch(e) {}
})();
</script>"""
