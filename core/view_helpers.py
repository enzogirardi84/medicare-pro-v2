"""Utilidades de UI compartidas entre vistas Streamlit (mensajes, bloques de ayuda)."""

from contextlib import contextmanager
from html import escape
from typing import Iterator, Optional

import streamlit as st


@contextmanager
def lista_plegable(
    titulo: str,
    *,
    count: Optional[int] = None,
    expanded: bool = False,
    height: Optional[int] = 360,
) -> Iterator[None]:
    """
    Lista o bloque largo dentro de un expander; opcionalmente con contenedor con scroll vertical.
    Reduce altura de página y DOM cuando está plegado (mejor rendimiento en el navegador).

    - ``height=None``: solo expander, sin contenedor de altura fija (útil si adentro hay gráficos o varios scrolls).
    - ``height>0``: ``st.container(height=...)`` interno con barra de desplazamiento.
    """
    etiqueta = f"{titulo} ({count})" if count is not None else titulo
    with st.expander(etiqueta, expanded=expanded):
        if height is not None and height > 0:
            with st.container(height=height, border=True):
                yield
        else:
            yield


def aviso_sin_paciente() -> None:
    st.warning(
        "Necesitás un **paciente activo** para usar esta vista. "
        "En el panel izquierdo, elegí un paciente en el selector (o cargá uno en **Admisión** si todavía no está en la lista)."
    )


def bloque_estado_vacio(
    titulo: str,
    mensaje: str,
    *,
    sugerencia: Optional[str] = None,
    compact: bool = True,
) -> None:
    """
    Estado vacío unificado (sin datos / sin resultados). Texto escapado; sin Markdown en mensaje.
    Por defecto usa modo compacto (menos padding, tipografía más chica). Pasá compact=False para el bloque amplio.
    """
    sug = ""
    if sugerencia:
        sug = f"<p class='mc-empty-sug'>{escape(str(sugerencia))}</p>"
    mod = "mc-empty-state--compact" if compact else "mc-empty-state--relaxed"
    st.markdown(
        f"""
        <div class="mc-empty-state {mod}" role="status">
            <span class="mc-empty-icon" aria-hidden="true">&#9432;</span>
            <div class="mc-empty-body">
                <h4 class="mc-empty-title">{escape(str(titulo))}</h4>
                <p class="mc-empty-text">{escape(str(mensaje))}</p>
                {sug}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def aviso_registro_clinico_legal() -> None:
    """Aviso breve para vistas con datos sensibles o exportación legal."""
    st.caption(
        "Los datos clínicos son confidenciales. Registrá solo información necesaria para la atención "
        "y respetá las políticas de tu institución y la normativa aplicable."
    )


def bloque_mc_grid_tarjetas(items):
    """
    Renderiza una fila de tarjetas .mc-card dentro de .mc-grid-3.
    items: lista de (titulo, descripcion), hasta 6 pares.
    """
    if not items:
        return
    cards = []
    for titulo, descripcion in items[:6]:
        cards.append(
            f'<div class="mc-card"><h4>{escape(str(titulo))}</h4><p>{escape(str(descripcion))}</p></div>'
        )
    st.markdown(f'<div class="mc-grid-3">{"".join(cards)}</div>', unsafe_allow_html=True)
