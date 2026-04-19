"""Utilidades de UI compartidas entre vistas Streamlit (mensajes, bloques de ayuda)."""

from contextlib import contextmanager
from html import escape
import re
from typing import Iterator, Optional

import streamlit as st
import streamlit.components.v1 as components


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


_VISTAS_COMPACTAS_MOVIL = {
    "Admision",
    "Clinica",
    "Pediatria",
    "Evolucion",
    "Estudios",
    "Materiales",
    "Recetas",
    "Balance",
    "Inventario",
    "Caja",
    "Emergencias y Ambulancia",
    "Alertas app paciente",
    "Red de Profesionales",
    "Escalas Clinicas",
    "Historial",
    "PDF",
    "Telemedicina",
    "Cierre Diario",
    "Mi Equipo",
    "Asistencia en Vivo",
    "RRHH y Fichajes",
    "Proyecto y Roadmap",
    "Auditoria",
    "Auditoria Legal",
    "Diagnosticos",
}


def _slug_vista(nombre_vista: str) -> str:
    base = re.sub(r"[^a-z0-9]+", "-", str(nombre_vista or "").strip().lower())
    return base.strip("-") or "sin-vista"


def aplicar_compactacion_movil_por_vista(nombre_vista: str) -> None:
    """
    Compacta spacing y contenedores en vistas clínicas/operativas pesadas.
    Se activa solo en móvil y limpia la clase cuando el usuario sale de esas vistas.
    """
    from core.ui_liviano import headers_sugieren_equipo_liviano

    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
    habilitar = es_movil and nombre_vista in _VISTAS_COMPACTAS_MOVIL
    vista_slug = _slug_vista(nombre_vista)

    st.markdown(
        """
        <style>
        @media (max-width: 767px) {
            html.mc-view-compact .mc-hero {
                padding: 0.78rem 0.86rem !important;
                margin: 0 0 0.5rem !important;
                border-radius: 18px !important;
            }
            html.mc-view-compact .mc-hero-title {
                margin: 0 0 0.14rem !important;
                font-size: 1.16rem !important;
                line-height: 1.08 !important;
            }
            html.mc-view-compact .mc-hero-text {
                margin: 0 !important;
                font-size: 0.77rem !important;
                line-height: 1.4 !important;
            }
            html.mc-view-compact .mc-chip-row {
                gap: 0.32rem !important;
                margin-top: 0.42rem !important;
            }
            html.mc-view-compact .mc-chip {
                padding: 0.28rem 0.5rem !important;
                font-size: 0.65rem !important;
            }
            html.mc-view-compact .mc-grid-3 {
                gap: 0.42rem !important;
                margin: 0.2rem 0 0.55rem !important;
            }
            html.mc-view-compact .mc-card {
                padding: 0.72rem 0.78rem !important;
                min-height: 0 !important;
            }
            html.mc-view-compact .mc-card h4 {
                margin: 0 0 0.14rem !important;
                font-size: 0.82rem !important;
            }
            html.mc-view-compact .mc-card p {
                margin: 0 !important;
                font-size: 0.72rem !important;
                line-height: 1.35 !important;
            }
            html.mc-view-compact h2,
            html.mc-view-compact h3,
            html.mc-view-compact h4 {
                margin-top: 0.18rem !important;
                margin-bottom: 0.2rem !important;
            }
            html.mc-view-compact [data-testid="stCaptionContainer"] {
                margin: 0.06rem 0 0.18rem !important;
            }
            html.mc-view-compact [data-testid="stAlert"] {
                margin: 0.18rem 0 !important;
                padding: 0.45rem 0.55rem !important;
            }
            html.mc-view-compact [data-testid="stExpander"],
            html.mc-view-compact [data-testid="stForm"],
            html.mc-view-compact [data-testid="stVerticalBlock"] > div[style*="border"] {
                margin: 0.16rem 0 0.42rem !important;
                padding: 0.72rem 0.78rem !important;
                border-radius: 16px !important;
            }
            html.mc-view-compact [data-testid="stForm"] [data-testid="stVerticalBlock"],
            html.mc-view-compact [data-testid="stExpander"] [data-testid="stVerticalBlock"] {
                gap: 0.24rem !important;
            }
            html.mc-view-compact [data-testid="stForm"] [data-testid="stElementContainer"],
            html.mc-view-compact [data-testid="stExpander"] [data-testid="stElementContainer"] {
                margin-bottom: 0.16rem !important;
            }
            html.mc-view-compact [data-testid="stTabs"] {
                margin: 0.15rem 0 0.35rem !important;
            }
            html.mc-view-compact [data-testid="stTabs"] button {
                min-height: 34px !important;
                padding: 0.32rem 0.55rem !important;
                font-size: 0.74rem !important;
            }
            html.mc-view-compact [data-testid="stMetric"] {
                padding: 0.45rem !important;
                margin: 0 !important;
            }
            html.mc-view-compact [data-testid="stMetricLabel"] {
                font-size: 0.68rem !important;
            }
            html.mc-view-compact [data-testid="stMetricValue"] {
                font-size: 1rem !important;
                line-height: 1.1 !important;
            }
            html.mc-view-compact [data-testid="stDataFrame"],
            html.mc-view-compact [data-testid="stDataEditor"] {
                margin: 0.22rem 0 !important;
            }
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stTextInput"]),
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stNumberInput"]),
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]),
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stDateInput"]),
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stTextArea"]),
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stCheckbox"]),
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stRadio"]),
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) {
                flex-direction: row !important;
                flex-wrap: wrap !important;
                align-items: flex-start !important;
                gap: 0.45rem !important;
            }
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stTextInput"]) > [data-testid="stColumn"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stNumberInput"]) > [data-testid="stColumn"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > [data-testid="stColumn"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stDateInput"]) > [data-testid="stColumn"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stTextArea"]) > [data-testid="stColumn"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stCheckbox"]) > [data-testid="stColumn"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stRadio"]) > [data-testid="stColumn"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="stColumn"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stTextInput"]) > [data-testid="column"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stNumberInput"]) > [data-testid="column"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stSelectbox"]) > [data-testid="column"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stDateInput"]) > [data-testid="column"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stTextArea"]) > [data-testid="column"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stCheckbox"]) > [data-testid="column"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stRadio"]) > [data-testid="column"],
            html.mc-view-compact [data-testid="stHorizontalBlock"]:has([data-testid="stMetric"]) > [data-testid="column"] {
                width: auto !important;
                min-width: min(100%, 9.4rem) !important;
                flex: 1 1 9.4rem !important;
                height: auto !important;
                min-height: 0 !important;
                max-height: none !important;
                align-self: flex-start !important;
                padding: 0 !important;
                margin-bottom: 0 !important;
            }
            html.mc-view-compact [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] [style*="height:"],
            html.mc-view-compact [data-testid="stHorizontalBlock"] > [data-testid="column"] [style*="height:"],
            html.mc-view-compact [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] div[data-testid="stVerticalBlock"],
            html.mc-view-compact [data-testid="stHorizontalBlock"] > [data-testid="column"] div[data-testid="stVerticalBlock"] {
                height: auto !important;
                min-height: 0 !important;
                max-height: none !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    components.html(
        f"""
        <script>
        (function() {{
          try {{
            var parentWin = window.parent && window.parent.document ? window.parent : window;
            var doc = parentWin.document || document;
            var root = doc.documentElement;
            if (!root) return;
            Array.from(root.classList).forEach(function(cls) {{
              if (cls.indexOf("mc-view-") === 0) root.classList.remove(cls);
            }});
            root.classList.remove("mc-view-compact");
            if ({str(habilitar).lower()}) {{
              root.classList.add("mc-view-compact");
              root.classList.add("mc-view-{vista_slug}");
            }}
          }} catch (e) {{}}
        }})();
        </script>
        """,
        height=0,
        width=0,
    )
