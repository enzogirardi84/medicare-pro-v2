"""Vista de Presupuestos."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict

import streamlit as st

from core.db_sql import delete_presupuesto, get_clientes, get_presupuestos, upsert_prefactura, upsert_presupuesto
from core.excel_export import XLSX_DISPONIBLE, exportar_presupuestos_excel
from core.pdf_export import FPDF_DISPONIBLE, exportar_presupuesto_pdf
from core.utils import bloque_estado_vacio, fmt_fecha, fmt_moneda, generar_id, hoy, mostrar_error_db, sanitize_filename

ESTADOS_PRESUPUESTO = ["Borrador", "Enviado", "Aceptado", "Rechazado", "Vencido", "Convertido"]


def _parse_date(value: Any, default: date) -> date:
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return default


def _form_presupuesto(existing: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    es_edicion = existing is not None
    clientes = get_clientes(st.session_state.get("billing_empresa_id", ""))
    cliente_opts = {c["nombre"]: c for c in clientes}
    if not cliente_opts:
        st.warning("Primero carga un cliente fiscal para poder crear presupuestos.")
        return None

    base_items = existing.get("items", []) if existing else []
    form_id = existing.get("id", "new") if existing else "new"
    item_count = st.number_input(
        "Cantidad de conceptos",
        min_value=1,
        max_value=20,
        value=max(1, len(base_items) or 1),
        key=f"pres_item_count_{form_id}",
    )

    with st.form(f"pres_form_{form_id}", border=True):
        st.markdown(f"### {'Editar presupuesto' if es_edicion else 'Nuevo presupuesto'}")
        c1, c2, c3 = st.columns(3)
        cliente_names = list(cliente_opts.keys())
        with c1:
            cliente_sel = st.selectbox(
                "Cliente *",
                options=[""] + cliente_names,
                index=cliente_names.index(existing.get("cliente_nombre", "")) + 1
                if existing and existing.get("cliente_nombre") in cliente_opts
                else 0,
            )
        with c2:
            fecha = st.date_input("Fecha", value=_parse_date(existing.get("fecha") if existing else "", date.today()))
        with c3:
            valido_default = _parse_date(existing.get("valido_hasta") if existing else "", fecha + timedelta(days=15))
            valido = st.date_input("Valido hasta", value=valido_default)

        st.markdown("#### Conceptos")
        items = []
        for i in range(int(item_count)):
            base = base_items[i] if i < len(base_items) and isinstance(base_items[i], dict) else {}
            ic1, ic2, ic3, ic4 = st.columns([3, 1, 1.2, 0.7])
            with ic1:
                concepto = st.text_input(
                    "Concepto",
                    value=base.get("concepto", ""),
                    key=f"pres_conc_{form_id}_{i}",
                    placeholder="Ej: Consulta cardiologica",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with ic2:
                cantidad = st.number_input(
                    "Cant.",
                    min_value=1.0,
                    value=float(base.get("cantidad", 1) or 1),
                    step=1.0,
                    key=f"pres_cant_{form_id}_{i}",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with ic3:
                precio = st.number_input(
                    "Precio $",
                    min_value=0.0,
                    value=float(base.get("precio_unitario", 0) or 0),
                    step=100.0,
                    key=f"pres_precio_{form_id}_{i}",
                    label_visibility="collapsed" if i > 0 else "visible",
                )
            with ic4:
                st.caption(fmt_moneda(cantidad * precio))
            if concepto.strip():
                items.append({"concepto": concepto.strip(), "cantidad": cantidad, "precio_unitario": precio})

        total = sum(float(it["cantidad"]) * float(it["precio_unitario"]) for it in items)
        st.markdown(f"**Total: {fmt_moneda(total)}**")
        notas = st.text_area("Notas", value=existing.get("notas", "") if existing else "", height=70)

        submitted = st.form_submit_button("Guardar presupuesto", use_container_width=True, type="primary")
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
            if valido < fecha:
                st.error("La fecha de validez no puede ser anterior a la fecha del presupuesto.")
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
    st.markdown("## Presupuestos")
    st.caption("Crea presupuestos profesionales, exportalos y convertilos en pre-facturas.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    presupuestos = get_presupuestos(empresa_id)

    tab1, tab2 = st.tabs(["Historial", "Nuevo presupuesto"])

    with tab1:
        if not presupuestos:
            bloque_estado_vacio("Sin presupuestos", "Crea tu primer presupuesto desde la pestaña Nuevo presupuesto.")
        else:
            f1, f2, f3, f4 = st.columns([2, 1, 1, 1])
            with f1:
                busqueda = st.text_input("Buscar", placeholder="Numero o cliente...").strip().lower()
            with f2:
                estado_filtro = st.selectbox("Estado", ["Todos"] + ESTADOS_PRESUPUESTO)
            with f3:
                fecha_desde = st.date_input("Desde", value=None, key="pres_fecha_desde")
            with f4:
                fecha_hasta = st.date_input("Hasta", value=None, key="pres_fecha_hasta")
            filtrados = presupuestos
            if estado_filtro != "Todos":
                filtrados = [p for p in filtrados if p.get("estado") == estado_filtro]
            if fecha_desde:
                filtrados = [p for p in filtrados if str(p.get("fecha", ""))[:10] >= fecha_desde.isoformat()]
            if fecha_hasta:
                filtrados = [p for p in filtrados if str(p.get("fecha", ""))[:10] <= fecha_hasta.isoformat()]
            if busqueda:
                filtrados = [
                    p
                    for p in filtrados
                    if busqueda in str(p.get("numero", "")).lower()
                    or busqueda in str(p.get("cliente_nombre", "")).lower()
                ]

            st.metric("Total filtrado", fmt_moneda(sum(float(p.get("total", 0) or 0) for p in filtrados)))
            if XLSX_DISPONIBLE and filtrados:
                st.download_button(
                    "Exportar Excel",
                    data=exportar_presupuestos_excel(filtrados, empresa_nombre),
                    file_name=f"presupuestos_{sanitize_filename(empresa_nombre)}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            with st.container(height=610, border=False):
                for p in filtrados:
                    pid = p.get("id")
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3, 1.3, 1.7])
                        with c1:
                            st.markdown(f"**{p.get('numero', '-')}** | {p.get('cliente_nombre', '-')}")
                            st.caption(f"{fmt_fecha(p.get('fecha', ''))} | Vence: {fmt_fecha(p.get('valido_hasta', ''))} | {fmt_moneda(p.get('total', 0))}")
                        with c2:
                            nuevo_estado = st.selectbox(
                                "Estado",
                                ESTADOS_PRESUPUESTO,
                                index=ESTADOS_PRESUPUESTO.index(p.get("estado", "Borrador")) if p.get("estado") in ESTADOS_PRESUPUESTO else 0,
                                key=f"pres_est_{pid}",
                                label_visibility="collapsed",
                            )
                            if nuevo_estado != p.get("estado"):
                                updated = dict(p)
                                updated["estado"] = nuevo_estado
                                if upsert_presupuesto(updated):
                                    st.toast("Estado actualizado.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("actualizar el estado")
                        with c3:
                            b1, b2, b3 = st.columns(3)
                            with b1:
                                if FPDF_DISPONIBLE:
                                    st.download_button(
                                        "PDF",
                                        data=exportar_presupuesto_pdf(p, empresa_nombre, p.get("items", [])),
                                        file_name=f"presupuesto_{sanitize_filename(p.get('numero', ''))}.pdf",
                                        mime="application/pdf",
                                        key=f"pdf_pres_{pid}",
                                        use_container_width=True,
                                    )
                            with b2:
                                if st.button("Editar", key=f"edit_pres_{pid}", use_container_width=True):
                                    st.session_state["pres_editing"] = pid
                                    st.rerun()
                            with b3:
                                confirm = st.checkbox("OK", key=f"confirm_del_pres_{pid}")
                                if st.button("Borrar", key=f"del_pres_{pid}", use_container_width=True, disabled=not confirm):
                                    if delete_presupuesto(pid):
                                        st.toast("Presupuesto eliminado.")
                                        st.rerun()
                                    else:
                                        mostrar_error_db("eliminar el presupuesto")

                        if p.get("estado") == "Aceptado":
                            if st.button("Convertir a pre-factura", key=f"conv_pres_{pid}", use_container_width=True):
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
                                    "presupuesto_origen": pid,
                                    "notas": p.get("notas", ""),
                                }
                                converted = dict(p)
                                converted["estado"] = "Convertido"
                                if upsert_prefactura(prefactura_data) and upsert_presupuesto(converted):
                                    st.toast("Pre-factura generada.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("convertir el presupuesto")

                        if st.session_state.get("pres_editing") == pid:
                            st.divider()
                            data = _form_presupuesto(p)
                            if data:
                                if upsert_presupuesto(data):
                                    st.session_state.pop("pres_editing", None)
                                    st.toast("Presupuesto actualizado.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("actualizar el presupuesto")

    with tab2:
        data = _form_presupuesto()
        if data:
            if upsert_presupuesto(data):
                st.toast("Presupuesto creado.")
                st.rerun()
            else:
                mostrar_error_db("guardar el presupuesto")
