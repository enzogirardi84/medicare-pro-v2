# HTML/CSS de la landing pre-login (publicidad). Mantener contenido comercial aca para no inflar main.py.

from core._landing_html_parts import _PART_1, _PART_2, _PART_3, _PART_4, _PART_5, _PART_6, _PART_7


def obtener_html_landing_publicidad(logo_html: str) -> str:
    """Retorna el bloque completo <style> + markup para st.markdown(..., unsafe_allow_html=True)."""
    return (
        _PART_1 + _PART_2 + _PART_3 + _PART_4 + _PART_5 + _PART_6 + _PART_7
    ).replace("__LOGO__", logo_html)
