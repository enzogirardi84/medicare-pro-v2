"""
Landing pre-login liviana: sin auth, database ni utils pesados (mejor FCP en PageSpeed).

Se importa antes del resto de main.py para que visitantes anónimos no paguen el arranque completo.
"""

from __future__ import annotations

import base64
from pathlib import Path

import streamlit as st

REPO_ROOT = Path(__file__).resolve().parent.parent

LANDING_CHROME_CSS = """
            #MainMenu {visibility: hidden !important;}
            header[data-testid="stHeader"],
            [data-testid="stHeader"] {display: none !important;}
            [data-testid="stToolbar"],
            [data-testid="stDecoration"] {display: none !important;}
            div[data-testid="stToolbarActions"] {display: none !important;}
            .stDeployButton,
            [class*="stDeployButton"] {display: none !important;}
            footer,
            footer[data-testid="stFooter"] {visibility: hidden !important; height: 0 !important; min-height: 0 !important; overflow: hidden !important;}
            html { overflow-x: hidden !important; scroll-behavior: smooth; }
            body, .stApp { overflow-x: hidden !important; }
            ::-webkit-scrollbar { width: 7px; background: rgba(5,8,18,0.6); }
            ::-webkit-scrollbar-thumb { background: rgba(45,212,191,0.38); border-radius: 6px; }
            ::-webkit-scrollbar-thumb:hover { background: rgba(45,212,191,0.62); }
            .block-container {
                padding-top: max(8px, env(safe-area-inset-top, 0px)) !important;
                padding-bottom: 0rem !important;
                max-width: 100% !important;
                margin-top: 0 !important;
                overflow: visible !important;
            }
            .stApp {
                background-color: #03050a !important;
                background-image:
                    radial-gradient(ellipse 100% 50% at 50% -15%, rgba(45, 212, 191, 0.08), transparent 50%),
                    radial-gradient(circle at 92% 8%, rgba(96, 165, 250, 0.1), transparent 40%),
                    linear-gradient(168deg, #03050a 0%, #060d18 100%) !important;
            }
            /* Sticky top-ingresar button */
            .block-container > div:has(> .stButton):first-of-type {
                position: sticky !important;
                top: 0 !important;
                z-index: 99999 !important;
                background: rgba(3, 5, 10, 0.93) !important;
                padding: 6px 0 !important;
                backdrop-filter: blur(10px);
                border-bottom: 1px solid rgba(45, 212, 191, 0.15);
            }
            div.stButton { display: flex; justify-content: center; margin-top: 18px; padding-bottom: 42px; }
            div.stButton > button {
                min-height: 60px !important;
                min-width: 320px !important;
                padding: 0 34px !important;
                border-radius: 9999px !important;
                border: 1px solid rgba(186, 230, 253, 0.24) !important;
                background:
                    linear-gradient(135deg, rgba(18, 184, 166, 0.98) 0%, rgba(37, 99, 235, 0.98) 58%, rgba(56, 189, 248, 0.96) 100%) !important;
                color: white !important;
                font-size: 1rem !important;
                font-weight: 900 !important;
                text-transform: uppercase;
                letter-spacing: 0.18em;
                box-shadow:
                    0 18px 42px rgba(14, 165, 233, 0.22),
                    0 0 0 1px rgba(255,255,255,0.06) inset !important;
                transition: transform 0.25s ease, box-shadow 0.25s ease, filter 0.25s ease !important;
                backdrop-filter: blur(12px);
            }
            div.stButton > button:hover {
                transform: translateY(-3px) scale(1.01) !important;
                filter: brightness(1.04) !important;
                box-shadow:
                    0 24px 54px rgba(56, 189, 248, 0.28),
                    0 0 0 1px rgba(255,255,255,0.09) inset !important;
            }
"""


def _query_flag(nombre: str) -> bool:
    qp = getattr(st, "query_params", None)
    if qp is None:
        return False
    try:
        valor = qp.get(nombre)
        if isinstance(valor, list):
            valor = valor[0] if valor else ""
        return str(valor or "").strip().lower() in {"1", "true", "si", "yes", "on"}
    except Exception:
        return False


def ensure_entered_app_default() -> None:
    """Portada por defecto; ?login=1 o ?directo=1 salta la publicidad (pruebas / acceso directo)."""
    if "entered_app" not in st.session_state:
        st.session_state.entered_app = _query_flag("login") or _query_flag("directo")


def obtener_logo_landing() -> str:
    posibles = [
        REPO_ROOT / "assets" / "logo_medicare_pro.jpeg",
        REPO_ROOT / "assets" / "logo_medicare_pro.jpg",
        REPO_ROOT / "assets" / "logo_medicare_pro.png",
        REPO_ROOT / "logo_medicare_pro.jpeg",
        REPO_ROOT / "logo_medicare_pro.jpg",
        REPO_ROOT / "logo_medicare_pro.png",
    ]
    for ruta in posibles:
        if ruta.exists():
            mime = "image/png" if ruta.suffix.lower() == ".png" else "image/jpeg"
            encoded = base64.b64encode(ruta.read_bytes()).decode()
            return (
                f"<img src='data:{mime};base64,{encoded}' "
                "alt='MediCare Enterprise PRO — plataforma de salud domiciliaria y auditoría clínica' "
                "width='112' height='112' decoding='async' fetchpriority='high' "
                "style='height:112px;width:auto;border-radius:22px;box-shadow:0 15px 35px rgba(0,0,0,0.45),0 0 24px rgba(20,184,166,0.22);display:block;'>"
            )

    svg = """
    <svg xmlns='http://www.w3.org/2000/svg' width='320' height='160' viewBox='0 0 320 160'>
      <defs>
        <linearGradient id='g1' x1='0%' y1='0%' x2='100%' y2='100%'>
          <stop offset='0%' stop-color='#14b8a6'/>
          <stop offset='100%' stop-color='#3b82f6'/>
        </linearGradient>
      </defs>
      <rect x='18' y='18' width='284' height='124' rx='28' fill='#08111f'/>
      <rect x='26' y='26' width='268' height='108' rx='24' fill='url(#g1)' opacity='0.12'/>
      <circle cx='84' cy='80' r='30' fill='url(#g1)'/>
      <path d='M74 80h20M84 70v20' stroke='#fff' stroke-width='8' stroke-linecap='round'/>
      <text x='128' y='72' fill='#f8fafc' font-size='26' font-family='Inter, Arial, sans-serif' font-weight='700'>MediCare</text>
      <text x='128' y='102' fill='#94a3b8' font-size='18' font-family='Inter, Arial, sans-serif' font-weight='600'>Enterprise PRO</text>
    </svg>
    """
    encoded = base64.b64encode(svg.encode("utf-8")).decode()
    return (
        f"<img src='data:image/svg+xml;base64,{encoded}' "
        "alt='MediCare Enterprise PRO — plataforma de salud domiciliaria y auditoría clínica' "
        "width='284' height='124' decoding='async' fetchpriority='high' "
        "style='height:112px;width:auto;display:block;'>"
    )


def render_publicidad_y_detener() -> None:
    """
    Muestra la landing y detiene el script. No importar módulos pesados antes de llamar esto.
    """
    from core.landing_publicidad import obtener_html_landing_publicidad

    st.markdown(f"<style>{LANDING_CHROME_CSS}</style>", unsafe_allow_html=True)

    # Boton sticky en HTML puro — no desaparece en re-renders de Streamlit
    st.markdown(
        """<div style="position:sticky;top:0;z-index:99999;background:rgba(3,5,10,0.93);
        padding:10px 0;text-align:center;border-bottom:1px solid rgba(45,212,191,0.18);
        backdrop-filter:blur(12px)">
        <a href="?login=1" target="_self" style="display:inline-flex;align-items:center;justify-content:center;
        min-height:52px;padding:0 36px;border-radius:9999px;
        background:linear-gradient(135deg,rgba(18,184,166,0.98) 0%,rgba(37,99,235,0.98) 58%,rgba(56,189,248,0.96) 100%);
        color:white;font-weight:900;font-size:0.95rem;letter-spacing:0.16em;
        text-decoration:none;text-transform:uppercase;
        box-shadow:0 12px 32px rgba(14,165,233,0.22);border:1px solid rgba(186,230,253,0.22)">
        \U0001F680&nbsp;&nbsp;INGRESAR AL SISTEMA
        </a></div>""",
        unsafe_allow_html=True,
    )

    logo_html = obtener_logo_landing()
    _landing_html = obtener_html_landing_publicidad(logo_html)
    if hasattr(st, "html"):
        st.html(_landing_html, width="stretch")
    else:
        st.markdown(_landing_html, unsafe_allow_html=True)
    if st.button("\U0001F680 INGRESAR AL SISTEMA", key="btn_ingresar_main"):
        st.session_state.entered_app = True
        st.rerun()
    st.stop()
