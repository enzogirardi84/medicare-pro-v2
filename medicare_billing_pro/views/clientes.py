"""Vista de Clientes Fiscales."""
from __future__ import annotations

from typing import Any, Dict

import streamlit as st

from core.db_sql import delete_cliente, get_clientes, get_cobros, get_prefacturas, get_presupuestos, upsert_cliente
from core.excel_export import XLSX_DISPONIBLE, exportar_clientes_excel
from core.billing_logic import enriquecer_prefacturas_con_saldo, money
from core.utils import (
    bloque_estado_vacio,
    fmt_moneda,
    generar_id,
    is_valid_email,
    mostrar_error_db,
    normalize_document,
    normalize_phone,
    sanitize_filename,
)

CONDICIONES_FISCALES = [
    "Responsable Inscripto",
    "Monotributista",
    "Exento",
    "Consumidor Final",
    "No Categorizado",
]


def _form_cliente(existing: Dict[str, Any] | None = None, clientes: list[Dict[str, Any]] | None = None) -> Dict[str, Any]:
    es_edicion = existing is not None
    form_key = existing.get("id", "new") if existing else "new"
    with st.form(f"cliente_form_{form_key}", border=True):
        st.markdown(f"### {'Editar cliente' if es_edicion else 'Nuevo cliente'}")
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre / Razon Social *", value=existing.get("nombre", "") if existing else "")
            dni = st.text_input("DNI / CUIT *", value=existing.get("dni", "") if existing else "")
            email = st.text_input("Email", value=existing.get("email", "") if existing else "")
        with c2:
            telefono = st.text_input("Telefono", value=existing.get("telefono", "") if existing else "")
            direccion = st.text_input("Direccion", value=existing.get("direccion", "") if existing else "")
            condicion = st.selectbox(
                "Condicion Fiscal",
                options=CONDICIONES_FISCALES,
                index=CONDICIONES_FISCALES.index(existing.get("condicion_fiscal", "Consumidor Final"))
                if existing and existing.get("condicion_fiscal") in CONDICIONES_FISCALES
                else 3,
            )
        notas = st.text_area("Notas", value=existing.get("notas", "") if existing else "", height=74)

        submitted = st.form_submit_button("Guardar cliente", use_container_width=True, type="primary")
        if submitted:
            nombre = nombre.strip()
            dni = normalize_document(dni)
            email = email.strip().lower()
            if not nombre or not dni:
                st.error("Nombre y DNI/CUIT son obligatorios.")
                return {}
            if not is_valid_email(email):
                st.error("El email no tiene un formato valido.")
                return {}
            duplicado = next(
                (
                    c
                    for c in clientes or []
                    if normalize_document(c.get("dni", "")) == dni
                    and str(c.get("id", "")) != str(existing.get("id", "") if existing else "")
                ),
                None,
            )
            if duplicado:
                st.error(f"Ya existe un cliente con ese DNI/CUIT: {duplicado.get('nombre', '')}.")
                return {}
            return {
                "id": existing.get("id") if existing else generar_id(),
                "empresa_id": st.session_state.get("billing_empresa_id", ""),
                "nombre": nombre,
                "dni": dni,
                "email": email,
                "telefono": normalize_phone(telefono),
                "direccion": direccion.strip(),
                "condicion_fiscal": condicion,
                "notas": notas.strip(),
            }
    return {}


def render_clientes() -> None:
    st.markdown("## Clientes fiscales")
    st.caption("Datos impositivos de pacientes, obras sociales y terceros.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    clientes = get_clientes(empresa_id)
    presupuestos = get_presupuestos(empresa_id)
    prefacturas = enriquecer_prefacturas_con_saldo(get_prefacturas(empresa_id), get_cobros(empresa_id))
    cobros = get_cobros(empresa_id)

    tab1, tab2 = st.tabs(["Listado", "Nuevo cliente"])

    with tab1:
        if not clientes:
            bloque_estado_vacio(
                "Sin clientes cargados",
                "Todavia no registraste ningun cliente fiscal. Usa la pestaña Nuevo cliente para agregar el primero.",
                "Luego vas a poder usarlos en presupuestos, pre-facturas y cobros.",
            )
        else:
            top1, top2 = st.columns([2.4, 1])
            with top1:
                busqueda = st.text_input("Buscar cliente", placeholder="Nombre, DNI/CUIT, email o telefono...").strip().lower()
            filtrados = clientes
            if busqueda:
                filtrados = [
                    c
                    for c in clientes
                    if busqueda in str(c.get("nombre", "")).lower()
                    or busqueda in str(c.get("dni", "")).lower()
                    or busqueda in str(c.get("email", "")).lower()
                    or busqueda in str(c.get("telefono", "")).lower()
                ]
            with top2:
                st.metric("Clientes", len(filtrados))

            if XLSX_DISPONIBLE and filtrados:
                excel_data = exportar_clientes_excel(filtrados, empresa_nombre)
                st.download_button(
                    "Exportar Excel",
                    data=excel_data,
                    file_name=f"clientes_{sanitize_filename(empresa_nombre)}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            with st.container(height=610, border=False):
                for cliente in filtrados:
                    cliente_id = cliente.get("id")
                    with st.container(border=True):
                        c1, c2, c3, c4 = st.columns([3, 1, 1, 1])
                        with c1:
                            st.markdown(f"**{cliente.get('nombre', 'Sin nombre')}**")
                            st.caption(f"DNI/CUIT: {cliente.get('dni', '-')} | {cliente.get('condicion_fiscal', '-')}")
                            contacto = " | ".join(v for v in [cliente.get("email", ""), cliente.get("telefono", "")] if v)
                            if contacto:
                                st.caption(contacto)
                            cli_pres = [p for p in presupuestos if str(p.get("cliente_id", "")) == str(cliente_id)]
                            cli_pref = [p for p in prefacturas if str(p.get("cliente_id", "")) == str(cliente_id)]
                            cli_cobros = [c for c in cobros if str(c.get("cliente_id", "")) == str(cliente_id)]
                            with st.expander("Historial y saldo", expanded=False):
                                h1, h2, h3, h4 = st.columns(4)
                                h1.metric("Presupuestado", fmt_moneda(sum(money(p.get("total")) for p in cli_pres)))
                                h2.metric("Pre-facturado", fmt_moneda(sum(money(p.get("total")) for p in cli_pref)))
                                h3.metric("Cobrado", fmt_moneda(sum(money(c.get("monto")) for c in cli_cobros)))
                                h4.metric("Saldo", fmt_moneda(sum(money(p.get("saldo")) for p in cli_pref)))
                                ultimos = sorted(
                                    [
                                        {"Fecha": p.get("fecha", ""), "Tipo": "Presupuesto", "Numero": p.get("numero", ""), "Monto": fmt_moneda(p.get("total", 0))}
                                        for p in cli_pres
                                    ]
                                    + [
                                        {"Fecha": p.get("fecha", ""), "Tipo": "Pre-factura", "Numero": p.get("numero", ""), "Monto": fmt_moneda(p.get("total", 0))}
                                        for p in cli_pref
                                    ]
                                    + [
                                        {"Fecha": c.get("fecha", ""), "Tipo": "Cobro", "Numero": c.get("concepto", ""), "Monto": fmt_moneda(c.get("monto", 0))}
                                        for c in cli_cobros
                                    ],
                                    key=lambda row: str(row.get("Fecha", "")),
                                    reverse=True,
                                )[:6]
                                if ultimos:
                                    st.dataframe(ultimos, use_container_width=True, hide_index=True, height=210)
                                else:
                                    st.caption("Sin movimientos todavia.")
                        with c2:
                            if st.button("Cuenta", key=f"cc_cli_{cliente_id}", use_container_width=True):
                                st.session_state["cc_cliente_label"] = (
                                    f"{cliente.get('nombre', 'Sin nombre')} | {cliente.get('dni', '')}"
                                    if cliente.get("dni")
                                    else cliente.get("nombre", "Sin nombre")
                                )
                                st.session_state["billing_modulo_activo"] = "Cuenta corriente"
                                st.rerun()
                        with c3:
                            if st.button("Editar", key=f"edit_cli_{cliente_id}", use_container_width=True):
                                st.session_state["cli_editing"] = cliente_id
                                st.rerun()
                        with c4:
                            confirmar = st.checkbox("Confirmar", key=f"confirm_del_cli_{cliente_id}")
                            if st.button("Borrar", key=f"del_cli_{cliente_id}", use_container_width=True, disabled=not confirmar):
                                if delete_cliente(cliente_id):
                                    st.toast("Cliente eliminado.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("eliminar el cliente")

                        if st.session_state.get("cli_editing") == cliente_id:
                            st.divider()
                            data = _form_cliente(cliente, clientes)
                            if data:
                                if upsert_cliente(data):
                                    st.session_state.pop("cli_editing", None)
                                    st.toast("Cliente actualizado.")
                                    st.rerun()
                                else:
                                    mostrar_error_db("actualizar el cliente")

    with tab2:
        data = _form_cliente(clientes=clientes)
        if data:
            result = upsert_cliente(data)
            if result:
                st.toast("Cliente creado correctamente.")
                st.rerun()
            else:
                mostrar_error_db("guardar el cliente")
