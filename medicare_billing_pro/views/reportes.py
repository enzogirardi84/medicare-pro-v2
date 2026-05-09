"""Vista de Reportes para Contador — resúmenes mensuales, exportaciones combinadas."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import streamlit as st

from core.db_sql import get_presupuestos, get_prefacturas, get_cobros
from core.utils import fmt_moneda, fmt_fecha, bloque_estado_vacio, calcular_total, agrupar_por_mes
from core.pdf_export import exportar_reporte_contable_pdf, exportar_reporte_cobros_pdf, FPDF_DISPONIBLE
from core.excel_export import exportar_reporte_contable_excel, XLSX_DISPONIBLE


def _filtrar_por_mes(items: List[Dict], mes: str, campo_fecha: str = "fecha") -> List[Dict]:
    return [it for it in items if str(it.get(campo_fecha, ""))[:7] == mes]


def render_reportes() -> None:
    st.markdown("## 📊 Reportes para Contador")
    st.caption("Resúmenes mensuales listos para tu contador. Exportá en PDF o Excel.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")

    presupuestos = get_presupuestos(empresa_id)
    prefacturas = get_prefacturas(empresa_id)
    cobros = get_cobros(empresa_id)

    # Determinar meses disponibles
    meses = set()
    for lst, campo in [(presupuestos, "fecha"), (prefacturas, "fecha"), (cobros, "fecha")]:
        for item in lst:
            f = str(item.get(campo, ""))[:7]
            if f:
                meses.add(f)
    meses_ordenados = sorted(meses, reverse=True)

    if not meses_ordenados:
        bloque_estado_vacio(
            "Sin datos para reportar",
            "Registrá presupuestos, pre-facturas o cobros para generar reportes contables.",
            "Los reportes se generan automáticamente por mes."
        )
        return

    mes_sel = st.selectbox("Seleccionar mes", meses_ordenados, format_func=lambda m: f"{m} — {date(int(m[:4]), int(m[5:7]), 1).strftime('%B %Y').capitalize()}")

    pres_mes = _filtrar_por_mes(presupuestos, mes_sel)
    fac_mes = _filtrar_por_mes(prefacturas, mes_sel)
    cob_mes = _filtrar_por_mes(cobros, mes_sel)

    # ── Métricas ──
    st.divider()
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        total_pres = calcular_total(pres_mes, "total")
        st.metric("Presupuestado", fmt_moneda(total_pres), delta=f"{len(pres_mes)} docs")
    with m2:
        total_fac = calcular_total(fac_mes, "total")
        st.metric("Facturado", fmt_moneda(total_fac), delta=f"{len(fac_mes)} docs")
    with m3:
        total_cob = calcular_total(cob_mes, "monto")
        st.metric("Cobrado", fmt_moneda(total_cob), delta=f"{len(cob_mes)} cobros")
    with m4:
        pendiente = total_fac - total_cob
        st.metric("Pendiente", fmt_moneda(pendiente), delta_color="inverse")

    st.divider()

    # ── Exportaciones ──
    st.markdown("### 📥 Exportar Reporte")

    ec1, ec2 = st.columns(2)
    with ec1:
        if XLSX_DISPONIBLE:
            excel_data = exportar_reporte_contable_excel(empresa_nombre, mes_sel, pres_mes, fac_mes, cob_mes)
            st.download_button(
                "📊 Descargar Excel para Contador",
                data=excel_data,
                file_name=f"reporte_contable_{mes_sel}_{empresa_nombre.replace(' ', '_')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        else:
            st.caption("⚠️ openpyxl no disponible para exportar Excel.")
    with ec2:
        if FPDF_DISPONIBLE:
            pdf_data = exportar_reporte_contable_pdf(empresa_nombre, mes_sel, pres_mes, fac_mes, cob_mes)
            st.download_button(
                "📄 Descargar PDF para Contador",
                data=pdf_data,
                file_name=f"reporte_contable_{mes_sel}_{empresa_nombre.replace(' ', '_')}.pdf",
                mime="application/pdf",
                use_container_width=True,
            )
        else:
            st.caption("⚠️ fpdf no disponible para exportar PDF.")

    # ── Detalle ──
    st.markdown("### 📋 Detalle del Mes")

    # Cobros
    if cob_mes:
        st.markdown(f"#### 💰 Cobros ({len(cob_mes)})")
        for c in cob_mes:
            with st.container(border=True):
                st.markdown(f"**{c.get('cliente_nombre', '—')}** — {fmt_moneda(c.get('monto', 0))}")
                st.caption(f"{fmt_fecha(c.get('fecha', ''))}  ·  {c.get('metodo_pago', '')}  ·  {c.get('concepto', '—')}")

    # Pre-facturas
    if fac_mes:
        st.markdown(f"#### 🧾 Pre-facturas ({len(fac_mes)})")
        for f in fac_mes:
            with st.container(border=True):
                st.markdown(f"**{f.get('numero', '—')}** — {f.get('cliente_nombre', '—')} — {fmt_moneda(f.get('total', 0))}")
                st.caption(f"{fmt_fecha(f.get('fecha', ''))}  ·  Estado: {f.get('estado', '—')}")

    # Presupuestos
    if pres_mes:
        st.markdown(f"#### 📝 Presupuestos ({len(pres_mes)})")
        for p in pres_mes:
            with st.container(border=True):
                st.markdown(f"**{p.get('numero', '—')}** — {p.get('cliente_nombre', '—')} — {fmt_moneda(p.get('total', 0))}")
                st.caption(f"{fmt_fecha(p.get('fecha', ''))}  ·  Estado: {p.get('estado', '—')}")

    # ── Exportar solo cobros ──
    st.divider()
    st.markdown("### 📤 Exportar Solo Cobros del Mes")
    if cob_mes:
        cc1, cc2 = st.columns(2)
        with cc1:
            if XLSX_DISPONIBLE:
                from core.excel_export import exportar_cobros_excel
                cob_excel = exportar_cobros_excel(cob_mes, empresa_nombre)
                st.download_button("📊 Cobros Excel", data=cob_excel, file_name=f"cobros_{mes_sel}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
        with cc2:
            if FPDF_DISPONIBLE:
                cob_pdf = exportar_reporte_cobros_pdf(cob_mes, empresa_nombre, f"{mes_sel}-01", f"{mes_sel}-31")
                st.download_button("📄 Cobros PDF", data=cob_pdf, file_name=f"cobros_{mes_sel}.pdf", mime="application/pdf", use_container_width=True)
