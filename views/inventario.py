from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from core.alert_toasts import queue_toast
import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.permissions import STOCK_AJUSTAR, STOCK_ELIMINAR, STOCK_VER, puede
from core.view_helpers import bloque_estado_vacio, lista_plegable
from core.utils import cargar_json_asset, seleccionar_limite_registros, ahora
from core.db_sql import (
    delete_inventario_item_sql,
    get_inventario_by_empresa,
    get_inventario_item_by_name,
    insert_inventario,
    update_inventario_item_sql,
)
from core.nextgen_sync import _obtener_uuid_empresa
from core.app_logging import log_event

_COLORES_CATEGORIA = [
    "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
    "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
]


def render_inventario(mi_empresa):
    usuario_actual = st.session_state.get("u_actual", {})
    puede_ver_stock = puede(usuario_actual, STOCK_VER)
    puede_ajustar_stock = puede(usuario_actual, STOCK_AJUSTAR)
    puede_eliminar_stock = puede(usuario_actual, STOCK_ELIMINAR)

    if not puede_ver_stock:
        st.warning("No tenés permisos suficientes para ver el inventario.")
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Inventario y stock de farmacia</h2>
            <p class="mc-hero-text">Gestioná medicamentos e insumos con un catálogo guiado para evitar errores de carga. La vista prioriza alertas, correcciones rápidas y control visual de stock crítico.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Catálogo sugerido</span>
                <span class="mc-chip">Alerta de faltantes</span>
                <span class="mc-chip">Corrección de stock</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    inv_mio = []
    try:
        empresa_uuid = _obtener_uuid_empresa(mi_empresa)
        if empresa_uuid:
            inv_sql = get_inventario_by_empresa(empresa_uuid)
            if inv_sql:
                for i in inv_sql:
                    inv_mio.append({
                        "empresa": mi_empresa,
                        "item": i.get("nombre", ""),
                        "stock": i.get("stock_actual", 0),
                        "stock_minimo": i.get("stock_minimo", 0) or 0,
                        "categoria": i.get("categoria", ""),
                        "costo_unitario": i.get("costo_unitario", 0) or 0,
                        "id_sql": i.get("id")
                    })
                st.session_state["inventario_db"] = list(inv_mio)
    except Exception as e:
        log_event("error_leer_inventario_sql", str(e))

    if not inv_mio and st.session_state.get("inventario_db"):
        inv_mio = st.session_state["inventario_db"]
        inv_mio = [i for i in st.session_state.get("inventario_db", []) if i is not None and i.get("empresa") == mi_empresa]

    def _umbral_critico(item):
        sm = int(item.get("stock_minimo", 0) or 0)
        return sm if sm > 0 else 10

    def _umbral_bajo(item):
        sm = int(item.get("stock_minimo", 0) or 0)
        return sm * 2 if sm > 0 else 25

    stock_critico = [i for i in inv_mio if i.get("stock", 0) <= _umbral_critico(i)]
    stock_bajo = [i for i in inv_mio if _umbral_critico(i) < i.get("stock", 0) <= _umbral_bajo(i)]
    total_unidades = sum(int(i.get("stock", 0) or 0) for i in inv_mio)

    _valor_total = sum(
        float(i.get("stock", 0)) * float(i.get("costo_unitario", 0) or 0)
        for i in inv_mio
        if float(i.get("costo_unitario", 0) or 0) > 0
    )

    _hace_7d_dt = ahora() - timedelta(days=7)
    _cons_7d = []
    for c in st.session_state.get("consumos_db", []):
        if c.get("empresa") != mi_empresa:
            continue
        _fecha_str = (c.get("fecha") or "")[:10]
        try:
            _fecha_dt = datetime.strptime(_fecha_str, "%d/%m/%Y")
            if _fecha_dt >= _hace_7d_dt:
                _cons_7d.append(c)
        except (ValueError, TypeError):
            pass
    _unid_7d = sum(int(c.get("cantidad", 0) or 0) for c in _cons_7d)

    if inv_mio:
        cols = st.columns(3)
        cols[0].metric("Ítems en inventario", len(inv_mio))
        cols[0].metric("🔴 Stock crítico", len(stock_critico), help="Según stock mínimo de cada ítem o ≤10 por defecto")
        cols[1].metric("🟡 Stock bajo", len(stock_bajo), help="Por debajo del doble del stock mínimo o ≤25 por defecto")
        cols[1].metric("Unidades totales", total_unidades)
        cols[2].metric("Valor total", f"${_valor_total:,.0f}".replace(",", ".") if _valor_total > 0 else "—", help="Suma stock × costo unitario")

    if _cons_7d:
        st.caption(f"📊 Consumos últimos 7 días: **{len(_cons_7d)} registros** ({_unid_7d} unidades)")

    consumos_empresa = [
        c for c in st.session_state.get("consumos_db", [])
        if c.get("empresa") == mi_empresa
    ]
    if consumos_empresa:
        _conteo_cons = Counter()
        for c in consumos_empresa:
            _conteo_cons[c.get("insumo", "")] += int(c.get("cantidad", 0) or 0)
        _top5 = _conteo_cons.most_common(5)
        if _top5:
            with st.expander("📊 Top insumos más consumidos (histórico)", expanded=False):
                for ins, qty in _top5:
                    stock_ins = next((i.get("stock", 0) for i in inv_mio if i.get("item", "").lower() == ins.lower()), None)
                    _sm = next((i.get("stock_minimo", 10) for i in inv_mio if i.get("item", "").lower() == ins.lower()), 10)
                    _sem = " 🔴" if stock_ins is not None and stock_ins <= _sm else (" 🟡" if stock_ins is not None and stock_ins <= _sm * 2 else "")
                    st.caption(f"**{ins}** — {qty} u. consumidas{_sem}" + (f" | stock actual: {stock_ins}" if stock_ins is not None else ""))

    if stock_critico:
        with lista_plegable("Stock crítico (según stock mínimo)", count=len(stock_critico), expanded=True, height=260):
            for item in stock_critico[:80]:
                _sm = int(item.get("stock_minimo", 0) or 0)
                _reponer = max(1, _sm * 2 - int(item.get("stock", 0)))
                lbl = f"**{_reponer}** para reposición sugerida" if _sm > 0 else ""
                log_event("inventario", f"error: stock critico {item.get('item')} = {item.get('stock', 0)}")
                st.error(f"{item.get('item')} → **{item.get('stock', 0)}** ({lbl})")
    if stock_bajo:
        with lista_plegable("Stock bajo (por debajo del doble del mínimo)", count=len(stock_bajo), expanded=False, height=200):
            for item in stock_bajo[:80]:
                _sm = int(item.get("stock_minimo", 0) or 0)
                _reponer = max(1, _sm * 2 - int(item.get("stock", 0)))
                lbl = f" — reponer **{_reponer}**" if _sm > 0 else ""
                st.warning(f"{item.get('item')} → {item.get('stock', 0)} unidades{lbl}")

    try:
        vademecum_base = cargar_json_asset("vademecum.json")
    except Exception:
        vademecum_base = []

    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>Carga guiada</h4><p>Usá el catálogo frecuente para minimizar errores de tipeo del personal.</p></div>
            <div class="mc-card"><h4>Nuevos ítems</h4><p>También podés cargar un insumo nuevo cuando todavía no existe en el catálogo.</p></div>
            <div class="mc-card"><h4>Control visual</h4><p>Los faltantes se resaltan para detectar rápido qué necesita reposición.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Stock crítico (≤10) está en un panel plegable. El formulario suma mercadería; la tabla completa y la corrección de ítems también se pueden plegar."
    )

    if puede_ajustar_stock:
        with st.form("form_inv", clear_on_submit=True):
            st.markdown("##### Ingreso de mercadería")
            c1, c2, c3 = st.columns([2, 2, 1])
            lista_base_inv = ["-- Seleccionar del catálogo --"] + vademecum_base

            item_sel = c1.selectbox("1. Catálogo frecuente", lista_base_inv)
            nuevo_item = c2.text_input("2. Escribir insumo nuevo")
            cantidad = c3.number_input("Cantidad", min_value=1, value=10, step=1)
            c4, c5 = st.columns([1, 1])
            _cat_input = c4.text_input("Categoría (opcional)", placeholder="Ej: Medicamentos, Descartables")
            _costo_input = c5.number_input("Costo unitario $ (opcional)", min_value=0.0, value=0.0, step=1.0, format="%.2f")

            if st.form_submit_button("Sumar al stock", use_container_width=True, type="primary"):
                item_final = nuevo_item.strip().title() if nuevo_item.strip() else item_sel
                if item_final and item_final != "-- Seleccionar del catálogo --":
                    sql_ok = False
                    item_sql_id = None
                    try:
                        empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                        if empresa_uuid:
                            existente = get_inventario_item_by_name(empresa_uuid, item_final)
                            if existente:
                                item_sql_id = existente.get("id")
                                _upd = {"stock_actual": int(existente.get("stock_actual") or 0) + cantidad}
                                if _cat_input.strip():
                                    _upd["categoria"] = _cat_input.strip()
                                if _costo_input > 0:
                                    _upd["costo_unitario"] = _costo_input
                                sql_ok = update_inventario_item_sql(item_sql_id, _upd, empresa_uuid)
                            else:
                                datos_sql = {"empresa_id": empresa_uuid, "nombre": item_final, "stock_actual": cantidad}
                                if _cat_input.strip():
                                    datos_sql["categoria"] = _cat_input.strip()
                                if _costo_input > 0:
                                    datos_sql["costo_unitario"] = _costo_input
                                creado = insert_inventario(datos_sql)
                                sql_ok = bool(creado)
                                item_sql_id = creado.get("id") if creado else None
                            log_event("inventario_sql_insert_update", f"Item: {item_final}; sql_ok={sql_ok}")
                    except Exception as e:
                        log_event("error_inventario_sql", str(e))

                    encontrado = False
                    if "inventario_db" not in st.session_state:
                        st.session_state["inventario_db"] = []
                    for i in st.session_state["inventario_db"]:
                        if i is None:
                            continue
                        if i.get("item", "").lower() == item_final.lower() and i.get("empresa") == mi_empresa:
                            i["stock"] = int(i.get("stock") or 0) + cantidad
                            if item_sql_id:
                                i["id_sql"] = item_sql_id
                            if _cat_input.strip():
                                i["categoria"] = _cat_input.strip()
                            if _costo_input > 0:
                                i["costo_unitario"] = _costo_input
                            encontrado = True
                            break
                    if not encontrado:
                        _entry = {"item": item_final, "stock": cantidad, "empresa": mi_empresa}
                        if item_sql_id:
                            _entry["id_sql"] = item_sql_id
                        if _cat_input.strip():
                            _entry["categoria"] = _cat_input.strip()
                        if _costo_input > 0:
                            _entry["costo_unitario"] = _costo_input
                        st.session_state.setdefault("inventario_db", []).append(_entry)

                    from core.database import _trim_db_list
                    _trim_db_list("inventario_db", 1000)
                    if not sql_ok:
                        with st.spinner("Guardando respaldo local..."):
                            guardar_datos(spinner=False)
                    queue_toast(f"Se agregaron {cantidad} unidades de {item_final}.")
                    st.rerun()
    else:
        st.info("Tenés acceso de solo lectura al inventario. Los ingresos y ajustes de stock están deshabilitados para este usuario.")

    st.divider()

    if inv_mio:
        df_stock = pd.DataFrame(inv_mio).rename(columns={
            "item": "Insumo", "stock": "Stock actual", "stock_minimo": "Stock mínimo",
            "categoria": "Categoría", "costo_unitario": "Costo unit.",
        })

        _categorias = sorted(set(i.get("categoria", "") for i in inv_mio if i.get("categoria")))
        _filtros = st.columns([2, 1.2, 1])
        _busq_inv = _filtros[0].text_input(
            "🔍 Buscar insumo", placeholder="Nombre...", key="inventario_busqueda",
        ).strip().lower()
        _cat_sel = _filtros[1].selectbox(
            "Categoría", ["Todas"] + _categorias, key="inventario_categoria",
        )
        _filtro_crit = _filtros[2].selectbox(
            "Stock",
            ["Todos", "Crítico", "Bajo", "Normal (>25)"],
            key="inventario_filtro",
        )
        df_filtrado = df_stock.copy()
        df_filtrado["Stock actual"] = pd.to_numeric(df_filtrado["Stock actual"], errors="coerce").fillna(0).astype(int)
        if _busq_inv:
            df_filtrado = df_filtrado[df_filtrado["Insumo"].str.lower().str.contains(_busq_inv, na=False)]
        if _cat_sel != "Todas":
            df_filtrado = df_filtrado[df_filtrado.get("Categoría", "") == _cat_sel]
        if _filtro_crit == "Crítico":
            df_filtrado = df_filtrado[df_filtrado["Stock actual"] <= df_filtrado.get("Stock mínimo", 10)]
        elif _filtro_crit == "Bajo":
            _b = df_filtrado["Stock mínimo"].fillna(10) * 2
            df_filtrado = df_filtrado[(df_filtrado["Stock actual"] > df_filtrado["Stock mínimo"].fillna(10)) & (df_filtrado["Stock actual"] <= _b)]
        elif _filtro_crit == "Normal (>25)":
            df_filtrado = df_filtrado[df_filtrado["Stock actual"] > 25]
        if _busq_inv or _filtro_crit != "Todos":
            st.caption(f"{len(df_filtrado)} insumo(s) encontrado(s)")

        limite_stock = seleccionar_limite_registros(
            "Insumos a mostrar",
            len(df_filtrado),
            key="inventario_limite_stock",
            default=50,
            opciones=(10, 20, 50, 100, 200, 500),
        )

        def _row_umbral(row):
            sm = row.get("Stock mínimo", 10)
            return sm if sm > 0 else 10

        def colorear_stock(row):
            stock = row["Stock actual"]
            umbral = _row_umbral(row)
            if stock <= umbral:
                return ["background-color: #3c1f1f; color: #ffb4b4; font-weight: bold"] * len(row)
            if stock <= umbral * 2:
                return ["background-color: #3c3217; color: #ffe08a; font-weight: 600"] * len(row)
            return ["background-color: #122033; color: #ffffff"] * len(row)

        _cols_tabla = ["Insumo", "Stock actual", "Stock mínimo"]
        if "Categoría" in df_filtrado.columns and df_filtrado["Categoría"].notna().any():
            _cols_tabla.append("Categoría")
        if "Costo unit." in df_filtrado.columns and (pd.to_numeric(df_filtrado["Costo unit."], errors="coerce").fillna(0) > 0).any():
            _cols_tabla.append("Costo unit.")

        styled = (
            df_filtrado.sort_values(by="Stock actual", ascending=True)[_cols_tabla]
            .head(limite_stock)
            .style.apply(colorear_stock, axis=1)
        )
        with lista_plegable("Tabla de stock actual", count=len(df_filtrado), expanded=False, height=520):
            st.dataframe(styled, use_container_width=True, hide_index=True, height=496)
    else:
        bloque_estado_vacio(
            "Inventario vacío",
            "No hay insumos cargados para esta clínica.",
            sugerencia="Usá Ingreso de mercadería arriba: catálogo o insumo nuevo y cantidad.",
        )

    st.divider()

    if inv_mio and puede_ajustar_stock:
        st.markdown("### 📦 Ajuste de stock masivo")
        st.caption("Seleccioná varios ítems y aplicá un mismo ajuste a todos.")
        _items_all = [i.get("item", "") for i in inv_mio]
        _selected = st.multiselect("Ítems a ajustar", options=_items_all, key="batch_inv_items")
        if _selected:
            _ajuste = st.number_input("Cantidad a sumar/restar", value=0, step=1, key="batch_inv_qty")
            _razon = st.text_input("Motivo del ajuste", placeholder="Ej: inventario físico", key="batch_inv_reason")
            if st.button("✅ Aplicar ajuste masivo", type="primary", key="batch_inv_apply", use_container_width=True):
                if _razon.strip():
                    empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                    _count = 0
                    _sql_fallos = 0

                    for _inv in inv_mio:
                        if _inv.get("item", "") in _selected:
                            nuevo_stock = max(0, int(_inv.get("stock", 0)) + _ajuste)
                            _inv["stock"] = nuevo_stock
                            _count += 1

                            item_sql_id = _inv.get("id_sql")
                            if empresa_uuid and item_sql_id:
                                ok = update_inventario_item_sql(
                                    item_sql_id,
                                    {"stock_actual": nuevo_stock},
                                    empresa_uuid,
                                )
                                if not ok:
                                    _sql_fallos += 1
                            else:
                                _sql_fallos += 1

                    st.session_state["inventario_db"] = inv_mio

                    if _sql_fallos:
                        guardar_datos(spinner=False)

                    st.success(f"✅ {_count} ítems ajustados ({_ajuste:+d} unidades)")
                    log_event(
                        "inventario",
                        f"batch_ajuste:{_count}items:{_ajuste:+d}:fallos_sql={_sql_fallos}:{_razon}",
                    )
                    st.rerun()
                else:
                    st.warning("Indicá un motivo para el ajuste.")
        st.divider()

        with lista_plegable("Ajuste manual, corrección y baja de insumos", expanded=False, height=None):
            st.markdown("#### Ajuste manual y corrección")
            item_a_editar = st.selectbox("Seleccionar insumo a corregir", [i.get("item", "") for i in inv_mio if i is not None], key="edit_sel")
            _item_data = next((i for i in inv_mio if i is not None and i.get("item") == item_a_editar), {})
            _s_act = _item_data.get("stock", 0)
            _s_min = int(_item_data.get("stock_minimo", 0) or 0)
            _costo = float(_item_data.get("costo_unitario", 0) or 0)
            c_aj1, c_aj2, c_aj3 = st.columns([1, 1, 1])
            nuevo_stock = c_aj1.number_input("Stock real", min_value=0, value=_s_act, key="new_stock")
            nuevo_min = c_aj2.number_input("Stock mínimo", min_value=0, value=_s_min, key="new_min")
            nuevo_costo = c_aj3.number_input("Costo unitario $", min_value=0.0, value=_costo, step=0.5, format="%.2f", key="new_costo")
            try:
                from core._insumos_map import stock_minimo_sugerido
                _sug_min = stock_minimo_sugerido(item_a_editar, mi_empresa)
                if _sug_min > 0:
                    st.caption(f"💡 ≈**{_sug_min}** uds. según consumos")
            except Exception:
                pass
            c_save_col, _ = st.columns([1, 1])
            if c_save_col.button("Guardar cambios", use_container_width=True, type="primary"):
                cambios = {"stock_actual": nuevo_stock, "stock_minimo": nuevo_min, "costo_unitario": nuevo_costo}
                sql_ok = False
                try:
                    empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                    item_sql_id = _item_data.get("id_sql")
                    if empresa_uuid and item_sql_id:
                        sql_ok = update_inventario_item_sql(item_sql_id, cambios, empresa_uuid)
                    log_event("inventario_sql_update", f"Item: {item_a_editar}; sql_ok={sql_ok}")
                except Exception as e:
                    log_event("error_inventario_sql_update", str(e))
                if "inventario_db" in st.session_state:
                    for i in st.session_state["inventario_db"]:
                        if i is not None and i.get("item") == item_a_editar and i.get("empresa") == mi_empresa:
                            i["stock"] = nuevo_stock
                            i["stock_minimo"] = nuevo_min
                            i["costo_unitario"] = nuevo_costo
                            break
                if not sql_ok:
                    guardar_datos(spinner=True)
                queue_toast(f"{item_a_editar}: stock={nuevo_stock}, mínimo={nuevo_min}, costo=${nuevo_costo:.2f}")
                st.rerun()

            if puede_eliminar_stock:
                col_del1, col_del2 = st.columns([3, 1])
                del_item = col_del1.selectbox("Eliminar insumo por completo", [i.get("item", "") for i in inv_mio if i is not None], key="del_sel")
                confirmar = col_del1.checkbox("Confirmar eliminación definitiva", key="conf_del_item")
                if col_del2.button("Eliminar insumo", use_container_width=True, type="secondary", disabled=not confirmar):
                    sql_ok = False
                    try:
                        empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                        _item_del_data = next((i for i in inv_mio if i.get("item") == del_item), {})
                        item_sql_id = _item_del_data.get("id_sql")
                        if empresa_uuid and item_sql_id:
                            sql_ok = delete_inventario_item_sql(item_sql_id, empresa_uuid)
                        log_event("inventario_sql_delete", f"Item: {del_item}; sql_ok={sql_ok}")
                    except Exception as e:
                        log_event("error_inventario_sql_delete", str(e))

                    if "inventario_db" in st.session_state:
                        st.session_state["inventario_db"] = [
                            i for i in st.session_state["inventario_db"] if i is None or not (i.get("item") == del_item and i.get("empresa") == mi_empresa)
                        ]
                    if not sql_ok:
                        guardar_datos(spinner=True)
                    queue_toast(f"Se eliminó {del_item} del inventario.")
                    st.rerun()
            else:
                st.caption("La eliminación definitiva de insumos está deshabilitada para este usuario.")

    # --- EXPORTAR REPORTE ---
    st.divider()
    st.markdown("### 📦 Reporte de inventario")
    with st.expander("Exportar reporte completo", expanded=False):
        col_exp1, col_exp2 = st.columns(2)
        with col_exp1:
            if st.button("📄 Exportar PDF", use_container_width=True, key="inv_export_pdf"):
                try:
                    with st.spinner("Generando PDF..."):
                        _exportar_inventario_pdf(inv_mio, mi_empresa)
                except Exception as e:
                    log_event("inventario", f"error_export_pdf:{type(e).__name__}:{e}")
                    st.error(f"Error al generar PDF: {e}")
        with col_exp2:
            if st.button("📊 Exportar Excel", use_container_width=True, key="inv_export_xlsx"):
                try:
                    with st.spinner("Generando Excel..."):
                        _exportar_inventario_excel(inv_mio, mi_empresa)
                except Exception as e:
                    log_event("inventario", f"error_export_xlsx:{type(e).__name__}:{e}")
                    st.error(f"Error al generar Excel: {e}")


def _exportar_inventario_pdf(inventario: list, empresa: str) -> None:
    """Genera PDF con reporte completo de inventario y consumos."""
    try:
        from fpdf import FPDF
        from core.export_utils import pdf_output_bytes, safe_text

        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=20)
        pdf.add_page()
        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, f"Inventario - {empresa}", ln=True, align="C")
        pdf.set_font("Helvetica", "", 9)
        pdf.cell(0, 6, f"Generado: {datetime.now().strftime('%d/%m/%Y %H:%M')}", ln=True, align="C")
        pdf.ln(5)

        # --- SECCION INVENTARIO ---
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Stock actual", ln=True)
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_fill_color(25, 55, 95)
        pdf.set_text_color(255, 255, 255)
        pdf.cell(10, 7, "#", border=1, fill=True, align="C")
        pdf.cell(70, 7, "Insumo", border=1, fill=True)
        pdf.cell(20, 7, "Stock", border=1, fill=True, align="C")
        pdf.cell(20, 7, "Minimo", border=1, fill=True, align="C")
        pdf.cell(30, 7, "Categoria", border=1, fill=True, align="C")
        pdf.cell(40, 7, "Costo unit.", border=1, fill=True, align="C")
        pdf.ln()

        pdf.set_font("Helvetica", "", 8)
        pdf.set_text_color(40, 40, 40)
        total_valor = 0
        for idx, item in enumerate(inventario, 1):
            if item is None:
                continue
            stock = item.get("stock", 0)
            costo = item.get("costo_unitario", 0) or 0
            total_valor += int(stock) * float(costo)
            pdf.cell(10, 6, str(idx), border=1, align="C")
            pdf.cell(70, 6, safe_text((item.get("item") or "-")[:60]), border=1)
            pdf.cell(20, 6, str(stock), border=1, align="C")
            pdf.cell(20, 6, str(item.get("stock_minimo", 0)), border=1, align="C")
            pdf.cell(30, 6, safe_text((item.get("categoria") or "-")[:25]), border=1, align="C")
            pdf.cell(40, 6, f"${float(costo):.2f}", border=1, align="C")
            pdf.ln()

        pdf.ln(3)
        pdf.set_font("Helvetica", "B", 10)
        pdf.cell(0, 7, f"Total items: {len(inventario)} | Valor total inventario: ${total_valor:.2f}", ln=True)
        pdf.ln(8)

        # --- SECCION CONSUMOS ---
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(0, 8, "Insumos utilizados (historial)", ln=True)

        consumos = st.session_state.get("consumos_db", [])
        cons_emp = [c for c in consumos if isinstance(c, dict) and c.get("empresa") == empresa]

        if cons_emp:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_fill_color(25, 55, 95)
            pdf.set_text_color(255, 255, 255)
            pdf.cell(10, 7, "#", border=1, fill=True, align="C")
            pdf.cell(60, 7, "Insumo", border=1, fill=True)
            pdf.cell(22, 7, "Cantidad", border=1, fill=True, align="C")
            pdf.cell(50, 7, "Paciente", border=1, fill=True)
            pdf.cell(48, 7, "Fecha", border=1, fill=True, align="C")
            pdf.ln()

            pdf.set_font("Helvetica", "", 8)
            pdf.set_text_color(40, 40, 40)
            total_consumido = 0
            for idx, c in enumerate(cons_emp, 1):
                cant = int(c.get("cantidad", 0) or 0)
                total_consumido += cant
                pdf.cell(10, 6, str(idx), border=1, align="C")
                pdf.cell(60, 6, safe_text((c.get("item") or c.get("medicamento") or c.get("insumo") or "-")[:50]), border=1)
                pdf.cell(22, 6, str(cant), border=1, align="C")
                pdf.cell(50, 6, safe_text((c.get("paciente") or "-")[:40]), border=1)
                pdf.cell(48, 6, safe_text(str(c.get("fecha", ""))[:16]), border=1, align="C")
                pdf.ln()

            pdf.ln(3)
            pdf.set_font("Helvetica", "B", 10)
            pdf.cell(0, 7, f"Total registros: {len(cons_emp)} | Unidades consumidas: {total_consumido}", ln=True)
        else:
            pdf.set_font("Helvetica", "", 9)
            pdf.cell(0, 6, "Sin registros de consumo.", ln=True)

        st.download_button("Descargar PDF", pdf_output_bytes(pdf),
                           file_name=f"inventario_{empresa}_{datetime.now().strftime('%Y%m%d')}.pdf",
                           mime="application/pdf", key="inv_dl_pdf")
    except ImportError:
        log_event("inventario", "error_fpdf_no_disponible")
        st.error("FPDF no disponible. Instalar con: pip install fpdf2")


def _exportar_inventario_excel(inventario: list, empresa: str) -> None:
    """Genera Excel con reporte completo de inventario y consumos."""
    import io

    df_inv = pd.DataFrame(inventario)
    columnas = {"item": "Insumo", "stock": "Stock actual", "stock_minimo": "Stock minimo",
                "categoria": "Categoria", "costo_unitario": "Costo unitario", "empresa": "Empresa"}
    df_inv = df_inv.rename(columns=columnas)
    df_inv = df_inv[list(columnas.values())]
    df_inv["Valor total"] = df_inv["Stock actual"] * df_inv["Costo unitario"].fillna(0)
    df_inv = df_inv.sort_values("Insumo")

    cons_emp = [c for c in st.session_state.get("consumos_db", [])
                if isinstance(c, dict) and c.get("empresa") == empresa]
    df_cons = pd.DataFrame(cons_emp) if cons_emp else pd.DataFrame()
    if not df_cons.empty:
        cols_cons = {"item": "Insumo", "cantidad": "Cantidad", "paciente": "Paciente",
                     "fecha": "Fecha", "empresa": "Empresa"}
        df_cons = df_cons.rename(columns=cols_cons)
        df_cons = df_cons[[c for c in cols_cons.values() if c in df_cons.columns]]
        df_cons = df_cons.sort_values("Fecha", ascending=False)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_inv.to_excel(writer, sheet_name="Inventario", index=False)
        ws = writer.sheets["Inventario"]
        for col in ws.columns:
            max_len = max(len(str(c.value or "")) for c in col) + 2
            ws.column_dimensions[col[0].column_letter].width = min(max_len, 40)

        if not df_cons.empty:
            df_cons.to_excel(writer, sheet_name="Insumos utilizados", index=False)
            ws2 = writer.sheets["Insumos utilizados"]
            for col in ws2.columns:
                max_len = max(len(str(c.value or "")) for c in col) + 2
                ws2.column_dimensions[col[0].column_letter].width = min(max_len, 40)

    st.download_button("Descargar Excel", buffer.getvalue(),
                       file_name=f"inventario_{empresa}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                       mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                       key="inv_dl_xlsx")
