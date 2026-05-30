"""Motor de adaptabilidad ambiental y contraste tactico para entornos medicos.
Detecta condiciones de iluminacion via hardware (Media Query L5) y permite
cambio manual entre modo normal, alto contraste y vision nocturna.

Modos:
- Normal: Tema oscuro corporativo estandar
- Alto Contraste: Fondos negros, bordes amarillos, texto blanco bold
- Nocturno: Tonos ambar/rojo apagado, sin luz azul
"""
from __future__ import annotations

import streamlit as st

SENSOR_KEY = "_ui_ambient_mode"


def inyectar_ambient_sensor() -> None:
    """Inyecta CSS + JS para deteccion ambiental y selector de modo.

    Incluye:
    - @media (light-level) para deteccion automatica de luminosidad
    - Boton flotante para cambio manual de modo
    - Clases CSS para cada modo (.modo-normal, .modo-alto-contraste, .modo-nocturno)
    """
    modo_actual = st.session_state.get(SENSOR_KEY, "normal")

    st.markdown(f"""<style>
    /* ─── MODO NORMAL (default) ─────────────────────── */
    .modo-normal .stApp {{
        background: linear-gradient(160deg, #08101e, #0c1929, #0f1f35, #070e18) !important;
    }}
    .modo-normal [data-testid="stButton"] button[kind="primary"] {{
        background: linear-gradient(135deg, #1d4ed8, #0ea5e9) !important;
    }}

    /* ─── MODO ALTO CONTRASTE ───────────────────────── */
    .modo-alto-contraste .stApp {{
        background: #000000 !important;
    }}
    .modo-alto-contraste [data-testid="stSidebar"] {{
        background: #0a0a0a !important;
        border-right: 2px solid #ffd700 !important;
    }}
    .modo-alto-contraste input,
    .modo-alto-contraste select,
    .modo-alto-contraste textarea {{
        border: 2px solid #ffffff !important;
        background: #000000 !important;
        color: #ffffff !important;
        font-weight: 700 !important;
    }}
    .modo-alto-contraste [data-testid="stButton"] button {{
        border: 2px solid #ffd700 !important;
        color: #ffffff !important;
        font-weight: 700 !important;
        background: #1a1a1a !important;
    }}
    .modo-alto-contraste [data-testid="stButton"] button[kind="primary"] {{
        background: #003300 !important;
        border: 2px solid #00ff00 !important;
        color: #00ff00 !important;
    }}
    .modo-alto-contraste [data-testid="stMetricValue"] {{
        background: none !important;
        -webkit-text-fill-color: #00ff00 !important;
        color: #00ff00 !important;
        font-weight: 900 !important;
    }}
    .modo-alto-contraste [data-testid="stMetricLabel"] {{
        color: #ffd700 !important;
        font-weight: 700 !important;
    }}
    .modo-alto-contraste h1, .modo-alto-contraste h2, .modo-alto-contraste h3,
    .modo-alto-contraste h4, .modo-alto-contraste p, .modo-alto-contraste span {{
        color: #ffffff !important;
        font-weight: 700 !important;
    }}

    /* ─── MODO VISION NOCTURNA ──────────────────────── */
    .modo-nocturno .stApp {{
        background: #0a0500 !important;
    }}
    .modo-nocturno [data-testid="stSidebar"] {{
        background: #0d0800 !important;
    }}
    .modo-nocturno input,
    .modo-nocturno select,
    .modo-nocturno textarea {{
        background: #1a0e00 !important;
        border-color: #8b4513 !important;
        color: #ffa500 !important;
    }}
    .modo-nocturno [data-testid="stButton"] button {{
        background: #2a1500 !important;
        border-color: #8b4513 !important;
        color: #ff8c00 !important;
    }}
    .modo-nocturno [data-testid="stButton"] button[kind="primary"] {{
        background: #4a2200 !important;
        border: 1px solid #ff4500 !important;
        color: #ff6347 !important;
    }}
    .modo-nocturno [data-testid="stMetricValue"] {{
        background: none !important;
        -webkit-text-fill-color: #ff8c00 !important;
        color: #ff8c00 !important;
    }}
    .modo-nocturno [data-testid="stMetricLabel"] {{
        color: #cd853f !important;
    }}
    .modo-nocturno h1, .modo-nocturno h2, .modo-nocturno h3 {{
        color: #ffa500 !important;
    }}
    .modo-nocturno .stApp {{
        filter: sepia(0.5) hue-rotate(-15deg) !important;
    }}

    /* ─── BOTON FLOTANTE DE CAMBIO DE MODO ──────────── */
    .mc-ambient-toggle {{
        position: fixed !important;
        bottom: 80px !important;
        right: 12px !important;
        z-index: 999999 !important;
        width: 44px !important;
        height: 44px !important;
        border-radius: 50% !important;
        border: 1px solid rgba(255,255,255,0.15) !important;
        background: rgba(15,23,42,0.85) !important;
        color: #e2e8f0 !important;
        font-size: 1.1rem !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.3) !important;
        transition: all 0.2s !important;
    }}
    .mc-ambient-toggle:hover {{
        transform: scale(1.1) !important;
    }}
    @media (hover: none) and (pointer: coarse) {{
        .mc-ambient-toggle {{
            backdrop-filter: none !important;
            -webkit-backdrop-filter: none !important;
        }}
    }}
    </style>

    <!-- Boton flotante de cambio de modo (JS puro) -->
    <div class="mc-ambient-toggle" id="mc-ambient-btn" onclick="toggleAmbientMode()"
         title="Cambiar modo de pantalla">{"☀" if modo_actual == "alto-contraste" else "🌙" if modo_actual == "nocturno" else "☀"}</div>

    <script>
    var CURRENT_MODE = "{modo_actual}";

    function toggleAmbientMode() {{
        var modes = ["normal", "alto-contraste", "nocturno"];
        var icons = ["☀", "🔦", "🌙"];
        var idx = modes.indexOf(CURRENT_MODE);
        var next = (idx + 1) % modes.length;

        // Actualizar clases en el body
        document.body.className = document.body.className
            .replace(/modo-[a-z-]+/g, "")
            .trim();
        document.body.classList.add("modo-" + modes[next]);

        // Actualizar boton
        var btn = document.getElementById("mc-ambient-btn");
        if (btn) btn.innerHTML = icons[next];
        if (btn) btn.title = "Modo: " + modes[next];

        CURRENT_MODE = modes[next];

        // Enviar nuevo modo a Streamlit via query params
        var url = new URL(window.location.href);
        url.searchParams.set("ambient", modes[next]);
        window.history.replaceState({{}}, "", url.toString());
    }}

    // Deteccion automatica via prefers-contrast / light-level
    try {{
        var mq = window.matchMedia("(prefers-contrast: more)");
        if (mq.matches && CURRENT_MODE === "normal") {{
            toggleAmbientMode();
            if (CURRENT_MODE === "normal") toggleAmbientMode(); // alto-contraste
        }}
    }} catch(e) {{}}
    </script>
    """, unsafe_allow_html=True)


def detectar_modo_ambiente() -> str:
    """Detecta el modo ambiente desde query params o session_state.

    Returns:
        "normal" | "alto-contraste" | "nocturno"
    """
    # Query param tiene prioridad (cambio manual)
    try:
        qp_mode = st.query_params.get("ambient")
        if qp_mode in ("alto-contraste", "nocturno"):
            st.session_state[SENSOR_KEY] = qp_mode
            return qp_mode
    except Exception:
        pass

    return st.session_state.get(SENSOR_KEY, "normal")


def aplicar_modo_ambiente() -> None:
    """Aplica el modo ambiente actual al DOM."""
    modo = detectar_modo_ambiente()
    st.markdown(
        f'<script>document.body.className = document.body.className.replace(/modo-[a-z-]+/g,"").trim();'
        f'document.body.classList.add("modo-{modo}");</script>',
        unsafe_allow_html=True,
    )
