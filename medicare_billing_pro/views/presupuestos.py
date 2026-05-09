"""Vista de Presupuestos — creación, edición, envío y conversión a pre-factura."""
from __future__ import annotations

import json
from datetime import date, timedelta
from typing import Any, Dict, List

import streamlit as st

from core.db_sql import get_clientes, get_presupuestos, upsert_presupuesto, delete_presupuesto, upsert_prefactura
from core.utils import generar_id, hoy, fmt_moneda, fmt_fecha, bloque_estado_vacio, calcular_total
from core.pdf_export import exportar_presupuesto_pdf, FPDF_DISPONIBLE
from core.excel_export import exportar_presupuestos_excel, XLSX_DISPONIBLE

ESTADOS_PRESUPUESTO = ["Borrador", "Enviado", "Aceptado", "Rechazado", "Vencido", "Convertido"]


def _form_presupuesto(existing: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    es_edicion = existing is not None
    clientes = get_clientes(st.session_state.get("billing_empresa_id", ""))
    cliente_opts = {c["nombre"]: c for c in clientes}
    base_items = existing.get("items", []) if existing else []
    item_count = st.number_input(
        "Cantidad de conceptos",
        min_value=1,
        max_value=20,
        value=max(1, len(base_items) or 1),
        key=f"pres_item_count_{existing.get('id') if existing else 'new'}",
    )

    with st.form(f"pres_form_{'edit' if es_edicion else 'new'}", border=True):
        st.markdown(f"### {'✏️ Editar' if es_edicion else '📝 Nuevo'} Presupuesto")
        c1, c2, c3 = st.columns(3)
        with c1:
            cliente_sel = st.selectbox(
                "Cliente *",
                options=[""] + list(cliente_opts.keys()),
                index=0 if not existing else list(cliente_opts.keys()).index(existing.get("cliente_nombre", "")) + 1 if existing.get("cliente_nombre") in cliente_opts else 0,
                key="pres_cliente",
            )
        with c2:
            fecha = st.date_input("Fecha", value=date.today() if not existing else date.fromisoformat(str(existing.get("fecha", str(hoy())))[:10]), key="pres_fecha")
        with c3:
            valido = st.date_input("Válido hasta", value=fecha + timedelta(days=15), key="pres_valido")

        # Items
        st.markdown("#### Conceptos")
        items = []
        for i in range(int(item_count)):
            item = base_items[i] if i < len(base_items) and isinstance(base_items[i], dict) else {"concepto": "", "cantidad": 1, "precio_unitario": 0.0}
            ic1, ic2, ic3, ic4 = st.columns([3, 1, 1.2, 0.6])
            with ic1:
                item["concepto"] = st.text_input("Concepto", value=item.get("concepto", ""), key=f"pres_conc_{i}", label_visibility="collapsed" if i > 0 else "visible", placeholder="Ej: Consulta cardiológica")
            with ic2:
                item["cantidad"] = st.number_input("Cant.", min_value=1, value=int(item.get("cantidad", 1)), key=f"pres_cant_{i}", label_visibility="collapsed" if i > 0 else "visible")
            with ic3:
                item["precio_unitario"] = st.number_input("Precio $", min_value=0.0, value=float(item.get("precio_unitario", 0)), step=100.0, key=f"pres_precio_{i}", label_visibility="collapsed" if i > 0 else "visible")
            with ic4:
                st.markdown(f"<small style='color:#64748b'>${item['cantidad'] * item['precio_unitario']:,.0f}</small>", unsafe_allow_html=True)
            items.append(item)

        items = [it for it in items if str(it.get("concepto", "")).strip()]
        total = sum(it["cantidad"] * it["precio_unitario"] for it in items)
        st.markdown(f"**Total: {fmt_moneda(total)}**")

        notas = st.text_area("Notas", value=existing.get("notas", "") if existing else "", key="pres_notas", height=60)

        submitted = st.form_submit_button("💾 Guardar Presupuesto", use_container_width=True, type="primary")
        if submitted:
            if not cliente_sel:
                st.error("Seleccioná un cliente.")
                return None
            cliente_data = cliente_opts.get(cliente_sel, {})
            return {
                "id": existing.get("id") if existing else generar_id(),
                "empresa_id": st.session_state.get("billing_empresa_id", ""),
                "numero": existing.get("numero") if existing else f"PRES-{generar_id()[:6].upper()}",
                "cliente_id": cliente_data.get("id", ""),
                "cliente_nombre": cliente_sel,
                "fecha": fecha.isoformat(),
                "valido_hasta": valido.isoformat(),
                "items": items,
                "total": total,
                "estado": existing.get("estado", "Borrador") if existing else "Borrador",
                "notas": notas.strip(),
            }
    return None


def render_presupuestos() -> None:
    st.markdown("## 📝 Presupuestos")
    st.caption("Creá presupuestos profesionales, envialos y convertilos en pre-facturas.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    presupuestos = get_presupuestos(empresa_id)

    tab1, tab2 = st.tabs(["📋 Historial", "➕ Nuevo Presupuesto"])

    with tab1:
        if not presupuestos:
            bloque_estado_vacio("Sin presupuestos", "Creá tu primer presupuesto desde la pestaña «Nuevo Presupuesto».")
        else:
            estado_filtro = st.selectbox("Filtrar por estado", ["Todos"] + ESTADOS_PRESUPUESTO, key="pres_filtro")
            filtrados = presupuestos if estado_filtro == "Todos" else [p for p in presupuestos if p.get("estado") == estado_filtro]

            if XLSX_DISPONIBLE and filtrados:
                excel_data = exportar_presupuestos_excel(filtrados, empresa_nombre)
                st.download_button("📥 Exportar Excel", data=excel_data, file_name=f"presupuestos_{empresa_nombre.replace(' ', '_')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

            for p in filtrados:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1.5, 1.5])
                    with c1:
                        estado_color = {"Borrador": "⚪", "Enviado": "🔵", "Aceptado": "🟢", "Rechazado": "🔴", "Vencido": "🟠", "Convertido": "🟣"}.get(p.get("estado", ""), "⚪")
                        st.markdown(f"{estado_color} **{p.get('numero', '—')}** — {p.get('cliente_nombre', '—')}")
                        st.caption(f"{fmt_fecha(p.get('fecha', ''))}  ·  Vence: {fmt_fecha(p.get('valido_hasta', ''))}  ·  {fmt_moneda(p.get('total', 0))}")
                    with c2:
                        nuevo_estado = st.selectbox("Estado", ESTADOS_PRESUPUESTO, index=ESTADOS_PRESUPUESTO.index(p.get("estado", "Borrador")) if p.get("estado") in ESTADOS_PRESUPUESTO else 0, key=f"pres_est_{p.get('id')}", label_visibility="collapsed")
                        if nuevo_estado != p.get("estado"):
                            p["estado"] = nuevo_estado
                            upsert_presupuesto(p)
                            st.rerun()
                    with c3:
                        bcol1, bcol2 = st.columns(2)
                        with bcol1:
                            if FPDF_DISPONIBLE:
                                pdf_data = exportar_presupuesto_pdf(p, empresa_nombre, p.get("items", []))
                                st.download_button("📄 PDF", data=pdf_data, file_name=f"presupuesto_{p.get('numero', '')}.pdf", mime="application/pdf", key=f"pdf_pres_{p.get('id')}", use_container_width=True)
                        with bcol2:
                            if st.button("🗑️", key=f"del_pres_{p.get('id')}", use_container_width=True):
                                delete_presupuesto(p.get("id"))
                                st.toast("Presupuesto eliminado.", icon="🗑️")
                                st.rerun()

                    # Convertir a pre-factura
                    if p.get("estado") == "Aceptado":
                        if st.button("📋 Convertir a Pre-factura", key=f"conv_pres_{p.get('id')}", use_container_width=True):
                            prefactura_data = {
                                "id": generar_id(),
                                "empresa_id": empresa_id,
                                "numero": f"FAC-{generar_id()[:6].upper()}",
                                "cliente_id": p.get("cliente_id", ""),
                                "cliente_nombre": p.get("cliente_nombre", ""),
                                "cliente_dni": "",
                                "fecha": hoy().isoformat(),
                                "items": p.get("items", []),
                                "total": p.get("total", 0),
                                "estado": "Pendiente",
                                "presupuesto_origen": p.get("id"),
                                "notas": p.get("notas", ""),
                            }
                            upsert_prefactura(prefactura_data)
                            p["estado"] = "Convertido"
                            upsert_presupuesto(p)
                            st.toast("Pre-factura generada.", icon="📋")
                            st.rerun()

                    # Editar
                    if st.button("✏️ Editar", key=f"edit_pres_{p.get('id')}"):
                        st.session_state["pres_editing"] = p.get("id")
                        st.rerun()
                    if st.session_state.get("pres_editing") == p.get("id"):
                        st.divider()
                        st.session_state["pres_items"] = p.get("items", [])
                        data = _form_presupuesto(p)
                        if data:
                            upsert_presupuesto(data)
                            st.session_state.pop("pres_editing", None)
                            st.session_state.pop("pres_items", None)
                            st.toast("Presupuesto actualizado.", icon="✅")
                            st.rerun()

    with tab2:
        st.session_state.pop("pres_items", None)
        data = _form_presupuesto()
        if data:
            result = upsert_presupuesto(data)
            if result:
                st.session_state.pop("pres_items", None)
                st.toast("Presupuesto creado.", icon="✅")
                st.rerun()
            else:
                st.error("Error al guardar.")
