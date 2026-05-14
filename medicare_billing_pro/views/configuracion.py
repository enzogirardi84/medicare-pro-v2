"""Configuracion fiscal y operativa de Billing Pro."""
from __future__ import annotations

from datetime import date

import streamlit as st

from core.arca_service import validar_configuracion_arca
from core.db_sql import get_auditoria, get_config_fiscal, get_numeradores, registrar_auditoria, upsert_config_fiscal, upsert_numerador
from core.utils import generar_id, mostrar_error_db, normalize_document, normalize_phone

CONDICIONES_IVA = ["Responsable Inscripto", "Monotributista", "Exento", "Consumidor Final", "No Categorizado"]
TIPOS_NUMERADOR = ["PRES", "PREF", "FACA", "FACB", "FACC", "REC"]


def render_configuracion() -> None:
    st.markdown("## Configuracion fiscal")
    st.caption("Datos institucionales, ARCA, numeracion y auditoria operativa.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    usuario = st.session_state.get("billing_user", {}).get("nombre", "")
    config = get_config_fiscal(empresa_id)

    tab1, tab2, tab3 = st.tabs(["Datos fiscales", "Numeracion", "Auditoria"])

    with tab1:
        with st.form("config_fiscal_form", border=True):
            c1, c2 = st.columns(2)
            with c1:
                razon_social = st.text_input("Razon social", value=config.get("razon_social", ""))
                nombre_fantasia = st.text_input("Nombre fantasia", value=config.get("nombre_fantasia", ""))
                cuit = st.text_input("CUIT", value=config.get("cuit", ""))
                condicion_iva = st.selectbox(
                    "Condicion IVA",
                    CONDICIONES_IVA,
                    index=CONDICIONES_IVA.index(config.get("condicion_iva", "Monotributista")) if config.get("condicion_iva") in CONDICIONES_IVA else 1,
                )
                inicio = st.date_input(
                    "Inicio actividades",
                    value=date.fromisoformat(str(config.get("inicio_actividades", date.today().isoformat()))[:10]) if config.get("inicio_actividades") else date.today(),
                )
            with c2:
                domicilio = st.text_input("Domicilio fiscal", value=config.get("domicilio_fiscal", ""))
                ingresos_brutos = st.text_input("Ingresos brutos", value=config.get("ingresos_brutos", ""))
                punto_venta = st.number_input("Punto de venta ARCA", min_value=1, max_value=99999, value=int(config.get("punto_venta", 1) or 1))
                email = st.text_input("Email facturacion", value=config.get("email_facturacion", ""))
                telefono = st.text_input("Telefono facturacion", value=config.get("telefono_facturacion", ""))
            leyenda = st.text_area("Leyenda en facturas", value=config.get("leyenda_factura", ""), height=80)
            modo = st.selectbox("Modo ARCA", ["homologacion", "produccion"], index=0 if config.get("arca_modo", "homologacion") == "homologacion" else 1)
            cert_ok = st.checkbox("Certificado y clave privada configurados fuera de la app", value=bool(config.get("arca_certificado_configurado", False)))

            if st.form_submit_button("Guardar configuracion fiscal", type="primary", width='stretch'):
                data = {
                    "empresa_id": empresa_id,
                    "razon_social": razon_social.strip(),
                    "nombre_fantasia": nombre_fantasia.strip(),
                    "cuit": normalize_document(cuit),
                    "condicion_iva": condicion_iva,
                    "domicilio_fiscal": domicilio.strip(),
                    "ingresos_brutos": ingresos_brutos.strip(),
                    "inicio_actividades": inicio.isoformat(),
                    "punto_venta": int(punto_venta),
                    "email_facturacion": email.strip().lower(),
                    "telefono_facturacion": normalize_phone(telefono),
                    "leyenda_factura": leyenda.strip(),
                    "arca_modo": modo,
                    "arca_certificado_configurado": cert_ok,
                }
                if upsert_config_fiscal(data):
                    registrar_auditoria(empresa_id, usuario, "guardar_config_fiscal", "config_fiscal", empresa_id, {"modo": modo})
                    st.toast("Configuracion guardada.")
                    st.rerun()
                else:
                    mostrar_error_db("guardar la configuracion fiscal")

        status = validar_configuracion_arca(get_config_fiscal(empresa_id))
        (st.success if status.listo else st.warning)(status.mensaje)

    with tab2:
        numeradores = get_numeradores(empresa_id)
        st.caption("Define el ultimo numero usado. El siguiente comprobante suma 1 automaticamente.")
        with st.container(height=560, border=False):
            for tipo in TIPOS_NUMERADOR:
                actual = next((n for n in numeradores if n.get("tipo") == tipo), {})
                with st.form(f"num_{tipo}", border=True):
                    c1, c2, c3 = st.columns(3)
                    with c1:
                        pv = st.number_input("Punto de venta", min_value=1, max_value=99999, value=int(actual.get("punto_venta", config.get("punto_venta", 1)) or 1), key=f"pv_{tipo}")
                    with c2:
                        prefijo = st.text_input("Prefijo", value=actual.get("prefijo", tipo), key=f"pref_{tipo}")
                    with c3:
                        ultimo = st.number_input("Ultimo numero", min_value=0, value=int(actual.get("ultimo_numero", 0) or 0), key=f"ult_{tipo}")
                    if st.form_submit_button(f"Guardar {tipo}", width='stretch'):
                        if upsert_numerador({
                            "id": actual.get("id") or generar_id(),
                            "empresa_id": empresa_id,
                            "tipo": tipo,
                            "punto_venta": int(pv),
                            "prefijo": prefijo.strip() or tipo,
                            "ultimo_numero": int(ultimo),
                        }):
                            registrar_auditoria(empresa_id, usuario, "guardar_numerador", "numerador", tipo, {"ultimo": int(ultimo)})
                            st.toast(f"Numerador {tipo} guardado.")
                            st.rerun()
                        else:
                            mostrar_error_db("guardar el numerador")

    with tab3:
        rows = get_auditoria(empresa_id, 200)
        if rows:
            busqueda = st.text_input("Buscar auditoria", placeholder="Usuario, accion, entidad o ID...").strip().lower()
            if busqueda:
                rows = [
                    r
                    for r in rows
                    if busqueda in str(r.get("usuario", "")).lower()
                    or busqueda in str(r.get("accion", "")).lower()
                    or busqueda in str(r.get("entidad", "")).lower()
                    or busqueda in str(r.get("entidad_id", "")).lower()
                ]
            st.dataframe(
                [
                    {
                        "Fecha": r.get("created_at", ""),
                        "Usuario": r.get("usuario", ""),
                        "Accion": r.get("accion", ""),
                        "Entidad": r.get("entidad", ""),
                        "ID": r.get("entidad_id", ""),
                    }
                    for r in rows
                ],
                width='stretch',
                hide_index=True,
                height=520,
            )
        else:
            st.info("Todavia no hay eventos de auditoria.")
