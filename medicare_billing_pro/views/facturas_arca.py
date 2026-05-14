"""Facturas ARCA internas, preparadas para homologacion WSFEv1."""
from __future__ import annotations

from datetime import date
from typing import Any, Dict, List

import streamlit as st

from core.arca_service import emitir_factura_homologacion, validar_configuracion_arca
from core.billing_logic import money
from core.db_sql import (
    delete_factura_arca,
    generar_numero_formal,
    get_clientes,
    get_config_fiscal,
    get_facturas_arca,
    get_prefacturas,
    registrar_auditoria,
    upsert_factura_arca,
)
from core.excel_export import XLSX_DISPONIBLE, exportar_facturas_arca_excel
from core.pdf_export import FPDF_DISPONIBLE, exportar_factura_arca_pdf
from core.utils import bloque_estado_vacio, fmt_fecha, fmt_moneda, generar_id, mostrar_error_db, sanitize_filename

TIPOS = ["A", "B", "C"]
ESTADOS = ["Borrador", "Lista para ARCA", "CAE pendiente", "Autorizada", "Observada", "Anulada"]
CONDICIONES_IVA = ["Responsable Inscripto", "Monotributista", "Exento", "Consumidor Final", "No Categorizado"]
CONCEPTOS = ["Productos", "Servicios", "Productos y Servicios"]


def _calcular_importes(items: List[Dict[str, Any]], tipo: str, iva_incluido: bool) -> tuple[float, float, float]:
    bruto = sum(money(i.get("cantidad", 1)) * money(i.get("precio_unitario", 0)) for i in items)
    if tipo == "A" and iva_incluido:
        neto = round(bruto / 1.21, 2)
        iva = round(bruto - neto, 2)
        return neto, iva, round(bruto, 2)
    return round(bruto, 2), 0.0, round(bruto, 2)


def _form_factura(existing: Dict[str, Any] | None = None) -> Dict[str, Any] | None:
    empresa_id = st.session_state.get("billing_empresa_id", "")
    config = get_config_fiscal(empresa_id)
    clientes = get_clientes(empresa_id)
    cliente_opts = {c["nombre"]: c for c in clientes}
    base_items = existing.get("items", []) if existing else []
    form_id = existing.get("id", "new") if existing else "new"
    item_count = st.number_input("Cantidad de conceptos", min_value=1, max_value=30, value=max(1, len(base_items) or 1), key=f"arca_count_{form_id}")

    with st.form(f"arca_form_{form_id}", border=True):
        st.markdown(f"### {'Editar' if existing else 'Nueva'} factura ARCA")
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            punto_venta = st.number_input("Punto de venta", min_value=1, max_value=99999, value=int((existing or {}).get("punto_venta", config.get("punto_venta", 1)) or 1))
        with c2:
            tipo = st.selectbox("Tipo", TIPOS, index=TIPOS.index((existing or {}).get("tipo_comprobante", "C")) if (existing or {}).get("tipo_comprobante") in TIPOS else 2)
        with c3:
            concepto_arca = st.selectbox("Concepto ARCA", CONCEPTOS, index=CONCEPTOS.index((existing or {}).get("concepto_arca", "Servicios")) if (existing or {}).get("concepto_arca") in CONCEPTOS else 1)
        with c4:
            fecha = st.date_input("Fecha", value=date.fromisoformat(str((existing or {}).get("fecha", date.today().isoformat()))[:10]))

        c5, c6 = st.columns(2)
        with c5:
            names = list(cliente_opts.keys())
            cliente_sel = st.selectbox("Cliente *", [""] + names, index=names.index(existing.get("cliente_nombre", "")) + 1 if existing and existing.get("cliente_nombre") in names else 0)
        with c6:
            condicion = st.selectbox("Condicion IVA receptor", CONDICIONES_IVA, index=CONDICIONES_IVA.index((existing or {}).get("condicion_iva_receptor", "Consumidor Final")) if (existing or {}).get("condicion_iva_receptor") in CONDICIONES_IVA else 3)

        iva_incluido = st.checkbox("Factura A con IVA 21% incluido en el precio", value=bool(existing and money(existing.get("iva")) > 0))
        items: List[Dict[str, Any]] = []
        st.markdown("#### Conceptos")
        for i in range(int(item_count)):
            item = base_items[i] if i < len(base_items) and isinstance(base_items[i], dict) else {"concepto": "", "cantidad": 1, "precio_unitario": 0}
            ic1, ic2, ic3 = st.columns([3, 1, 1.2])
            with ic1:
                concepto = st.text_input("Concepto", value=item.get("concepto", ""), key=f"arca_con_{form_id}_{i}", label_visibility="collapsed" if i else "visible")
            with ic2:
                cantidad = st.number_input("Cant.", min_value=1, value=int(item.get("cantidad", 1) or 1), key=f"arca_can_{form_id}_{i}", label_visibility="collapsed" if i else "visible")
            with ic3:
                precio = st.number_input("Precio $", min_value=0.0, value=float(item.get("precio_unitario", 0) or 0), step=100.0, key=f"arca_pre_{form_id}_{i}", label_visibility="collapsed" if i else "visible")
            if concepto.strip():
                items.append({"concepto": concepto.strip(), "cantidad": cantidad, "precio_unitario": precio})

        neto, iva, total = _calcular_importes(items, tipo, iva_incluido)
        st.info(f"Neto {fmt_moneda(neto)} | IVA {fmt_moneda(iva)} | Total {fmt_moneda(total)}")
        notas = st.text_area("Notas", value=(existing or {}).get("notas", ""), height=70)

        if st.form_submit_button("Guardar factura", type="primary", width='stretch'):
            if not cliente_sel or not items:
                st.error("Selecciona cliente y agrega al menos un concepto.")
                return None
            cliente = cliente_opts[cliente_sel]
            tipo_num = {"A": "FACA", "B": "FACB", "C": "FACC"}.get(tipo, "FACC")
            numero = existing.get("numero") if existing else generar_numero_formal(empresa_id, tipo_num, int(punto_venta), tipo_num)
            return {
                "id": existing.get("id") if existing else generar_id(),
                "empresa_id": empresa_id,
                "numero": numero,
                "punto_venta": int(punto_venta),
                "tipo_comprobante": tipo,
                "concepto_arca": concepto_arca,
                "cliente_id": cliente.get("id", ""),
                "cliente_nombre": cliente_sel,
                "cliente_dni": cliente.get("dni", ""),
                "condicion_iva_receptor": condicion,
                "fecha": fecha.isoformat(),
                "items": items,
                "neto": neto,
                "iva": iva,
                "total": total,
                "estado": existing.get("estado", "Borrador") if existing else "Borrador",
                "cae": existing.get("cae", "") if existing else "",
                "cae_vencimiento": existing.get("cae_vencimiento") if existing else None,
                "arca_resultado": existing.get("arca_resultado", {}) if existing else {},
                "prefactura_origen": existing.get("prefactura_origen", "") if existing else "",
                "notas": notas.strip(),
            }
    return None


def _desde_prefactura(pref: Dict[str, Any], tipo: str, punto_venta: int, iva_incluido: bool) -> Dict[str, Any]:
    empresa_id = pref.get("empresa_id", st.session_state.get("billing_empresa_id", ""))
    items = pref.get("items", []) or []
    neto, iva, total = _calcular_importes(items, tipo, iva_incluido)
    tipo_num = {"A": "FACA", "B": "FACB", "C": "FACC"}.get(tipo, "FACC")
    return {
        "id": generar_id(),
        "empresa_id": empresa_id,
        "numero": generar_numero_formal(empresa_id, tipo_num, punto_venta, tipo_num),
        "punto_venta": punto_venta,
        "tipo_comprobante": tipo,
        "concepto_arca": "Servicios",
        "cliente_id": pref.get("cliente_id", ""),
        "cliente_nombre": pref.get("cliente_nombre", ""),
        "cliente_dni": pref.get("cliente_dni", ""),
        "condicion_iva_receptor": "Consumidor Final",
        "fecha": date.today().isoformat(),
        "items": items,
        "neto": neto,
        "iva": iva,
        "total": total,
        "estado": "Lista para ARCA",
        "cae": "",
        "cae_vencimiento": None,
        "arca_resultado": {},
        "prefactura_origen": pref.get("id", ""),
        "notas": pref.get("notas", ""),
    }


def render_facturas_arca() -> None:
    st.markdown("## Facturas ARCA")
    st.caption("Comprobantes internos preparados para homologacion y posterior emision fiscal oficial.")

    empresa_id = st.session_state.get("billing_empresa_id", "")
    empresa_nombre = st.session_state.get("billing_empresa_nombre", "Mi Empresa")
    usuario = st.session_state.get("billing_user", {}).get("nombre", "")
    config = get_config_fiscal(empresa_id)
    facturas = get_facturas_arca(empresa_id)
    status = validar_configuracion_arca(config)
    (st.success if status.listo else st.warning)(status.mensaje)

    tab1, tab2, tab3 = st.tabs(["Historial", "Nueva factura", "Desde pre-factura"])
    with tab1:
        if not facturas:
            bloque_estado_vacio("Sin facturas ARCA", "Crea una factura o convierte una pre-factura.")
        else:
            f1, f2, f3, f4, f5 = st.columns([1.4, 1, 1, 1, 1])
            with f1:
                busqueda = st.text_input("Buscar factura", placeholder="Numero, cliente, DNI/CUIT o CAE...").strip().lower()
            with f2:
                estado_filtro = st.selectbox("Estado", ["Todos"] + ESTADOS, key="arca_estado_filtro")
            with f3:
                tipo_filtro = st.selectbox("Tipo", ["Todos"] + TIPOS, key="arca_tipo_filtro")
            with f4:
                fecha_desde = st.date_input("Desde", value=None, key="arca_fecha_desde")
            with f5:
                fecha_hasta = st.date_input("Hasta", value=None, key="arca_fecha_hasta")
            facturas_filtradas = facturas
            if estado_filtro != "Todos":
                facturas_filtradas = [f for f in facturas_filtradas if f.get("estado") == estado_filtro]
            if tipo_filtro != "Todos":
                facturas_filtradas = [f for f in facturas_filtradas if f.get("tipo_comprobante") == tipo_filtro]
            if fecha_desde:
                facturas_filtradas = [f for f in facturas_filtradas if str(f.get("fecha", ""))[:10] >= fecha_desde.isoformat()]
            if fecha_hasta:
                facturas_filtradas = [f for f in facturas_filtradas if str(f.get("fecha", ""))[:10] <= fecha_hasta.isoformat()]
            if busqueda:
                facturas_filtradas = [
                    f
                    for f in facturas_filtradas
                    if busqueda in str(f.get("numero", "")).lower()
                    or busqueda in str(f.get("cliente_nombre", "")).lower()
                    or busqueda in str(f.get("cliente_dni", "")).lower()
                    or busqueda in str(f.get("cae", "")).lower()
                ]
            k1, k2 = st.columns(2)
            k1.metric("Facturas filtradas", len(facturas_filtradas))
            k2.metric("Total filtrado", fmt_moneda(sum(money(f.get("total")) for f in facturas_filtradas)))
            if XLSX_DISPONIBLE:
                st.download_button("Exportar Excel", exportar_facturas_arca_excel(facturas_filtradas, empresa_nombre), f"facturas_arca_{sanitize_filename(empresa_nombre)}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", width='stretch')
            with st.container(height=610, border=False):
                for f in facturas_filtradas:
                    with st.container(border=True):
                        c1, c2, c3 = st.columns([3.1, 1.25, 2.55])
                        with c1:
                            st.markdown(f"**Factura {f.get('tipo_comprobante', 'C')} {f.get('numero', '-')}** | {f.get('cliente_nombre', '-')}")
                            st.caption(f"{fmt_fecha(f.get('fecha', ''))} | Neto {fmt_moneda(f.get('neto', 0))} | IVA {fmt_moneda(f.get('iva', 0))} | Total {fmt_moneda(f.get('total', 0))}")
                            st.caption(f"Estado: {f.get('estado', 'Borrador')} | CAE: {f.get('cae') or 'Pendiente'}")
                        with c2:
                            estado = st.selectbox("Estado", ESTADOS, index=ESTADOS.index(f.get("estado", "Borrador")) if f.get("estado") in ESTADOS else 0, key=f"arca_est_{f.get('id')}", label_visibility="collapsed")
                            if estado != f.get("estado"):
                                f["estado"] = estado
                                if upsert_factura_arca(f):
                                    registrar_auditoria(empresa_id, usuario, "cambiar_estado", "factura_arca", f.get("id", ""), {"estado": estado})
                                    st.rerun()
                        with c3:
                            b1, b2, b3 = st.columns([1.25, 1, 1.2])
                            with b1:
                                if FPDF_DISPONIBLE:
                                    st.download_button("Descargar PDF", exportar_factura_arca_pdf(f, empresa_nombre, f.get("items", []), config), f"factura_arca_{sanitize_filename(f.get('numero', ''))}.pdf", mime="application/pdf", key=f"pdf_arca_{f.get('id')}", width='stretch')
                            with b2:
                                result = emitir_factura_homologacion(f, config)
                                if st.button("Emitir", key=f"emit_arca_{f.get('id')}", width='stretch', disabled=not status.listo):
                                    st.warning(result.get("mensaje", "Pendiente de homologacion."))
                            with b3:
                                confirm = st.checkbox("Confirmar", key=f"confirm_del_arca_{f.get('id')}")
                                if st.button("Eliminar", key=f"del_arca_{f.get('id')}", width='stretch', disabled=not confirm):
                                    if delete_factura_arca(f.get("id")):
                                        registrar_auditoria(empresa_id, usuario, "borrar", "factura_arca", f.get("id", ""))
                                        st.rerun()

    with tab2:
        data = _form_factura()
        if data:
            if upsert_factura_arca(data):
                registrar_auditoria(empresa_id, usuario, "crear", "factura_arca", data.get("id", ""), {"numero": data.get("numero")})
                st.toast("Factura ARCA creada.")
                st.rerun()
            else:
                mostrar_error_db("guardar factura ARCA")

    with tab3:
        prefs = [p for p in get_prefacturas(empresa_id) if p.get("estado") != "Anulada"]
        if not prefs:
            bloque_estado_vacio("Sin pre-facturas disponibles", "Crea una pre-factura primero.")
        else:
            pv = st.number_input("Punto de venta", min_value=1, max_value=99999, value=int(config.get("punto_venta", 1) or 1), key="conv_pv")
            tipo = st.selectbox("Tipo", TIPOS, index=2, key="conv_tipo")
            iva_incluido = st.checkbox("Factura A con IVA 21% incluido", key="conv_iva")
            with st.container(height=560, border=False):
                for p in prefs:
                    with st.container(border=True):
                        st.markdown(f"**{p.get('numero', '-')}** | {p.get('cliente_nombre', '-')} | {fmt_moneda(p.get('total', 0))}")
                        if st.button("Convertir a factura ARCA", key=f"conv_arca_{p.get('id')}", width='stretch'):
                            data = _desde_prefactura(p, tipo, int(pv), iva_incluido)
                            if upsert_factura_arca(data):
                                registrar_auditoria(empresa_id, usuario, "convertir_prefactura", "factura_arca", data.get("id", ""), {"prefactura": p.get("id")})
                                st.toast("Factura ARCA generada.")
                                st.rerun()
                            else:
                                mostrar_error_db("convertir la pre-factura")
