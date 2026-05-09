"""Medicare Billing Pro — Sistema de Facturación Médica Profesional.
Entry point principal. Ejecutar con: streamlit run main.py
"""
from __future__ import annotations

import streamlit as st

from core.config import PAGE_TITLE, APP_NAME, APP_VERSION
from core.config import ALLOW_LOCAL_FALLBACK
from core.app_logging import configurar_logging_basico, log_event
from core.auth import require_auth, render_logout_button
from core.db_sql import (
    LOCAL_DATA_PATH,
    get_clientes,
    get_cobros,
    get_prefacturas,
    get_presupuestos,
    supabase,
)
from core.utils import fmt_moneda

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
    .stApp {
        background:
            radial-gradient(ellipse 80% 50% at 100% 0%, rgba(20, 184, 166, 0.10), transparent 55%),
            radial-gradient(ellipse 70% 45% at 0% 10%, rgba(59, 130, 246, 0.08), transparent 50%),
            linear-gradient(180deg, #0b1020 0%, #070b14 100%);
    }
    .main .block-container {
        max-width: 1440px;
        padding: 2rem 3rem 3rem;
    }
    h1, h2, h3 {
        letter-spacing: 0;
        color: #f8fafc !important;
    }
    p, label, .stMarkdown, .stCaption, [data-testid="stMarkdownContainer"] {
        color: #cbd5e1;
    }
    [data-testid="stCaptionContainer"],
    [data-testid="stMarkdownContainer"] small {
        color: #94a3b8 !important;
    }
    [data-baseweb="input"] > div,
    [data-baseweb="select"] > div,
    [data-baseweb="textarea"] > div,
    textarea,
    input {
        background: rgba(15, 23, 42, 0.82) !important;
        border-color: #334155 !important;
        color: #f8fafc !important;
    }
    [data-baseweb="input"] > div:focus-within,
    [data-baseweb="select"] > div:focus-within,
    [data-baseweb="textarea"] > div:focus-within {
        border-color: #14b8a6 !important;
        box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.16) !important;
    }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background: #0f172a;
        border-right: 1px solid #1e293b;
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
        background: #1e293b !important;
        border: 1px solid #334155 !important;
        color: #5eead4 !important;
    }

    /* ── Header ── */
    .billing-header {
        background:
            radial-gradient(ellipse 70% 90% at 100% 0%, rgba(20, 184, 166, 0.18), transparent 55%),
            linear-gradient(145deg, rgba(18, 32, 54, 0.98) 0%, rgba(11, 18, 32, 0.99) 100%);
        margin: -1rem 0 1.4rem 0;
        padding: 1.65rem 2rem;
        border: 1px solid rgba(148, 163, 184, 0.12);
        border-radius: 0 0 22px 22px;
        box-shadow: 0 24px 56px rgba(2, 6, 18, 0.28), inset 0 1px 0 rgba(255, 255, 255, 0.04);
    }
    .billing-header h1 {
        color: #ffffff;
        font-size: 1.75rem;
        font-weight: 700;
        margin: 0;
    }
    .billing-header p {
        color: #94a3b8;
        font-size: 0.92rem;
        margin: 0.35rem 0 0 0;
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
        background: #1e293b;
        color: #e2e8f0;
        border: 1px solid #334155;
        text-decoration: none;
        display: inline-block;
    }
    .billing-nav-pill:hover {
        background: #27354f;
        color: #f8fafc;
    }
    .billing-nav-pill.active {
        background: linear-gradient(135deg, #14b8a6 0%, #2563eb 100%);
        color: #ffffff;
        border-color: rgba(94, 234, 212, 0.35);
    }

    /* ── Summary ── */
    .billing-summary {
        display: grid;
        gap: 0.8rem;
        grid-template-columns: repeat(4, minmax(0, 1fr));
        margin: 0.25rem 0 1.2rem;
    }
    .billing-kpi {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.92) 0%, rgba(15, 23, 42, 0.96) 100%);
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 8px;
        padding: 0.95rem 1rem;
        box-shadow: 0 14px 34px rgba(2, 6, 18, 0.24), inset 0 1px 0 rgba(255, 255, 255, 0.04);
    }
    .billing-kpi span {
        color: #94a3b8;
        display: block;
        font-size: 0.78rem;
        font-weight: 600;
        margin-bottom: 0.35rem;
        text-transform: uppercase;
    }
    .billing-kpi strong {
        color: #f8fafc;
        display: block;
        font-size: 1.25rem;
        line-height: 1.2;
    }

    /* ── Cards ── */
    .billing-card {
        background: #1e293b;
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 1px 3px rgba(0,0,0,0.06), 0 1px 2px rgba(0,0,0,0.04);
        border: 1px solid #334155;
    }

    /* ── Métricas ── */
    [data-testid="stMetric"] {
        background: #1e293b;
        border-radius: 8px;
        padding: 1rem;
        box-shadow: 0 1px 2px rgba(0,0,0,0.04);
        border: 1px solid #334155;
    }
    [data-testid="stMetric"] label {
        color: #94a3b8 !important;
        font-size: 0.8rem !important;
    }
    [data-testid="stMetric"] [data-testid="stMetricValue"] {
        color: #f8fafc !important;
        font-size: 1.5rem !important;
        font-weight: 700 !important;
    }

    /* ── Buttons ── */
    .stButton > button {
        border-radius: 8px !important;
        font-weight: 650 !important;
        transition: all 0.15s !important;
        min-height: 3rem;
        white-space: normal !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 6px 15px rgba(14, 165, 233, 0.20);
    }
    .stButton > button[kind="secondary"] {
        background: #1e293b !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
    }
    .stButton > button[data-testid="stBaseButton-secondary"] {
        background: #1e293b !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
    }
    .stButton > button[kind="secondary"] p,
    .stButton > button[data-testid="stBaseButton-secondary"] p {
        color: #e2e8f0 !important;
    }
    .stButton > button[kind="secondary"]:hover {
        background: #27354f !important;
        border-color: #14b8a6 !important;
        color: #ffffff !important;
    }
    .stButton > button[data-testid="stBaseButton-secondary"]:hover {
        background: #27354f !important;
        border-color: #14b8a6 !important;
        color: #ffffff !important;
    }
    .stButton > button[kind="primary"] {
        background: linear-gradient(135deg, #14b8a6 0%, #2563eb 100%) !important;
        border: 1px solid rgba(94, 234, 212, 0.35) !important;
        color: #ffffff !important;
    }
    .stButton > button[data-testid="stBaseButton-primary"],
    .stButton > button[data-testid="stBaseButton-primary"] p,
    .stButton > button[kind="primary"] p {
        color: #ffffff !important;
    }
    [data-testid="stTabs"] [role="tablist"] {
        background: rgba(30, 41, 59, 0.76);
        border: 1px solid rgba(148, 163, 184, 0.14);
        border-radius: 8px;
        padding: 0.35rem;
        gap: 0.25rem;
    }
    [data-testid="stTabs"] [role="tab"] {
        border-radius: 7px;
        color: #cbd5e1;
        font-weight: 650;
        padding: 0.55rem 0.85rem;
    }
    [data-testid="stTabs"] [aria-selected="true"] {
        background: #0f172a;
        color: #ffffff;
        box-shadow: inset 0 -2px 0 #14b8a6;
    }
    [data-testid="stTabs"] [aria-selected="true"] p {
        color: #ffffff;
    }
    [data-testid="stAlert"] {
        border-radius: 8px;
    }

    /* ── Forms ── */
    [data-testid="stForm"] {
        background: linear-gradient(180deg, rgba(30, 41, 59, 0.92) 0%, rgba(15, 23, 42, 0.96) 100%);
        border-radius: 8px;
        padding: 1.5rem;
        box-shadow: 0 14px 34px rgba(2, 6, 18, 0.24);
        border: 1px solid rgba(148, 163, 184, 0.14);
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: rgba(148, 163, 184, 0.14) !important;
        border-radius: 8px !important;
        background: rgba(30, 41, 59, 0.88);
    }
    @media (max-width: 900px) {
        .main .block-container {
            padding: 1.25rem 1rem 2rem;
        }
        .billing-header {
            padding: 1.35rem 1.2rem;
        }
        .billing-summary {
            grid-template-columns: repeat(2, minmax(0, 1fr));
        }
    }
    @media (max-width: 560px) {
        .billing-summary {
            grid-template-columns: 1fr;
        }
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
        st.caption("⚠️ Supabase requerido")
    if ALLOW_LOCAL_FALLBACK and LOCAL_DATA_PATH.exists():
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
empresa_id = st.session_state.get("billing_empresa_id", "")

clientes_resumen = get_clientes(empresa_id)
presupuestos_resumen = get_presupuestos(empresa_id)
prefacturas_resumen = get_prefacturas(empresa_id)
cobros_resumen = get_cobros(empresa_id)
cobros_total = sum(float(c.get("monto", 0) or 0) for c in cobros_resumen)

st.markdown(
    f"""
    <div class="billing-summary">
        <div class="billing-kpi"><span>Clientes</span><strong>{len(clientes_resumen)}</strong></div>
        <div class="billing-kpi"><span>Presupuestos</span><strong>{len(presupuestos_resumen)}</strong></div>
        <div class="billing-kpi"><span>Pre-facturas</span><strong>{len(prefacturas_resumen)}</strong></div>
        <div class="billing-kpi"><span>Cobrado</span><strong>{fmt_moneda(cobros_total)}</strong></div>
    </div>
    """,
    unsafe_allow_html=True,
)

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

if not supabase:
    st.error(
        "Supabase no está conectado. Medicare Billing Pro requiere Supabase para guardar datos. "
        "Configurá `SUPABASE_URL`, `SUPABASE_KEY` y ejecutá `medicare_billing_pro/migracion_supabase.sql`."
    )
elif ALLOW_LOCAL_FALLBACK and LOCAL_DATA_PATH.exists():
    st.info(
        "Modo respaldo local habilitado para desarrollo. En producción dejá `BILLING_ALLOW_LOCAL_FALLBACK=false` "
        "para guardar todo exclusivamente en Supabase."
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
