"""Vista de Reportes."""
from __future__ import annotations

from datetime import date
from typing import Dict, List

import streamlit as st

from core.db_sql import get_cobros, get_facturas_arca, get_prefacturas, get_presupuestos
from core.excel_export import XLSX_DISPONIBLE, exportar_cobros_excel, exportar_facturas_arca_excel, exportar_reporte_contable_excel
from core.pdf_export import FPDF_DISPONIBLE, exportar_reporte_cobros_pdf, exportar_reporte_contable_pdf
from core.billing_logic import enriquecer_prefacturas_con_saldo, money
from core.utils import bloque_estado_vacio, calcular_total, fmt_fecha, fmt_moneda, sanitize_filename


MESES_ES = {
    "01": "enero",
    "02": "febrero",
    "03": "marzo",
    "04": "abril",
    "05": "mayo",
    "06": "junio",
    "07": "julio",
    "08": "agosto",
    "09": "septiembre",
    "10": "octubre",
    "11": "noviembre",
    "12": "diciembre",
}


def _filtrar_por_mes(items: List[Dict], mes: str, campo_fecha: str = "fecha") -> List[Dict]:
    return [it for it in items if str(it.get(campo_fecha, ""))[:7] == mes]


def _mes_label(mes: str) -> str:
    try:
        nombre = MESES_ES.get(mes[5:7], mes[5:7]).capitalize()
        return f"{mes} | {nombre} {mes[:4]}"
    except Exception:
        return mes


def _dias_vencido(fecha_vencimiento: str) -> int:
    try:
        vencimiento = date.fromisoformat(str(fecha_vencimiento)[:10])
        return (date.today() - vencimiento).days
    except Exception:
        return 0


def _es_pendiente(item: Dict) -> bool:
    return str(item.get("estado", "")).strip().lower() in {"pendiente", "parcial"}


def _detalle_simple(titulo: str, items: List[Dict], monto_key: str = "total") -> None:
    if not items:
        return
    st.markdown(f"#### {titulo} ({len(items)})")
    with st.container(height=360, border=False):
        for item in items:
            with st.container(border=True):
                numero = item.get("numero") or item.get("cliente_nombre", "-")
                cliente = item.get("cliente_nombre", "")
                monto = fmt_moneda(item.get(monto_key, 0))
                st.markdown(f"**{numero}** {('| ' + cliente) if cliente and numero != cliente else ''} | {monto}")
                st.caption(f"{fmt_fecha(item.get('fecha', ''))} | Estado: {item.get('estado', '-')}")


def render_reportes() -> None:
    st.markdown("## Reportes")
    st.caption("Resumen mensual para contador con exportacion PDF y Excel.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")

    presupuestos = get_presupuestos(empresa_id)
    cobros = get_cobros(empresa_id)
    prefacturas = enriquecer_prefacturas_con_saldo(get_prefacturas(empresa_id), cobros)
    facturas_arca = get_facturas_arca(empresa_id)

    meses = set()
    for collection in (presupuestos, prefacturas, cobros, facturas_arca):
        for item in collection:
            fecha = str(item.get("fecha", ""))[:7]
            if fecha:
                meses.add(fecha)
    meses_ordenados = sorted(meses, reverse=True)

    if not meses_ordenados:
        bloque_estado_vacio(
            "Sin datos para reportar",
            "Registra presupuestos, pre-facturas o cobros para generar reportes contables.",
            "Los reportes se generan automaticamente por mes.",
        )
        return

    mes_sel = st.selectbox("Mes", meses_ordenados, format_func=_mes_label)
    pres_mes = _filtrar_por_mes(presupuestos, mes_sel)
    fac_mes = _filtrar_por_mes(prefacturas, mes_sel)
    cob_mes = _filtrar_por_mes(cobros, mes_sel)
    arca_mes = _filtrar_por_mes(facturas_arca, mes_sel)

    total_pres = calcular_total(pres_mes, "total")
    total_fac = calcular_total(fac_mes, "total")
    total_arca = calcular_total(arca_mes, "total")
    total_cob = calcular_total(cob_mes, "monto")
    pendiente = sum(money(p.get("saldo")) for p in fac_mes)

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Presupuestado", fmt_moneda(total_pres), delta=f"{len(pres_mes)} docs")
    m2.metric("Pre-facturado", fmt_moneda(total_fac), delta=f"{len(fac_mes)} docs")
    m3.metric("Facturas ARCA", fmt_moneda(total_arca), delta=f"{len(arca_mes)} docs")
    m4.metric("Cobrado", fmt_moneda(total_cob), delta=f"{len(cob_mes)} cobros")
    m5.metric("Pendiente", fmt_moneda(pendiente), delta_color="inverse")

    pendientes_mes = [item for item in fac_mes if money(item.get("saldo")) > 0 and _es_pendiente({"estado": item.get("estado_calculado", item.get("estado", ""))})]
    vencidas = [item for item in pendientes_mes if _dias_vencido(item.get("vencimiento", "")) > 0]
    por_vencer = [item for item in pendientes_mes if _dias_vencido(item.get("vencimiento", "")) <= 0]

    st.markdown("### Cartera pendiente")
    c1, c2, c3 = st.columns(3)
    c1.metric("Pendiente del mes", fmt_moneda(sum(money(p.get("saldo")) for p in pendientes_mes)), delta=f"{len(pendientes_mes)} docs")
    c2.metric("Vencidas", len(vencidas), delta=fmt_moneda(sum(money(p.get("saldo")) for p in vencidas)), delta_color="inverse")
    c3.metric("Por vencer", len(por_vencer), delta=fmt_moneda(sum(money(p.get("saldo")) for p in por_vencer)))

    if pendientes_mes:
        cartera_rows = []
        for item in sorted(pendientes_mes, key=lambda it: str(it.get("vencimiento") or it.get("fecha") or "")):
            dias = _dias_vencido(item.get("vencimiento", ""))
            cartera_rows.append(
                {
                    "Numero": item.get("numero", ""),
                    "Cliente": item.get("cliente_nombre", ""),
                    "Vence": fmt_fecha(item.get("vencimiento", "")),
                    "Dias": dias if dias > 0 else 0,
                    "Total": fmt_moneda(item.get("total", 0)),
                    "Cobrado": fmt_moneda(item.get("cobrado", 0)),
                    "Saldo": fmt_moneda(item.get("saldo", 0)),
                }
            )
        st.dataframe(cartera_rows, width='stretch', hide_index=True, height=260)
    else:
        bloque_estado_vacio("Cartera al dia", "No hay pre-facturas pendientes en el mes seleccionado.")

    st.markdown("### Exportar reporte")
    ec1, ec2, ec3, ec4, ec5 = st.columns(5)
    base_name = f"{mes_sel}_{sanitize_filename(empresa_nombre)}"
    with ec1:
        if XLSX_DISPONIBLE:
            st.download_button(
                "Excel contable",
                data=exportar_reporte_contable_excel(empresa_nombre, mes_sel, pres_mes, fac_mes, cob_mes),
                file_name=f"reporte_contable_{base_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width='stretch',
            )
    with ec2:
        if FPDF_DISPONIBLE:
            st.download_button(
                "PDF contable",
                data=exportar_reporte_contable_pdf(empresa_nombre, mes_sel, pres_mes, fac_mes, cob_mes),
                file_name=f"reporte_contable_{base_name}.pdf",
                mime="application/pdf",
                width='stretch',
            )
    with ec3:
        if XLSX_DISPONIBLE and cob_mes:
            st.download_button(
                "Cobros Excel",
                data=exportar_cobros_excel(cob_mes, empresa_nombre),
                file_name=f"cobros_{base_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width='stretch',
            )
    with ec4:
        if FPDF_DISPONIBLE and cob_mes:
            st.download_button(
                "Cobros PDF",
                data=exportar_reporte_cobros_pdf(cob_mes, empresa_nombre, f"{mes_sel}-01", f"{mes_sel}-31"),
                file_name=f"cobros_{base_name}.pdf",
                mime="application/pdf",
                width='stretch',
            )
    with ec5:
        if XLSX_DISPONIBLE and arca_mes:
            st.download_button(
                "ARCA Excel",
                data=exportar_facturas_arca_excel(arca_mes, empresa_nombre),
                file_name=f"facturas_arca_{base_name}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                width='stretch',
            )

    st.divider()
    st.markdown("### Detalle del mes")

    if cob_mes:
        st.markdown(f"#### Cobros ({len(cob_mes)})")
        with st.container(height=360, border=False):
            for cobro in cob_mes:
                with st.container(border=True):
                    st.markdown(f"**{cobro.get('cliente_nombre', '-')}** | {fmt_moneda(cobro.get('monto', 0))}")
                    st.caption(f"{fmt_fecha(cobro.get('fecha', ''))} | {cobro.get('metodo_pago', '')} | {cobro.get('concepto', '-')}")

    _detalle_simple("Pre-facturas", fac_mes, "total")
    _detalle_simple("Facturas ARCA", arca_mes, "total")
    _detalle_simple("Presupuestos", pres_mes, "total")
