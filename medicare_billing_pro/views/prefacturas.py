"""Vista de Pre-facturas — gestión de facturación previa a la factura oficial."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import streamlit as st

from core.db_sql import get_clientes, get_prefacturas, upsert_prefactura, delete_prefactura
from core.utils import generar_id, hoy, fmt_moneda, fmt_fecha, bloque_estado_vacio, calcular_total
from core.pdf_export import exportar_prefactura_pdf, FPDF_DISPONIBLE
from core.excel_export import exportar_prefacturas_excel, XLSX_DISPONIBLE

ESTADOS_PREFACTURA = ["Pendiente", "Cobrada", "Anulada", "Parcial"]


def _form_prefactura(existing: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    es_edicion = existing is not None
    clientes = get_clientes(st.session_state.get("billing_empresa_id", ""))
    cliente_opts = {c["nombre"]: c for c in clientes}
    base_items = existing.get("items", []) if existing else []
    item_count = st.number_input(
        "Cantidad de conceptos",
        min_value=1,
        max_value=20,
        value=max(1, len(base_items) or 1),
        key=f"fac_item_count_{existing.get('id') if existing else 'new'}",
    )

    with st.form(f"fac_form_{'edit' if es_edicion else 'new'}", border=True):
        st.markdown(f"### {'✏️ Editar' if es_edicion else '🧾 Nueva'} Pre-factura")
        c1, c2 = st.columns(2)
        with c1:
            cliente_sel = st.selectbox(
                "Cliente *",
                options=[""] + list(cliente_opts.keys()),
                index=0 if not existing else list(cliente_opts.keys()).index(existing.get("cliente_nombre", "")) + 1 if existing.get("cliente_nombre") in cliente_opts else 0,
                key="fac_cliente",
            )
        with c2:
            fecha = st.date_input("Fecha", value=date.today() if not existing else date.fromisoformat(str(existing.get("fecha", str(hoy())))[:10]), key="fac_fecha")

        st.markdown("#### Conceptos")
        items = []
        for i in range(int(item_count)):
            item = base_items[i] if i < len(base_items) and isinstance(base_items[i], dict) else {"concepto": "", "cantidad": 1, "precio_unitario": 0.0}
            ic1, ic2, ic3, ic4 = st.columns([3, 1, 1.2, 0.6])
            with ic1:
                item["concepto"] = st.text_input("Concepto", value=item.get("concepto", ""), key=f"fac_conc_{i}", label_visibility="collapsed" if i > 0 else "visible", placeholder="Ej: Honorarios médicos marzo")
            with ic2:
                item["cantidad"] = st.number_input("Cant.", min_value=1, value=int(item.get("cantidad", 1)), key=f"fac_cant_{i}", label_visibility="collapsed" if i > 0 else "visible")
            with ic3:
                item["precio_unitario"] = st.number_input("Precio $", min_value=0.0, value=float(item.get("precio_unitario", 0)), step=100.0, key=f"fac_precio_{i}", label_visibility="collapsed" if i > 0 else "visible")
            with ic4:
                st.markdown(f"<small style='color:#64748b'>${item['cantidad'] * item['precio_unitario']:,.0f}</small>", unsafe_allow_html=True)
            items.append(item)

        items = [it for it in items if str(it.get("concepto", "")).strip()]
        total = sum(it["cantidad"] * it["precio_unitario"] for it in items)
        st.markdown(f"**Total: {fmt_moneda(total)}**")

        notas = st.text_area("Notas", value=existing.get("notas", "") if existing else "", key="fac_notas", height=60)

        submitted = st.form_submit_button("💾 Guardar Pre-factura", use_container_width=True, type="primary")
        if submitted:
            if not cliente_sel:
                st.error("Seleccioná un cliente.")
                return None
            cliente_data = cliente_opts.get(cliente_sel, {})
            return {
                "id": existing.get("id") if existing else generar_id(),
                "empresa_id": st.session_state.get("billing_empresa_id", ""),
                "numero": existing.get("numero") if existing else f"FAC-{generar_id()[:6].upper()}",
                "cliente_id": cliente_data.get("id", ""),
                "cliente_nombre": cliente_sel,
                "cliente_dni": cliente_data.get("dni", ""),
                "fecha": fecha.isoformat(),
                "items": items,
                "total": total,
                "estado": existing.get("estado", "Pendiente") if existing else "Pendiente",
                "notas": notas.strip(),
            }
    return None


def render_prefacturas() -> None:
    st.markdown("## 🧾 Pre-facturas")
    st.caption("Documentos previos a la factura oficial. Registrá, cobrá y exportá.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    prefacturas = get_prefacturas(empresa_id)

    tab1, tab2 = st.tabs(["📋 Historial", "➕ Nueva Pre-factura"])

    with tab1:
        if not prefacturas:
            bloque_estado_vacio("Sin pre-facturas", "Creá tu primera pre-factura o convertí un presupuesto aceptado.")
        else:
            estado_filtro = st.selectbox("Filtrar por estado", ["Todos"] + ESTADOS_PREFACTURA, key="fac_filtro")
            filtradas = prefacturas if estado_filtro == "Todos" else [p for p in prefacturas if p.get("estado") == estado_filtro]

            if XLSX_DISPONIBLE and filtradas:
                excel_data = exportar_prefacturas_excel(filtradas, empresa_nombre)
                st.download_button("📥 Exportar Excel", data=excel_data, file_name=f"prefacturas_{empresa_nombre.replace(' ', '_')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

            for p in filtradas:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1.5, 1.5])
                    with c1:
                        estado_icono = {"Pendiente": "🟡", "Cobrada": "🟢", "Anulada": "⚫", "Parcial": "🟠"}.get(p.get("estado", ""), "⚪")
                        st.markdown(f"{estado_icono} **{p.get('numero', '—')}** — {p.get('cliente_nombre', '—')}")
                        st.caption(f"DNI: {p.get('cliente_dni', '—')}  ·  {fmt_fecha(p.get('fecha', ''))}  ·  {fmt_moneda(p.get('total', 0))}")
                    with c2:
                        nuevo_estado = st.selectbox("Estado", ESTADOS_PREFACTURA, index=ESTADOS_PREFACTURA.index(p.get("estado", "Pendiente")) if p.get("estado") in ESTADOS_PREFACTURA else 0, key=f"fac_est_{p.get('id')}", label_visibility="collapsed")
                        if nuevo_estado != p.get("estado"):
                            p["estado"] = nuevo_estado
                            upsert_prefactura(p)
                            st.rerun()
                    with c3:
                        bcol1, bcol2 = st.columns(2)
                        with bcol1:
                            if FPDF_DISPONIBLE:
                                pdf_data = exportar_prefactura_pdf(p, empresa_nombre, p.get("items", []))
                                st.download_button("📄 PDF", data=pdf_data, file_name=f"prefactura_{p.get('numero', '')}.pdf", mime="application/pdf", key=f"pdf_fac_{p.get('id')}", use_container_width=True)
                        with bcol2:
                            if st.button("🗑️", key=f"del_fac_{p.get('id')}", use_container_width=True):
                                delete_prefactura(p.get("id"))
                                st.toast("Pre-factura eliminada.", icon="🗑️")
                                st.rerun()

                    if st.button("✏️ Editar", key=f"edit_fac_{p.get('id')}"):
                        st.session_state["fac_editing"] = p.get("id")
                        st.rerun()
                    if st.session_state.get("fac_editing") == p.get("id"):
                        st.divider()
                        st.session_state["fac_items"] = p.get("items", [])
                        data = _form_prefactura(p)
                        if data:
                            upsert_prefactura(data)
                            st.session_state.pop("fac_editing", None)
                            st.session_state.pop("fac_items", None)
                            st.toast("Pre-factura actualizada.", icon="✅")
                            st.rerun()

    with tab2:
        st.session_state.pop("fac_items", None)
        data = _form_prefactura()
        if data:
            result = upsert_prefactura(data)
            if result:
                st.session_state.pop("fac_items", None)
                st.toast("Pre-factura creada.", icon="✅")
                st.rerun()
            else:
                st.error("Error al guardar.")
