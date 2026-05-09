"""Vista de Clientes Fiscales — ABM completo con datos impositivos."""
from __future__ import annotations

import json
from typing import Any, Dict, List

import streamlit as st

from core.db_sql import get_clientes, upsert_cliente, delete_cliente
from core.utils import generar_id, hoy, bloque_estado_vacio
from core.excel_export import exportar_clientes_excel, XLSX_DISPONIBLE

CONDICIONES_FISCALES = [
    "Responsable Inscripto",
    "Monotributista",
    "Exento",
    "Consumidor Final",
    "No Categorizado",
]


def _form_cliente(existing: Dict[str, Any] | None = None) -> Dict[str, Any]:
    """Formulario de alta/edición de cliente."""
    es_edicion = existing is not None
    with st.form(f"cliente_form_{'edit' if es_edicion else 'new'}", border=True):
        st.markdown(f"### {'✏️ Editar' if es_edicion else '➕ Nuevo'} Cliente")
        c1, c2 = st.columns(2)
        with c1:
            nombre = st.text_input("Nombre / Razón Social *", value=existing.get("nombre", "") if existing else "", key="cli_nombre")
            dni = st.text_input("DNI / CUIT *", value=existing.get("dni", "") if existing else "", key="cli_dni")
            email = st.text_input("Email", value=existing.get("email", "") if existing else "", key="cli_email")
        with c2:
            telefono = st.text_input("Teléfono", value=existing.get("telefono", "") if existing else "", key="cli_tel")
            direccion = st.text_input("Dirección", value=existing.get("direccion", "") if existing else "", key="cli_dir")
            condicion = st.selectbox(
                "Condición Fiscal",
                options=CONDICIONES_FISCALES,
                index=CONDICIONES_FISCALES.index(existing.get("condicion_fiscal", "Consumidor Final")) if existing and existing.get("condicion_fiscal") in CONDICIONES_FISCALES else 3,
                key="cli_cond",
            )
        notas = st.text_area("Notas", value=existing.get("notas", "") if existing else "", key="cli_notas", height=68)

        submitted = st.form_submit_button("💾 Guardar Cliente", use_container_width=True, type="primary")
        if submitted:
            if not nombre.strip() or not dni.strip():
                st.error("Nombre y DNI/CUIT son obligatorios.")
                return {}
            return {
                "id": existing.get("id") if existing else generar_id(),
                "empresa_id": st.session_state.get("billing_empresa_id", ""),
                "nombre": nombre.strip(),
                "dni": dni.strip(),
                "email": email.strip(),
                "telefono": telefono.strip(),
                "direccion": direccion.strip(),
                "condicion_fiscal": condicion,
                "notas": notas.strip(),
            }
    return {}


def render_clientes() -> None:
    st.markdown("## 🏢 Clientes Fiscales")
    st.caption("Administrá los datos impositivos de pacientes, obras sociales y terceros.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    clientes = get_clientes(empresa_id)

    # ── Acciones ──
    tab1, tab2 = st.tabs(["📋 Listado", "➕ Nuevo Cliente"])

    with tab1:
        if not clientes:
            bloque_estado_vacio(
                "Sin clientes cargados",
                "Todavía no registraste ningún cliente fiscal. Usá la pestaña «Nuevo Cliente» para agregar el primero.",
                "Podés importar pacientes desde Medicare Pro como clientes."
            )
        else:
            # Buscador
            busqueda = st.text_input("🔍 Buscar cliente", placeholder="Nombre, DNI o email...", key="cli_buscar").strip().lower()
            filtrados = clientes
            if busqueda:
                filtrados = [
                    c for c in clientes
                    if busqueda in c.get("nombre", "").lower()
                    or busqueda in c.get("dni", "").lower()
                    or busqueda in c.get("email", "").lower()
                ]

            st.caption(f"{len(filtrados)} cliente(s) encontrado(s)")

            # Exportar
            if XLSX_DISPONIBLE and filtrados:
                excel_data = exportar_clientes_excel(filtrados, empresa_nombre)
                st.download_button(
                    "📥 Exportar Excel",
                    data=excel_data,
                    file_name=f"clientes_{empresa_nombre.replace(' ', '_')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

            for c in filtrados:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 1, 1])
                    with c1:
                        st.markdown(f"**{c.get('nombre', 'Sin nombre')}**")
                        st.caption(f"DNI/CUIT: {c.get('dni', '—')}  ·  {c.get('condicion_fiscal', '—')}")
                        if c.get("email"):
                            st.caption(f"📧 {c.get('email')}")
                        if c.get("telefono"):
                            st.caption(f"📞 {c.get('telefono')}")
                    with c2:
                        if st.button("✏️ Editar", key=f"edit_cli_{c.get('id')}", use_container_width=True):
                            st.session_state["cli_editing"] = c.get("id")
                            st.rerun()
                    with c3:
                        if st.button("🗑️ Borrar", key=f"del_cli_{c.get('id')}", use_container_width=True):
                            if delete_cliente(c.get("id")):
                                st.toast("Cliente eliminado.", icon="🗑️")
                                st.rerun()
                            else:
                                st.error("No se pudo eliminar el cliente.")

                    # Edición inline
                    if st.session_state.get("cli_editing") == c.get("id"):
                        st.divider()
                        data = _form_cliente(c)
                        if data:
                            upsert_cliente(data)
                            st.session_state.pop("cli_editing", None)
                            st.toast("Cliente actualizado.", icon="✅")
                            st.rerun()

    with tab2:
        data = _form_cliente()
        if data:
            result = upsert_cliente(data)
            if result:
                st.toast("Cliente creado correctamente.", icon="✅")
                st.rerun()
            else:
                st.error("Error al guardar el cliente. Revisá la conexión.")
