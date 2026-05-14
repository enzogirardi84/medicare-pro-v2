"""Vista de Pre-facturas."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict

import streamlit as st

from core.db_sql import delete_prefactura, get_clientes, get_prefacturas, upsert_prefactura
from core.excel_export import XLSX_DISPONIBLE, exportar_prefacturas_excel
from core.pdf_export import FPDF_DISPONIBLE, exportar_prefactura_pdf
from core.billing_logic import enriquecer_prefacturas_con_saldo, money
from core.utils import bloque_estado_vacio, fmt_fecha, fmt_moneda, generar_id, mostrar_error_db, sanitize_filename

ESTADOS_PREFACTURA = ["Pendiente", "Cobrada", "Anulada", "Parcial"]


def _parse_date(value: Any, default: date) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return default


def _form_prefactura(existing: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    clientes = get_clientes(st.session_state.get("billing_empresa_id", ""))
    cliente_opts = {c["nombre"]: c for c in clientes}
    if not cliente_opts:
        st.warning("Primero carga un cliente fiscal para poder crear pre-facturas.")
        return None

    base_items = existing.get("items", []) if existing else []
    form_id = existing.get("id", "new") if existing else "new"
    item_count = st.number_input(
        "Cantidad de conceptos",
        min_value=1,
        max_value=20,
        value=max(1, len(base_items) or 1),
        key=f"fac_item_count_{form_id}",
    )

    with st.form(f"fac_form_{form_id}", border=True):
        st.markdown(f"### {'Editar pre-factura' if existing else 'Nueva pre-factura'}")
        c1, c2 = st.columns(2)
        names = list(cliente_opts.keys())
        with c1:
            cliente_sel = st.selectbox(
                "Cliente *",
                options=[""] + names,
                index=names.index(existing.get("cliente_nombre", "")) + 1
                if existing and existing.get("cliente_nombre") in cliente_opts
                else 0,
            )
        with c2:
            fecha = st.date_input("Fecha", value=_parse_date(existing.get("fecha") if existing else "", date.today()))

        st.markdown("#### Conceptos")
        items = []
        for i in range(int(item_count)):
            base = base_items[i] if i < len(base_items) and isinstance(base_items[i], dict) else {}
            ic1, ic2, ic3, ic4 = st.columns([3, 1, 1.2, 0.7])
            with ic1:
                concepto = st.text_input(
                    "Concepto",
                    value=base.get("concepto", ""),
                    key=f"fac_conc_{form_id}_{i}",
                    placeholder="Ej: Honorarios medicos marzo",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with ic2:
                cantidad = st.number_input("Cant.", min_value=1.0, value=float(base.get("cantidad", 1) or 1), step=1.0, key=f"fac_cant_{form_id}_{i}", label_visibility="collapsed" if i > 0 else "visible")
            with ic3:
                precio = st.number_input("Precio $", min_value=0.0, value=float(base.get("precio_unitario", 0) or 0), step=100.0, key=f"fac_precio_{form_id}_{i}", label_visibility="collapsed" if i > 0 else "visible")
            with ic4:
                st.caption(fmt_moneda(cantidad * precio))
            if concepto.strip():
                items.append({"concepto": concepto.strip(), "cantidad": cantidad, "precio_unitario": precio})

        total = sum(float(it["cantidad"]) * float(it["precio_unitario"]) for it in items)
        st.markdown(f"**Total: {fmt_moneda(total)}**")
        notas = st.text_area("Notas", value=existing.get("notas", "") if existing else "", height=70)

        submitted = st.form_submit_button("Guardar pre-factura", width='stretch', type="primary")
        if submitted:
            if not cliente_sel:
                st.error("Selecciona un cliente.")
                return None
            if not items:
                st.error("Agrega al menos un concepto.")
                return None
            if total <= 0:
                st.error("El total debe ser mayor a cero.")
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
    st.markdown("## Pre-facturas")
    st.caption("Documentos previos a la factura oficial, listos para cobrar y exportar.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    from core.db_sql import get_cobros

    cobros = get_cobros(empresa_id)
    prefacturas = enriquecer_prefacturas_con_saldo(get_prefacturas(empresa_id), cobros)

    tab1, tab2 = st.tabs(["Historial", "Nueva pre-factura"])

    with tab1:
        if not prefacturas:
            bloque_estado_vacio("Sin pre-facturas", "Crea tu primera pre-factura o converti un presupuesto aceptado.")
        else:
            f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
            with f1:
                busqueda = st.text_input("Buscar", placeholder="Numero, cliente o DNI/CUIT...").strip().lower()
            with f2:
                estado_filtro = st.selectbox("Estado", ["Todos"] + ESTADOS_PREFACTURA)
            with f3:
                fecha_desde = st.date_input("Desde", value=None, key="pref_fecha_desde")
            with f4:
                fecha_hasta = st.date_input("Hasta", value=None, key="pref_fecha_hasta")
            filtradas = prefacturas
            if estado_filtro != "Todos":
                filtradas = [p for p in filtradas if p.get("estado") == estado_filtro]
            if fecha_desde:
                filtradas = [p for p in filtradas if str(p.get("fecha", ""))[:10] >= fecha_desde.isoformat()]
            if fecha_hasta:
                filtradas = [p for p in filtradas if str(p.get("fecha", ""))[:10] <= fecha_hasta.isoformat()]
            if busqueda:
                filtradas = [
                    p
                    for p in filtradas
                    if busqueda in str(p.get("numero", "")).lower()
                    or busqueda in str(p.get("cliente_nombre", "")).lower()
                    or busqueda in str(p.get("cliente_dni", "")).lower()
                ]

            k1, k2, k3 = st.columns(3)
            k1.metric("Total filtrado", fmt_moneda(sum(money(p.get("total")) for p in filtradas)))
            k2.metric("Cobrado", fmt_moneda(sum(money(p.get("cobrado")) for p in filtradas)))
            k3.metric("Saldo", fmt_moneda(sum(money(p.get("saldo")) for p in filtradas)))
            if XLSX_DISPONIBLE and filtradas:
                st.download_button(
                    "Exportar Excel",
                    data=exportar_prefacturas_excel(filtradas, empresa_nombre),
                    file_name=f"prefacturas_{sanitize_filename(empresa_nombre)}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    width='stretch',
                )

            with st.container(height=610, border=False):
                for p in filtradas:
                    pid = p.get("id")
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3.2, 1.2, 2.4])
                        with c1:
                            st.markdown(f"**{p.get('numero', '-')}** | {p.get('cliente_nombre', '-')}")
                            st.caption(f"DNI/CUIT: {p.get('cliente_dni', '-')} | {fmt_fecha(p.get('fecha', ''))}")
                            st.caption(
                                f"Total: {fmt_moneda(p.get('total', 0))} | "
                                f"Cobrado: {fmt_moneda(p.get('cobrado', 0))} | "
                                f"Saldo: {fmt_moneda(p.get('saldo', 0))}"
                            )
                            if p.get("estado_calculado") and p.get("estado_calculado") != p.get("estado"):
                                st.caption(f"Estado sugerido por cobros: {p.get('estado_calculado')}")
                        with c2:
                            nuevo_estado = st.selectbox(
                                "Estado",
                                ESTADOS_PREFACTURA,
                                index=ESTADOS_PREFACTURA.index(p.get("estado", "Pendiente")) if p.get("estado") in ESTADOS_PREFACTURA else 0,
                                key=f"fac_est_{pid}",
                                label_visibility="collapsed",
                            )
                            if nuevo_estado != p.get("estado"):
                                updated = dict(p)
                                updated["estado"] = nuevo_estado
                                if upsert_prefactura(updated):
                                    st.toast("Estado actualizado.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("actualizar el estado")
                        with c3:
                            b1, b2, b3 = st.columns([1.2, 1, 1.15])
                            with b1:
                                if FPDF_DISPONIBLE:
                                    st.download_button(
                                        "Descargar PDF",
                                        data=exportar_prefactura_pdf(p, empresa_nombre, p.get("items", [])),
                                        file_name=f"prefactura_{sanitize_filename(p.get('numero', ''))}.pdf",
                                        mime="application/pdf",
                                        key=f"pdf_fac_{pid}",
                                        width='stretch',
                                    )
                            with b2:
                                if st.button("Editar", key=f"edit_fac_{pid}", width='stretch'):
                                    st.session_state["fac_editing"] = pid
                                    st.rerun()
                            with b3:
                                confirm = st.checkbox("Confirmar", key=f"confirm_del_fac_{pid}")
                                if st.button("Eliminar", key=f"del_fac_{pid}", width='stretch', disabled=not confirm):
                                    if delete_prefactura(pid):
                                        st.toast("Pre-factura eliminada.")
                                        st.rerun()
                                    else:
                                        mostrar_error_db("eliminar la pre-factura")

                        if st.session_state.get("fac_editing") == pid:
                            st.divider()
                            data = _form_prefactura(p)
                            if data:
                                if upsert_prefactura(data):
                                    st.session_state.pop("fac_editing", None)
                                    st.toast("Pre-factura actualizada.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("actualizar la pre-factura")

    with tab2:
        data = _form_prefactura()
        if data:
            if upsert_prefactura(data):
                st.toast("Pre-factura creada.")
                st.rerun()
            else:
                mostrar_error_db("guardar la pre-factura")
