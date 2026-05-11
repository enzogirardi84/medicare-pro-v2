"""Vista de Cobros."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict

import streamlit as st

from core.db_sql import delete_cobro, get_clientes, get_cobros, get_prefacturas, upsert_cobro, upsert_prefactura
from core.excel_export import XLSX_DISPONIBLE, exportar_cobros_excel
from core.pdf_export import FPDF_DISPONIBLE, exportar_recibo_cobro_pdf, exportar_reporte_cobros_pdf
from core.billing_logic import (
    estado_prefactura_por_saldo,
    enriquecer_prefacturas_con_saldo,
    prefacturas_con_saldo,
    saldo_prefactura,
)
from core.utils import agrupar_por_mes, bloque_estado_vacio, calcular_total, fmt_fecha, fmt_moneda, generar_id, mostrar_error_db, sanitize_filename

METODOS_PAGO = ["Efectivo", "Transferencia", "Tarjeta de Credito", "Tarjeta de Debito", "Cheque", "Mercado Pago", "Otro"]
ESTADOS_COBRO = ["Cobrado", "Pendiente", "Parcial", "Anulado"]


def _parse_date(value: Any, default: date) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return default


def _sync_prefactura(prefactura_id: str) -> bool:
    if not prefactura_id:
        return True
    empresa_id = st.session_state.get("billing_empresa_id", "")
    prefacturas = get_prefacturas(empresa_id)
    cobros = get_cobros(empresa_id)
    prefactura = next((p for p in prefacturas if str(p.get("id", "")) == str(prefactura_id)), None)
    if not prefactura:
        return True
    updated = dict(prefactura)
    updated["estado"] = estado_prefactura_por_saldo(prefactura, cobros)
    return bool(upsert_prefactura(updated))


def _form_cobro(existing: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    clientes = get_clientes(st.session_state.get("billing_empresa_id", ""))
    cliente_opts = {c["nombre"]: c for c in clientes}
    if not cliente_opts:
        st.warning("Primero carga un cliente fiscal para registrar cobros.")
        return None

    empresa_id = st.session_state.get("billing_empresa_id", "")
    prefacturas = get_prefacturas(empresa_id)
    cobros = get_cobros(empresa_id)
    prefacturas_pendientes = prefacturas_con_saldo(prefacturas, cobros)
    form_id = existing.get("id", "new") if existing else "new"

    with st.form(f"cobro_form_{form_id}", border=True):
        st.markdown(f"### {'Editar cobro' if existing else 'Nuevo cobro'}")
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
            fecha = st.date_input("Fecha de cobro", value=_parse_date(existing.get("fecha") if existing else "", date.today()))

        c3, c4 = st.columns(2)
        with c3:
            monto = st.number_input("Monto $ *", min_value=0.0, value=float(existing.get("monto", 0) or 0) if existing else 0.0, step=100.0)
        with c4:
            metodo = st.selectbox(
                "Metodo de pago",
                METODOS_PAGO,
                index=METODOS_PAGO.index(existing.get("metodo_pago", "Efectivo")) if existing and existing.get("metodo_pago") in METODOS_PAGO else 0,
            )

        concepto = st.text_input("Concepto", value=existing.get("concepto", "") if existing else "", placeholder="Ej: Pago honorarios marzo 2026")
        fac_opts = {
            (
                f"{p.get('numero', '')} | {p.get('cliente_nombre', '')} | "
                f"Saldo {fmt_moneda(p.get('saldo', 0))}"
            ): p
            for p in prefacturas_pendientes
        }
        fac_sel = st.selectbox("Vincular a pre-factura (opcional)", options=["Ninguna"] + list(fac_opts.keys())) if fac_opts else "Ninguna"
        if fac_sel != "Ninguna":
            fac_preview = fac_opts.get(fac_sel, {})
            st.caption(
                "Total: "
                f"{fmt_moneda(fac_preview.get('total', 0))} | "
                f"Cobrado: {fmt_moneda(fac_preview.get('cobrado', 0))} | "
                f"Saldo: {fmt_moneda(fac_preview.get('saldo', 0))}"
            )
        notas = st.text_area("Notas", value=existing.get("notas", "") if existing else "", height=70)

        submitted = st.form_submit_button("Guardar cobro", use_container_width=True, type="primary")
        if submitted:
            if not cliente_sel:
                st.error("Selecciona un cliente.")
                return None
            if monto <= 0:
                st.error("El monto debe ser mayor a cero.")
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
                "concepto": concepto.strip() or "Cobro",
                "estado": existing.get("estado", "Cobrado") if existing else "Cobrado",
                "notas": notas.strip(),
            }
            if fac_sel != "Ninguna":
                fac_data = dict(fac_opts.get(fac_sel, {}))
                if fac_data:
                    saldo = saldo_prefactura(fac_data, cobros)
                    if monto - saldo > 0.01:
                        st.error(f"El monto supera el saldo de la pre-factura ({fmt_moneda(saldo)}).")
                        return None
                    data["prefactura_id"] = fac_data.get("id")
                    projected_cobros = cobros + [data]
                    fac_data["estado"] = estado_prefactura_por_saldo(fac_data, projected_cobros)
                    if not upsert_prefactura(fac_data):
                        mostrar_error_db("actualizar la pre-factura vinculada")
                        return None
            return data
    return None


def render_cobros() -> None:
    st.markdown("## Cobros")
    st.caption("Registra pagos recibidos y mantiene trazabilidad por cliente, metodo y mes.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    cobros = get_cobros(empresa_id)
    prefacturas_por_id = {
        str(p.get("id", "")): p
        for p in enriquecer_prefacturas_con_saldo(get_prefacturas(empresa_id), cobros)
    }

    tab1, tab2 = st.tabs(["Historial", "Nuevo cobro"])

    with tab1:
        if not cobros:
            bloque_estado_vacio("Sin cobros registrados", "Registra tu primer cobro desde la pestaña Nuevo cobro.")
        else:
            cf1, cf2, cf3, cf4, cf5 = st.columns([1, 1, 2, 1, 1])
            with cf1:
                metodo_filtro = st.selectbox("Metodo", ["Todos"] + METODOS_PAGO)
            with cf2:
                estado_filtro = st.selectbox("Estado", ["Todos"] + ESTADOS_COBRO)
            with cf3:
                busqueda = st.text_input("Buscar", placeholder="Cliente o concepto...").strip().lower()
            with cf4:
                fecha_desde = st.date_input("Desde", value=None, key="cob_fecha_desde")
            with cf5:
                fecha_hasta = st.date_input("Hasta", value=None, key="cob_fecha_hasta")

            filtrados = cobros
            if metodo_filtro != "Todos":
                filtrados = [c for c in filtrados if c.get("metodo_pago") == metodo_filtro]
            if estado_filtro != "Todos":
                filtrados = [c for c in filtrados if c.get("estado") == estado_filtro]
            if fecha_desde:
                filtrados = [c for c in filtrados if str(c.get("fecha", ""))[:10] >= fecha_desde.isoformat()]
            if fecha_hasta:
                filtrados = [c for c in filtrados if str(c.get("fecha", ""))[:10] <= fecha_hasta.isoformat()]
            if busqueda:
                filtrados = [
                    c for c in filtrados
                    if busqueda in str(c.get("cliente_nombre", "")).lower()
                    or busqueda in str(c.get("concepto", "")).lower()
                ]

            total_cobrado = calcular_total(filtrados, "monto")
            st.metric("Total cobrado", fmt_moneda(total_cobrado))
            if XLSX_DISPONIBLE and filtrados:
                st.download_button(
                    "Exportar Excel",
                    data=exportar_cobros_excel(filtrados, empresa_nombre),
                    file_name=f"cobros_{sanitize_filename(empresa_nombre)}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            agrupados = agrupar_por_mes(filtrados)
            with st.container(height=650, border=False):
                for mes, items in agrupados.items():
                    mes_total = calcular_total(items, "monto")
                    with st.expander(f"{mes} | {len(items)} cobro(s) | {fmt_moneda(mes_total)}", expanded=len(agrupados) <= 2):
                        if FPDF_DISPONIBLE:
                            st.download_button(
                                "PDF del mes",
                                data=exportar_reporte_cobros_pdf(items, empresa_nombre, f"{mes}-01", f"{mes}-31"),
                                file_name=f"cobros_{sanitize_filename(mes)}.pdf",
                                mime="application/pdf",
                                use_container_width=True,
                                key=f"pdf_cob_mes_{mes}",
                            )
                        for cobro in items:
                            cid = cobro.get("id")
                            with st.container(border=True):
                                cc1, cc2, cc3 = st.columns([3, 1.2, 1.2])
                                with cc1:
                                    st.markdown(f"**{cobro.get('cliente_nombre', '-')}** | {fmt_moneda(cobro.get('monto', 0))}")
                                    st.caption(f"{fmt_fecha(cobro.get('fecha', ''))} | {cobro.get('metodo_pago', '')} | {cobro.get('concepto', '-')}")
                                    if cobro.get("prefactura_id"):
                                        pref = prefacturas_por_id.get(str(cobro.get("prefactura_id", "")), {})
                                        st.caption(f"Pre-factura vinculada: {pref.get('numero', cobro.get('prefactura_id'))}")
                                with cc2:
                                    nuevo_estado = st.selectbox(
                                        "Estado",
                                        ESTADOS_COBRO,
                                        index=ESTADOS_COBRO.index(cobro.get("estado", "Cobrado")) if cobro.get("estado") in ESTADOS_COBRO else 0,
                                        key=f"cob_est_{cid}",
                                        label_visibility="collapsed",
                                    )
                                    if nuevo_estado != cobro.get("estado"):
                                        updated = dict(cobro)
                                        updated["estado"] = nuevo_estado
                                        if upsert_cobro(updated):
                                            if updated.get("prefactura_id") and not _sync_prefactura(updated.get("prefactura_id", "")):
                                                mostrar_error_db("recalcular la pre-factura vinculada")
                                                return
                                            st.toast("Estado actualizado.")
                                            st.rerun()
                                        else:
                                            mostrar_error_db("actualizar el cobro")
                                with cc3:
                                    pref = prefacturas_por_id.get(str(cobro.get("prefactura_id", "")), {})
                                    if FPDF_DISPONIBLE:
                                        st.download_button(
                                            "Recibo",
                                            data=exportar_recibo_cobro_pdf(
                                                cobro,
                                                empresa_nombre,
                                                pref,
                                                float(pref.get("saldo", 0) or 0) if pref else 0,
                                            ),
                                            file_name=f"recibo_{sanitize_filename(str(cid))}.pdf",
                                            mime="application/pdf",
                                            key=f"pdf_recibo_{cid}",
                                            use_container_width=True,
                                        )
                                    confirm = st.checkbox("Borrar", key=f"confirm_del_cob_{cid}")
                                    if st.button("Eliminar", key=f"del_cob_{cid}", use_container_width=True, disabled=not confirm):
                                        prefactura_id = cobro.get("prefactura_id", "")
                                        if delete_cobro(cid):
                                            if prefactura_id and not _sync_prefactura(prefactura_id):
                                                mostrar_error_db("recalcular la pre-factura vinculada")
                                                return
                                            st.toast("Cobro eliminado.")
                                            st.rerun()
                                        else:
                                            mostrar_error_db("eliminar el cobro")

    with tab2:
        data = _form_cobro()
        if data:
            if upsert_cobro(data):
                st.toast("Cobro registrado.")
                st.rerun()
            else:
                mostrar_error_db("guardar el cobro")
