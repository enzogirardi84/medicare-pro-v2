"""Medicare Billing Pro - entry point."""
from __future__ import annotations

import sys
from pathlib import Path

# FIX: En Streamlit Cloud el repo-root core/ puede conflictear con
# medicare_billing_pro/core/. Forzamos la resolucion correcta.
_billing_root = Path(__file__).resolve().parent
if str(_billing_root) not in sys.path:
    sys.path.insert(0, str(_billing_root))

# Limpiar cache del root 'core' para evitar que Python reutilice el modulo equivocado
for _mod_name in list(sys.modules.keys()):
    if _mod_name == "core" or _mod_name.startswith("core."):
        del sys.modules[_mod_name]

import streamlit as st

from core.app_logging import configurar_logging_basico, log_event
from core.auth import render_logout_button, require_auth
from core.config import ALLOW_LOCAL_FALLBACK, APP_NAME, APP_VERSION, DEBUG, PAGE_TITLE
from core.db_sql import LOCAL_DATA_PATH, get_clientes, get_cobros, get_facturas_arca, get_prefacturas, get_presupuestos, supabase
from core.billing_logic import total_saldo_prefacturas
from core.ui_theme import aplicar_tema_billing
from core.utils import fmt_moneda

st.set_page_config(
    page_title=PAGE_TITLE,
    page_icon="B",
    layout="wide",
    initial_sidebar_state="expanded",
)

configurar_logging_basico()
aplicar_tema_billing()

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

st.title("Medicare Billing Pro")
st.caption(f"Facturacion medica profesional | {empresa_nombre}")
status = "Supabase activo" if supabase else "Supabase requerido"
if supabase:
    st.success(status)
else:
    st.warning(status)

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

# KPIs nativos de Streamlit (más compatibles con Cloud)
kpi_cols = st.columns(6)
kpis = [
    ("Clientes", len(clientes_resumen)),
    ("Presupuestos", len(presupuestos_resumen)),
    ("Pre-facturas", len(prefacturas_resumen)),
    ("Facturas ARCA", len(facturas_arca_resumen)),
    ("Cobrado", fmt_moneda(cobros_total)),
    ("Pendiente", fmt_moneda(pendiente_total)),
]
for col, (label, value) in zip(kpi_cols, kpis):
    with col:
        st.metric(label=label, value=value)

nav_labels = list(MODULOS)
for start in range(0, len(nav_labels), 3):
    cols = st.columns(3)
    for col, label in zip(cols, nav_labels[start : start + 3]):
        with col:
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
    st.divider()
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
    st.divider()

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
