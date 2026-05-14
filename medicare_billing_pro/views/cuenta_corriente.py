"""Cuenta corriente por cliente."""
from __future__ import annotations

from typing import Any, Dict, List

import streamlit as st

from core.billing_logic import enriquecer_prefacturas_con_saldo, money
from core.db_sql import get_clientes, get_cobros, get_facturas_arca, get_prefacturas, get_presupuestos
from core.excel_export import XLSX_DISPONIBLE, exportar_estado_cuenta_excel
from core.pdf_export import FPDF_DISPONIBLE, exportar_estado_cuenta_pdf
from core.utils import bloque_estado_vacio, fmt_fecha, fmt_moneda, sanitize_filename


def _cliente_key(cliente: Dict[str, Any]) -> str:
    doc = cliente.get("dni", "")
    return f"{cliente.get('nombre', 'Sin nombre')} | {doc}" if doc else cliente.get("nombre", "Sin nombre")


def _movimientos_cliente(
    cliente_id: str,
    presupuestos: List[Dict[str, Any]],
    prefacturas: List[Dict[str, Any]],
    facturas_arca: List[Dict[str, Any]],
    cobros: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    for presupuesto in presupuestos:
        if str(presupuesto.get("cliente_id", "")) != str(cliente_id):
            continue
        rows.append(
            {
                "fecha": presupuesto.get("fecha", ""),
                "tipo": "Presupuesto",
                "numero": presupuesto.get("numero", ""),
                "detalle": presupuesto.get("estado", ""),
                "debe": 0.0,
                "haber": 0.0,
                "orden": 0,
            }
        )
    for prefactura in prefacturas:
        if str(prefactura.get("cliente_id", "")) != str(cliente_id):
            continue
        rows.append(
            {
                "fecha": prefactura.get("fecha", ""),
                "tipo": "Pre-factura",
                "numero": prefactura.get("numero", ""),
                "detalle": prefactura.get("estado_calculado", prefactura.get("estado", "")),
                "debe": money(prefactura.get("total")),
                "haber": 0.0,
                "orden": 1,
            }
        )
    for cobro in cobros:
        if str(cobro.get("cliente_id", "")) != str(cliente_id):
            continue
        estado = str(cobro.get("estado", "Cobrado")).strip().lower()
        haber = money(cobro.get("monto")) if estado in {"cobrado", "parcial"} else 0.0
        rows.append(
            {
                "fecha": cobro.get("fecha", ""),
                "tipo": "Cobro",
                "numero": cobro.get("id", ""),
                "detalle": f"{cobro.get('metodo_pago', '')} | {cobro.get('concepto', '')}".strip(" |"),
                "debe": 0.0,
                "haber": haber,
                "orden": 2,
            }
        )
    for factura in facturas_arca:
        if str(factura.get("cliente_id", "")) != str(cliente_id):
            continue
        rows.append(
            {
                "fecha": factura.get("fecha", ""),
                "tipo": "Factura ARCA",
                "numero": factura.get("numero", ""),
                "detalle": f"{factura.get('tipo_comprobante', '')} | {factura.get('estado', '')} | CAE {factura.get('cae') or 'pendiente'}",
                "debe": 0.0,
                "haber": 0.0,
                "orden": 3,
            }
        )
    rows = sorted(rows, key=lambda r: (str(r.get("fecha", "")), int(r.get("orden", 0))))
    saldo = 0.0
    for row in rows:
        saldo += money(row.get("debe")) - money(row.get("haber"))
        row["saldo"] = saldo
    return rows


def _recalcular_saldo(movimientos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    saldo = 0.0
    recalculados: List[Dict[str, Any]] = []
    for mov in movimientos:
        row = dict(mov)
        saldo += money(row.get("debe")) - money(row.get("haber"))
        row["saldo"] = saldo
        recalculados.append(row)
    return recalculados


def render_cuenta_corriente() -> None:
    st.markdown("## Cuenta corriente")
    st.caption("Estado de cuenta por cliente con deuda, pagos y exportacion para enviar o archivar.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    clientes = get_clientes(empresa_id)
    if not clientes:
        bloque_estado_vacio(
            "Sin clientes",
            "Carga al menos un cliente fiscal para consultar su cuenta corriente.",
        )
        return

    cobros = get_cobros(empresa_id)
    prefacturas = enriquecer_prefacturas_con_saldo(get_prefacturas(empresa_id), cobros)
    presupuestos = get_presupuestos(empresa_id)
    facturas_arca = get_facturas_arca(empresa_id)

    clientes_opts = {_cliente_key(c): c for c in clientes}
    default_label = st.session_state.get("cc_cliente_label")
    labels = list(clientes_opts.keys())
    index = labels.index(default_label) if default_label in labels else 0
    selected = st.selectbox("Cliente", labels, index=index)
    st.session_state["cc_cliente_label"] = selected
    cliente = clientes_opts[selected]
    cliente_id = str(cliente.get("id", ""))

    movimientos = _movimientos_cliente(cliente_id, presupuestos, prefacturas, facturas_arca, cobros)
    if movimientos:
        fechas = sorted(str(m.get("fecha", ""))[:10] for m in movimientos if m.get("fecha"))
        fecha_desde_default = fechas[0] if fechas else ""
        fecha_hasta_default = fechas[-1] if fechas else ""
        f1, f2, f3 = st.columns([1, 1, 1.2])
        with f1:
            desde = st.date_input("Desde", value=None, key=f"cc_desde_{cliente_id}")
        with f2:
            hasta = st.date_input("Hasta", value=None, key=f"cc_hasta_{cliente_id}")
        with f3:
            tipo_filtro = st.selectbox(
                "Tipo",
                ["Todos", "Presupuesto", "Pre-factura", "Factura ARCA", "Cobro"],
                key=f"cc_tipo_{cliente_id}",
            )
        if desde:
            movimientos = [m for m in movimientos if str(m.get("fecha", ""))[:10] >= desde.isoformat()]
        if hasta:
            movimientos = [m for m in movimientos if str(m.get("fecha", ""))[:10] <= hasta.isoformat()]
        if tipo_filtro != "Todos":
            movimientos = [m for m in movimientos if m.get("tipo") == tipo_filtro]
        movimientos = _recalcular_saldo(movimientos)
        st.caption(f"Periodo completo disponible: {fmt_fecha(fecha_desde_default)} a {fmt_fecha(fecha_hasta_default)}")
    total_debe = sum(money(m.get("debe")) for m in movimientos)
    total_haber = sum(money(m.get("haber")) for m in movimientos)
    saldo = total_debe - total_haber

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Debe", fmt_moneda(total_debe))
    c2.metric("Haber", fmt_moneda(total_haber))
    c3.metric("Saldo", fmt_moneda(saldo), delta_color="inverse")
    c4.metric("Movimientos", len(movimientos))

    st.caption(
        " | ".join(
            value
            for value in [
                f"DNI/CUIT: {cliente.get('dni', '-')}",
                cliente.get("email", ""),
                cliente.get("telefono", ""),
            ]
            if value
        )
    )

    e1, e2 = st.columns(2)
    with e1:
        if XLSX_DISPONIBLE:
            st.download_button(
                "Exportar Excel",
                data=exportar_estado_cuenta_excel(cliente, empresa_nombre, movimientos, total_debe, total_haber, saldo),
                file_name=f"estado_cuenta_{sanitize_filename(cliente.get('nombre', 'cliente'))}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width='stretch',
            )
    with e2:
        if FPDF_DISPONIBLE:
            st.download_button(
                "Exportar PDF",
                data=exportar_estado_cuenta_pdf(cliente, empresa_nombre, movimientos, total_debe, total_haber, saldo),
                file_name=f"estado_cuenta_{sanitize_filename(cliente.get('nombre', 'cliente'))}.pdf",
                mime="application/pdf",
                width='stretch',
            )

    st.divider()
    if not movimientos:
        bloque_estado_vacio("Sin movimientos", "El cliente todavia no tiene presupuestos, pre-facturas ni cobros.")
        return

    rows = [
        {
            "Fecha": fmt_fecha(m.get("fecha", "")),
            "Tipo": m.get("tipo", ""),
            "Numero": m.get("numero", ""),
            "Detalle": m.get("detalle", ""),
            "Debe": fmt_moneda(m.get("debe", 0)) if money(m.get("debe")) else "",
            "Haber": fmt_moneda(m.get("haber", 0)) if money(m.get("haber")) else "",
            "Saldo": fmt_moneda(m.get("saldo", 0)),
        }
        for m in movimientos
    ]
    st.dataframe(rows, width='stretch', hide_index=True, height=430)
