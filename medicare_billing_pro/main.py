"""Medicare Billing Pro - entry point."""
from __future__ import annotations

import streamlit as st

from core.app_logging import configurar_logging_basico, log_event
from core.auth import render_logout_button, require_auth
from core.config import ALLOW_LOCAL_FALLBACK, APP_NAME, APP_VERSION, DEBUG, PAGE_TITLE
from core.db_sql import LOCAL_DATA_PATH, get_clientes, get_cobros, get_facturas_arca, get_prefacturas, get_presupuestos, supabase
from core.billing_logic import total_saldo_prefacturas
from core.utils import fmt_moneda

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon="B",
    layout="wide",
    initial_sidebar_state="expanded",
)

configurar_logging_basico()

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
    html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
    header[data-testid="stHeader"] { background: transparent; }
    .stApp { background: #0a0f1a !important; color: #e2e8f0; }
    .main .block-container {
        max-width: 1320px;
        padding: 1.1rem 1.6rem 2.4rem !important;
    }
    h1, h2, h3 { color: #f8fafc !important; letter-spacing: 0 !important; }
    p, label, .stMarkdown, .stCaption, [data-testid="stMarkdownContainer"] { color: #cbd5e1; }
    [data-testid="stSidebar"] {
        background: #0b1220 !important;
        border-right: 1px solid rgba(148, 163, 184, 0.16) !important;
    }
    [data-testid="stSidebar"] .stMarkdown,
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] .stCaption { color: #e2e8f0 !important; }
    .billing-header {
        display: grid;
        grid-template-columns: minmax(0, 1fr) auto;
        gap: 1rem;
        align-items: end;
        margin: 0 0 1rem 0;
        padding: 1rem 1.1rem;
        border-radius: 8px;
        background: linear-gradient(135deg, #111c2e 0%, #0d1524 100%);
        border: 1px solid rgba(148, 163, 184, 0.16);
        box-shadow: 0 14px 34px rgba(2, 6, 23, 0.22);
    }
    .billing-header h1 { font-size: 1.45rem; margin: 0; }
    .billing-header p { color: #94a3b8 !important; margin: 0.25rem 0 0; }
    .billing-status-pill {
        display: inline-flex;
        align-items: center;
        justify-content: center;
        min-height: 34px;
        padding: 0 0.85rem;
        border-radius: 999px;
        color: #ccfbf1;
        background: rgba(20, 184, 166, 0.12);
        border: 1px solid rgba(45, 212, 191, 0.22);
        font-size: 0.82rem;
        font-weight: 750;
        white-space: nowrap;
    }
    .billing-summary {
        display: grid;
        gap: 0.7rem;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
        margin: 0 0 0.9rem;
    }
    .billing-kpi {
        padding: 0.85rem 0.95rem;
        border-radius: 8px;
        background: #101827;
        border: 1px solid rgba(148, 163, 184, 0.14);
    }
    .billing-kpi span {
        display: block;
        color: #94a3b8;
        font-size: 0.72rem;
        font-weight: 700;
        text-transform: uppercase;
        margin-bottom: 0.35rem;
    }
    .billing-kpi strong {
        color: #f8fafc;
        display: block;
        font-size: 1.15rem;
    }
    [data-baseweb="input"] > div,
    [data-baseweb="select"] > div,
    [data-baseweb="textarea"] > div,
    textarea,
    input {
        background: rgba(15, 23, 42, 0.86) !important;
        border-color: #334155 !important;
        color: #f8fafc !important;
        border-radius: 8px !important;
    }
    [data-baseweb="input"] > div:focus-within,
    [data-baseweb="select"] > div:focus-within,
    [data-baseweb="textarea"] > div:focus-within {
        border-color: #14b8a6 !important;
        box-shadow: 0 0 0 3px rgba(20, 184, 166, 0.16) !important;
    }
    .stButton > button {
        border-radius: 8px !important;
        min-height: 2.65rem !important;
        font-weight: 700 !important;
        white-space: normal !important;
    }
    .stButton > button[kind="primary"],
    .stButton > button[data-testid="stBaseButton-primary"] {
        background: linear-gradient(135deg, #14b8a6 0%, #2563eb 100%) !important;
        border: 1px solid rgba(94, 234, 212, 0.35) !important;
        color: #ffffff !important;
    }
    .stButton > button[kind="secondary"],
    .stButton > button[data-testid="stBaseButton-secondary"] {
        background: #1e293b !important;
        color: #e2e8f0 !important;
        border: 1px solid #334155 !important;
    }
    .stButton > button p { color: inherit !important; }
    [data-testid="stTabs"] [role="tablist"] {
        background: #101827 !important;
        border-radius: 8px !important;
        border: 1px solid rgba(148, 163, 184, 0.14) !important;
        padding: 0.35rem;
    }
    [data-testid="stTabs"] [role="tab"] {
        border-radius: 7px;
        color: #cbd5e1;
        font-weight: 700;
        padding: 0.55rem 0.85rem;
    }
    [data-testid="stTabs"] [aria-selected="true"] {
        background: #0f172a;
        color: #ffffff;
        box-shadow: inset 0 -2px 0 #14b8a6;
    }
    [data-testid="stForm"],
    [data-testid="stVerticalBlockBorderWrapper"],
    [data-testid="stMetric"] {
        background: #101827 !important;
        border: 1px solid rgba(148, 163, 184, 0.14) !important;
        border-radius: 8px !important;
        box-shadow: none !important;
    }
    [data-testid="stAlert"] { border-radius: 8px; }
    [data-testid="stVerticalBlockBorderWrapper"] div[style*="overflow"]::-webkit-scrollbar,
    div[style*="overflow"]::-webkit-scrollbar {
        width: 8px;
        height: 8px;
    }
    [data-testid="stVerticalBlockBorderWrapper"] div[style*="overflow"]::-webkit-scrollbar-track,
    div[style*="overflow"]::-webkit-scrollbar-track {
        background: rgba(15, 23, 42, 0.55);
        border-radius: 999px;
    }
    [data-testid="stVerticalBlockBorderWrapper"] div[style*="overflow"]::-webkit-scrollbar-thumb,
    div[style*="overflow"]::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #14b8a6 0%, #2563eb 100%);
        border-radius: 999px;
    }
    @media (max-width: 900px) {
        .billing-summary { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    }
    @media (max-width: 760px) {
        .main .block-container { padding: 0.8rem 0.75rem 2rem !important; }
        .billing-header { grid-template-columns: 1fr; }
        .billing-summary { grid-template-columns: 1fr; }
    }
    </style>
    """,
    unsafe_allow_html=True,
)

if not require_auth():
    st.stop()

user = st.session_state.get("billing_user", {})
empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
empresa_id = st.session_state.get("billing_empresa_id", "")

with st.sidebar:
    st.markdown(f"## {APP_NAME}")
    st.caption(f"v{APP_VERSION}")
    st.divider()
    st.markdown(f"**{user.get('nombre', 'Usuario')}**")
    st.caption(f"Empresa: {empresa_nombre}")
    st.caption(f"Rol: {user.get('rol', 'usuario')}")
    st.caption("Supabase conectado" if supabase else "Supabase requerido")
    if ALLOW_LOCAL_FALLBACK and LOCAL_DATA_PATH.exists():
        st.caption(f"Archivo local: `{LOCAL_DATA_PATH.name}`")
    st.divider()
    render_logout_button()
    st.divider()
    st.caption("2026 Medicare Pro Suite")
    st.caption("[Documentacion](https://github.com/enzogirardi84/medicare-pro-v2)")

st.markdown(
    f"""
    <div class="billing-header">
        <div>
            <h1>Medicare Billing Pro</h1>
            <p>Facturacion medica profesional | {empresa_nombre}</p>
        </div>
        <div class="billing-status-pill">{'Supabase activo' if supabase else 'Supabase requerido'}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

MODULOS = {
    "Resumen": "dashboard",
    "Clientes fiscales": "clientes",
    "Presupuestos": "presupuestos",
    "Pre-facturas": "prefacturas",
    "Facturas ARCA": "facturas_arca",
    "Cobros": "cobros",
    "Cuenta corriente": "cuenta_corriente",
    "Reportes": "reportes",
    "Configuracion": "configuracion",
}

if "billing_modulo_activo" not in st.session_state or st.session_state["billing_modulo_activo"] not in MODULOS:
    st.session_state["billing_modulo_activo"] = "Resumen"

modulo_activo = st.session_state["billing_modulo_activo"]

clientes_resumen = get_clientes(empresa_id)
presupuestos_resumen = get_presupuestos(empresa_id)
prefacturas_resumen = get_prefacturas(empresa_id)
cobros_resumen = get_cobros(empresa_id)
facturas_arca_resumen = get_facturas_arca(empresa_id)
cobros_total = sum(float(c.get("monto", 0) or 0) for c in cobros_resumen)
pendiente_total = total_saldo_prefacturas(prefacturas_resumen, cobros_resumen)

st.markdown(
    f"""
    <div class="billing-summary">
        <div class="billing-kpi"><span>Clientes</span><strong>{len(clientes_resumen)}</strong></div>
        <div class="billing-kpi"><span>Presupuestos</span><strong>{len(presupuestos_resumen)}</strong></div>
        <div class="billing-kpi"><span>Pre-facturas</span><strong>{len(prefacturas_resumen)}</strong></div>
        <div class="billing-kpi"><span>Facturas ARCA</span><strong>{len(facturas_arca_resumen)}</strong></div>
        <div class="billing-kpi"><span>Cobrado</span><strong>{fmt_moneda(cobros_total)}</strong></div>
        <div class="billing-kpi"><span>Pendiente</span><strong>{fmt_moneda(pendiente_total)}</strong></div>
    </div>
    """,
    unsafe_allow_html=True,
)

cols = st.columns(len(MODULOS))
for i, label in enumerate(MODULOS):
    with cols[i]:
        if st.button(
            label,
            key=f"nav_{label}",
            use_container_width=True,
            type="primary" if modulo_activo == label else "secondary",
        ):
            st.session_state["billing_modulo_activo"] = label
            st.rerun()

st.divider()

if not supabase:
    st.error(
        "Supabase no esta conectado. Configura SUPABASE_URL, SUPABASE_KEY y SUPABASE_SERVICE_ROLE_KEY."
    )
elif ALLOW_LOCAL_FALLBACK and LOCAL_DATA_PATH.exists():
    st.info("Modo respaldo local habilitado. En produccion usa BILLING_ALLOW_LOCAL_FALLBACK=false.")

modulo_key = MODULOS.get(modulo_activo, "dashboard")


def _match_global(row: dict, query: str, fields: list[str]) -> bool:
    text = " ".join(str(row.get(field, "")) for field in fields).lower()
    return query in text


def _global_results(query: str) -> list[dict]:
    results: list[dict] = []
    for cliente in clientes_resumen:
        if _match_global(cliente, query, ["nombre", "dni", "email", "telefono", "condicion_fiscal"]):
            results.append(
                {
                    "modulo": "Clientes fiscales",
                    "titulo": cliente.get("nombre", "Cliente"),
                    "detalle": f"DNI/CUIT {cliente.get('dni', '-')} | {cliente.get('email', '')}",
                    "cliente_label": f"{cliente.get('nombre', 'Sin nombre')} | {cliente.get('dni', '')}"
                    if cliente.get("dni")
                    else cliente.get("nombre", "Sin nombre"),
                }
            )
    for presupuesto in presupuestos_resumen:
        if _match_global(presupuesto, query, ["numero", "cliente_nombre", "estado", "notas"]):
            results.append(
                {
                    "modulo": "Presupuestos",
                    "titulo": presupuesto.get("numero", "Presupuesto"),
                    "detalle": f"{presupuesto.get('cliente_nombre', '-')} | {fmt_moneda(presupuesto.get('total', 0))}",
                }
            )
    for prefactura in prefacturas_resumen:
        if _match_global(prefactura, query, ["numero", "cliente_nombre", "cliente_dni", "estado", "notas"]):
            results.append(
                {
                    "modulo": "Pre-facturas",
                    "titulo": prefactura.get("numero", "Pre-factura"),
                    "detalle": f"{prefactura.get('cliente_nombre', '-')} | {fmt_moneda(prefactura.get('total', 0))}",
                }
            )
    for factura in facturas_arca_resumen:
        if _match_global(factura, query, ["numero", "cliente_nombre", "cliente_dni", "estado", "cae"]):
            results.append(
                {
                    "modulo": "Facturas ARCA",
                    "titulo": f"{factura.get('tipo_comprobante', '')} {factura.get('numero', 'Factura ARCA')}",
                    "detalle": f"{factura.get('cliente_nombre', '-')} | {fmt_moneda(factura.get('total', 0))}",
                }
            )
    for cobro in cobros_resumen:
        if _match_global(cobro, query, ["cliente_nombre", "concepto", "metodo_pago", "estado"]):
            results.append(
                {
                    "modulo": "Cobros",
                    "titulo": cobro.get("cliente_nombre", "Cobro"),
                    "detalle": f"{cobro.get('concepto', '-')} | {fmt_moneda(cobro.get('monto', 0))}",
                }
            )
    return results[:12]


global_query = st.text_input(
    "Busqueda global",
    placeholder="Buscar cliente, DNI/CUIT, presupuesto, pre-factura, factura ARCA o cobro...",
    key="billing_global_search",
)
if global_query.strip():
    query = global_query.strip().lower()
    matches = _global_results(query)
    with st.container(height=260 if matches else 120, border=True):
        if not matches:
            st.caption("No se encontraron coincidencias.")
        else:
            for idx, item in enumerate(matches):
                c1, c2 = st.columns([4, 1])
                with c1:
                    st.markdown(f"**{item['titulo']}**")
                    st.caption(f"{item['modulo']} | {item['detalle']}")
                with c2:
                    if st.button("Abrir", key=f"global_open_{idx}_{item['modulo']}", use_container_width=True):
                        st.session_state["billing_modulo_activo"] = item["modulo"]
                        if item.get("cliente_label"):
                            st.session_state["cc_cliente_label"] = item["cliente_label"]
                        st.rerun()

try:
    if modulo_key == "dashboard":
        from views.dashboard import render_dashboard

        render_dashboard()
    elif modulo_key == "clientes":
        from views.clientes import render_clientes

        render_clientes()
    elif modulo_key == "presupuestos":
        from views.presupuestos import render_presupuestos

        render_presupuestos()
    elif modulo_key == "prefacturas":
        from views.prefacturas import render_prefacturas

        render_prefacturas()
    elif modulo_key == "facturas_arca":
        from views.facturas_arca import render_facturas_arca

        render_facturas_arca()
    elif modulo_key == "cobros":
        from views.cobros import render_cobros

        render_cobros()
    elif modulo_key == "cuenta_corriente":
        from views.cuenta_corriente import render_cuenta_corriente

        render_cuenta_corriente()
    elif modulo_key == "reportes":
        from views.reportes import render_reportes

        render_reportes()
    elif modulo_key == "configuracion":
        from views.configuracion import render_configuracion

        render_configuracion()
except Exception as exc:
    log_event("main", f"error_render:{modulo_key}:{type(exc).__name__}:{exc}")
    st.error(f"Error al cargar el modulo **{modulo_activo}**. Intenta recargar la pagina.")
    if DEBUG:
        st.exception(exc)
