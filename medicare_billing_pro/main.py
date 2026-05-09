"""Medicare Billing Pro — Sistema de Facturación Médica Profesional.
Entry point principal. Ejecutar con: streamlit run main.py
"""
from __future__ import annotations

import streamlit as st

from core.config import PAGE_TITLE, APP_NAME, APP_VERSION
from core.app_logging import configurar_logging_basico, log_event
from core.auth import require_auth, render_logout_button
from core.db_sql import supabase, LOCAL_DATA_PATH

# ── Page config ────────────────────────────────────────────
st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon="🧾",
    layout="wide",
    initial_sidebar_state="expanded",
)

configurar_logging_basico()

# ── CSS Profesional ────────────────────────────────────────
st.markdown("""
<style>
    /* ── Global ── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0F2644 0%, #1a3a5c 100%);
    }
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stCaption {
        color: #e2e8f0 !important;
    }
    [data-testid="stSidebar"] h2, [data-testid="stSidebar"] h3 {
        color: #ffffff !important;
    }
    [data-testid="stSidebar"] button {
        border-radius: 8px !important;
        font-weight: 500 !important;
    }

    /* ── Header ── */
    .billing-header {
        background: linear-gradient(135deg, #0F2644 0%, #1e4d7b 100%);
        margin: -4rem -4rem 1.5rem -4rem;
        padding: 1.8rem 3rem;
        border-bottom: 3px solid #f59e0b;
    }
    .billing-header h1 {
        color: #ffffff;
        font-size: 1.6rem;
        font-weight: 700;
        margin: 0;
    }
    .billing-header p {
        color: #94a3b8;
        font-size: 0.85rem;
        margin: 0.2rem 0 0 0;
    }

    /* ── Nav pills ── */
    .billing-nav-container {
        display: flex;
        gap: 0.4rem;
        flex-wrap: wrap;
        margin-bottom: 1.5rem;
    }
    .billing-nav-pill {
        padding: 0.5rem 1.2rem;
        border-radius: 20px;
        font-size: 0.85rem;
        font-weight: 500;
        cursor: pointer;
        transition: all 0.2s;
        background: #f1f5f9;
        color: #475569;
        border: 1px solid #e2e8f0;
        text-decoration: none;
        display: inline-block;
    }
    .billing-nav-pill:hover {
        background: #e2e8f0;
        color: #1e293b;
    }
    .billing-nav-pill.active {
        background: #0F2644;
        color: #ffffff;
        border-color: #0F2644;
    }

    /* ── Cards ── */
    .billing-card {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
        border: 1px solid #f1f5f9;
    }

    /* ── Métricas ── */
    [data-testid="stMetric"] {
        background: #ffffff;
        border-radius: 10px;
        padding: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        border: 1px solid #f1f5f9;
    }
    [data-testid="stMetric"] label {
        color: #64748b !important;
        font-size: 0.8rem !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #0F2644 !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 500 !important;
        transition: all 0.15s !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 2px 8px rgba(0,0,0,0.1);
    }

    /* ── Forms ── */
    [data-testid="stForm"] {
        background: #ffffff;
        border-radius: 12px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06);
        border: 1px solid #e2e8f0;
    }
</style>
""", unsafe_allow_html=True)

# ── Auth ───────────────────────────────────────────────────
if not require_auth():
    st.stop()

# ── Sidebar ────────────────────────────────────────────────
user = st.session_state.get("billing_user", {})
empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")

with st.sidebar:
    st.markdown(f"## 🧾 {APP_NAME}")
    st.caption(f"v{APP_VERSION}")
    st.divider()
    st.markdown(f"**{user.get('nombre', 'Usuario')}**")
    st.caption(f"🏥 {empresa_nombre}")
    st.caption(f"🔑 {user.get('rol', 'usuario')}")
    if supabase:
        st.caption("☁️ Supabase conectado")
    else:
        st.caption("💾 Modo local")
    if LOCAL_DATA_PATH.exists():
        st.caption(f"Archivo local: `{LOCAL_DATA_PATH.name}`")
    st.divider()
    render_logout_button()
    st.divider()
    st.caption("© 2026 Medicare Pro Suite")
    st.caption("[Documentación](https://github.com/enzogirardi84/medicare-pro-v2)")

# ── Header ─────────────────────────────────────────────────
st.markdown(f"""
<div class="billing-header">
    <h1>🧾 Medicare Billing Pro</h1>
    <p>Facturación médica profesional · {empresa_nombre}</p>
</div>
""", unsafe_allow_html=True)

# ── Navegación ─────────────────────────────────────────────
MODULOS = {
    "🏢 Clientes Fiscales": "clientes",
    "📝 Presupuestos": "presupuestos",
    "🧾 Pre-facturas": "prefacturas",
    "💰 Historial de Cobros": "cobros",
    "📊 Reportes para Contador": "reportes",
}

if "billing_modulo_activo" not in st.session_state:
    st.session_state["billing_modulo_activo"] = "🏢 Clientes Fiscales"

modulo_activo = st.session_state["billing_modulo_activo"]

# Render nav pills
cols = st.columns(len(MODULOS))
for i, (label, _) in enumerate(MODULOS.items()):
    with cols[i]:
        is_active = modulo_activo == label
        if st.button(
            label,
            key=f"nav_{label}",
            use_container_width=True,
            type="primary" if is_active else "secondary",
        ):
            st.session_state["billing_modulo_activo"] = label
            st.rerun()

st.divider()

if LOCAL_DATA_PATH.exists():
    st.info(
        "Modo respaldo local activo: si las tablas `billing_*` todavía no existen en Supabase, "
        "los datos se guardan en `data/billing_data.json` y la app sigue funcionando."
    )

# ── Router de vistas ───────────────────────────────────────
modulo_key = MODULOS.get(modulo_activo, "clientes")

try:
    if modulo_key == "clientes":
        from views.clientes import render_clientes
        render_clientes()
    elif modulo_key == "presupuestos":
        from views.presupuestos import render_presupuestos
        render_presupuestos()
    elif modulo_key == "prefacturas":
        from views.prefacturas import render_prefacturas
        render_prefacturas()
    elif modulo_key == "cobros":
        from views.cobros import render_cobros
        render_cobros()
    elif modulo_key == "reportes":
        from views.reportes import render_reportes
        render_reportes()
except Exception as exc:
    log_event("main", f"error_render:{modulo_key}:{type(exc).__name__}:{exc}")
    st.error(f"Error al cargar el módulo **{modulo_activo}**. Revisá los logs o intentá de nuevo.")
    st.exception(exc)
