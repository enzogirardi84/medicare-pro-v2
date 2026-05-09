"""Vista de Historial de Cobros — registro de pagos y estados."""
from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List

import streamlit as st

from core.db_sql import get_clientes, get_cobros, get_prefacturas, upsert_cobro, delete_cobro, upsert_prefactura
from core.utils import generar_id, hoy, fmt_moneda, fmt_fecha, bloque_estado_vacio, calcular_total, agrupar_por_mes
from core.pdf_export import exportar_reporte_cobros_pdf, FPDF_DISPONIBLE
from core.excel_export import exportar_cobros_excel, XLSX_DISPONIBLE

METODOS_PAGO = ["Efectivo", "Transferencia", "Tarjeta de Crédito", "Tarjeta de Débito", "Cheque", "Mercado Pago", "Otro"]
ESTADOS_COBRO = ["Cobrado", "Pendiente", "Parcial", "Anulado"]


def _form_cobro(existing: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    es_edicion = existing is not None
    clientes = get_clientes(st.session_state.get("billing_empresa_id", ""))
    cliente_opts = {c["nombre"]: c for c in clientes}
    prefacturas = get_prefacturas(st.session_state.get("billing_empresa_id", ""))
    prefacturas_pendientes = [p for p in prefacturas if p.get("estado") in ("Pendiente", "Parcial")]

    with st.form(f"cobro_form_{'edit' if es_edicion else 'new'}", border=True):
        st.markdown(f"### {'✏️ Editar' if es_edicion else '💰 Nuevo'} Cobro")
        c1, c2 = st.columns(2)
        with c1:
            cliente_sel = st.selectbox(
                "Cliente *",
                options=[""] + list(cliente_opts.keys()),
                index=0 if not existing else list(cliente_opts.keys()).index(existing.get("cliente_nombre", "")) + 1 if existing.get("cliente_nombre") in cliente_opts else 0,
                key="cob_cliente",
            )
        with c2:
            fecha = st.date_input("Fecha de cobro", value=date.today() if not existing else date.fromisoformat(str(existing.get("fecha", str(hoy())))[:10]), key="cob_fecha")

        c3, c4 = st.columns(2)
        with c3:
            monto = st.number_input("Monto $ *", min_value=0.0, value=float(existing.get("monto", 0)) if existing else 0.0, step=100.0, key="cob_monto")
        with c4:
            metodo = st.selectbox("Método de pago", METODOS_PAGO, index=METODOS_PAGO.index(existing.get("metodo_pago", "Efectivo")) if existing and existing.get("metodo_pago") in METODOS_PAGO else 0, key="cob_metodo")

        concepto = st.text_input("Concepto", value=existing.get("concepto", "") if existing else "", key="cob_concepto", placeholder="Ej: Pago honorarios marzo 2026")

        # Vincular a pre-factura
        if prefacturas_pendientes:
            fac_opts = {f"{p.get('numero', '')} — {fmt_moneda(p.get('total', 0))}": p for p in prefacturas_pendientes}
            fac_sel = st.selectbox("Vincular a pre-factura (opcional)", options=["— Ninguna —"] + list(fac_opts.keys()), key="cob_fac")
        else:
            fac_sel = "— Ninguna —"

        notas = st.text_area("Notas", value=existing.get("notas", "") if existing else "", key="cob_notas", height=60)

        submitted = st.form_submit_button("💾 Guardar Cobro", use_container_width=True, type="primary")
        if submitted:
            if not cliente_sel or monto <= 0:
                st.error("Cliente y monto mayor a 0 son obligatorios.")
                return None
            cliente_data = cliente_opts.get(cliente_sel, {})
            data = {
                "id": existing.get("id") if existing else generar_id(),
                "empresa_id": st.session_state.get("billing_empresa_id", ""),
                "cliente_id": cliente_data.get("id", ""),
                "cliente_nombre": cliente_sel,
                "fecha": fecha.isoformat(),
                "monto": monto,
                "metodo_pago": metodo,
                "concepto": concepto.strip(),
                "estado": "Cobrado",
                "notas": notas.strip(),
            }
            # Vincular pre-factura
            if fac_sel != "— Ninguna —":
                fac_data = fac_opts.get(fac_sel)
                if fac_data:
                    data["prefactura_id"] = fac_data.get("id")
                    # Actualizar estado de pre-factura
                    fac_total = float(fac_data.get("total", 0) or 0)
                    if monto >= fac_total:
                        fac_data["estado"] = "Cobrada"
                    else:
                        fac_data["estado"] = "Parcial"
                    upsert_prefactura(fac_data)
            return data
    return None


def render_cobros() -> None:
    st.markdown("## 💰 Historial de Cobros")
    st.caption("Registrá cada pago recibido y mantené la trazabilidad completa.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    cobros = get_cobros(empresa_id)

    tab1, tab2 = st.tabs(["📋 Historial", "➕ Nuevo Cobro"])

    with tab1:
        if not cobros:
            bloque_estado_vacio("Sin cobros registrados", "Registrá tu primer cobro desde la pestaña «Nuevo Cobro».")
        else:
            # Filtros
            cf1, cf2 = st.columns(2)
            with cf1:
                metodo_filtro = st.selectbox("Filtrar por método", ["Todos"] + METODOS_PAGO, key="cob_filtro_met")
            with cf2:
                estado_filtro = st.selectbox("Filtrar por estado", ["Todos"] + ESTADOS_COBRO, key="cob_filtro_est")

            filtrados = cobros
            if metodo_filtro != "Todos":
                filtrados = [c for c in filtrados if c.get("metodo_pago") == metodo_filtro]
            if estado_filtro != "Todos":
                filtrados = [c for c in filtrados if c.get("estado") == estado_filtro]

            total_cobrado = calcular_total(filtrados, "monto")
            st.metric("Total cobrado", fmt_moneda(total_cobrado))
            st.divider()

            # Exportar
            if XLSX_DISPONIBLE and filtrados:
                excel_data = exportar_cobros_excel(filtrados, empresa_nombre)
                st.download_button("📥 Exportar Excel", data=excel_data, file_name=f"cobros_{empresa_nombre.replace(' ', '_')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

            # Agrupados por mes
            agrupados = agrupar_por_mes(filtrados)
            for mes, items in agrupados.items():
                mes_total = calcular_total(items, "monto")
                with st.expander(f"📅 {mes} — {len(items)} cobro(s) — {fmt_moneda(mes_total)}", expanded=len(agrupados) <= 2):
                    for c in items:
                        with st.container(border=True):
                            cc1, cc2, cc3 = st.columns([3, 1, 0.8])
                            with cc1:
                                st.markdown(f"**{c.get('cliente_nombre', '—')}**  ·  {fmt_moneda(c.get('monto', 0))}")
                                st.caption(f"{fmt_fecha(c.get('fecha', ''))}  ·  {c.get('metodo_pago', '')}  ·  {c.get('concepto', '—')}")
                            with cc2:
                                nuevo_estado = st.selectbox("Estado", ESTADOS_COBRO, index=ESTADOS_COBRO.index(c.get("estado", "Cobrado")) if c.get("estado") in ESTADOS_COBRO else 0, key=f"cob_est_{c.get('id')}", label_visibility="collapsed")
                                if nuevo_estado != c.get("estado"):
                                    c["estado"] = nuevo_estado
                                    upsert_cobro(c)
                                    st.rerun()
                            with cc3:
                                if st.button("🗑️", key=f"del_cob_{c.get('id')}", use_container_width=True):
                                    delete_cobro(c.get("id"))
                                    st.toast("Cobro eliminado.", icon="🗑️")
                                    st.rerun()

    with tab2:
        data = _form_cobro()
        if data:
            result = upsert_cobro(data)
            if result:
                st.toast("Cobro registrado.", icon="💰")
                st.rerun()
            else:
                st.error("Error al guardar el cobro.")
