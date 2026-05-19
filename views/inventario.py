from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

from core.alert_toasts import queue_toast
import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import bloque_estado_vacio, lista_plegable
from core.utils import cargar_json_asset, seleccionar_limite_registros, ahora
from core.db_sql import get_inventario_by_empresa, insert_inventario
from core.nextgen_sync import _obtener_uuid_empresa
from core.app_logging import log_event

_COLORES_CATEGORIA = [
    "#3b82f6", "#10b981", "#f59e0b", "#ef4444", "#8b5cf6",
    "#ec4899", "#06b6d4", "#84cc16", "#f97316", "#6366f1",
]


def render_inventario(mi_empresa):
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Inventario y stock de farmacia</h2>
            <p class="mc-hero-text">Gestiona medicamentos e insumos con un catalogo guiado para evitar errores de carga. La vista prioriza alertas, correcciones rapidas y control visual de stock critico.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Catalogo sugerido</span>
                <span class="mc-chip">Alerta de faltantes</span>
                <span class="mc-chip">Correccion de stock</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 1. Intentar leer desde PostgreSQL (Hybrid Read)
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
                # Sincronizar session_state para que fallback JSON sea consistente
                st.session_state["inventario_db"] = list(inv_mio)
    except Exception as e:
        log_event("error_leer_inventario_sql", str(e))

    # 2. Fallback a JSON si SQL falla o esta vacio
    if not inv_mio:
        inv_mio = [i for i in st.session_state.get("inventario_db", []) if i.get("empresa") == mi_empresa]
        
    def _umbral_critico(item):
        sm = int(item.get("stock_minimo", 0) or 0)
        return sm if sm > 0 else 10

    def _umbral_bajo(item):
        sm = int(item.get("stock_minimo", 0) or 0)
        return sm * 2 if sm > 0 else 25

    stock_critico = [i for i in inv_mio if i.get("stock", 0) <= _umbral_critico(i)]
    stock_bajo = [i for i in inv_mio if _umbral_critico(i) < i.get("stock", 0) <= _umbral_bajo(i)]
    total_unidades = sum(int(i.get("stock", 0) or 0) for i in inv_mio)

    # ── Valor total del inventario ──────────────────────────────
    _valor_total = sum(
        float(i.get("stock", 0)) * float(i.get("costo_unitario", 0) or 0)
        for i in inv_mio
        if float(i.get("costo_unitario", 0) or 0) > 0
    )

    # ── Consumo últimos 7 días ────────────────────────────────────
    _hace_7d = (ahora() - timedelta(days=7)).strftime("%d/%m/%Y")
    _cons_7d = [
        c for c in st.session_state.get("consumos_db", [])
        if c.get("empresa") == mi_empresa and c.get("fecha", "")[:10] >= _hace_7d
    ]
    _unid_7d = sum(int(c.get("cantidad", 0) or 0) for c in _cons_7d)

    # ── Métricas globales ──────────────────────────────────────
    if inv_mio:
        cols = st.columns(5)
        cols[0].metric("Items en inventario", len(inv_mio))
        cols[1].metric("🔴 Stock crítico", len(stock_critico), help="Segun stock_minimo de cada item o ≤10 por defecto")
        cols[2].metric("🟡 Stock bajo", len(stock_bajo), help="Por debajo del doble del stock_minimo o ≤25 por defecto")
        cols[3].metric("Unidades totales", total_unidades)
        cols[4].metric("Valor total", f"${_valor_total:,.0f}".replace(",", ".") if _valor_total > 0 else "—", help="Suma stock × costo_unitario")

    # ── Consumo últimos 7 días ─────────────────────────────────
    if _cons_7d:
        st.caption(f"📊 Consumos últimos 7 días: **{len(_cons_7d)} registros** ({_unid_7d} unidades)")

    # ── Ranking insumos más consumidos ─────────────────────────
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
        with lista_plegable("Stock crítico (según stock_minimo)", count=len(stock_critico), expanded=True, height=260):
            for item in stock_critico[:80]:
                _sm = int(item.get("stock_minimo", 0) or 0)
                _reponer = max(1, _sm * 2 - int(item.get("stock", 0)))
                lbl = f"**{_reponer}** para repo. sugerida" if _sm > 0 else ""
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
            <div class="mc-card"><h4>Carga guiada</h4><p>Usa el catalogo frecuente para minimizar errores de tipeo del personal.</p></div>
            <div class="mc-card"><h4>Nuevos items</h4><p>Tambien podes cargar un insumo nuevo cuando todavia no existe en el catalogo.</p></div>
            <div class="mc-card"><h4>Control visual</h4><p>Los faltantes se resaltan para detectar rapido que necesita reposicion.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "Stock crítico (≤10) está en un panel plegable. El formulario suma mercadería; la tabla completa y la corrección de ítems también se pueden plegar."
    )

    with st.form("form_inv", clear_on_submit=True):
        st.markdown("##### Ingreso de mercaderia")
        c1, c2, c3 = st.columns([2, 2, 1])
        lista_base_inv = ["-- Seleccionar del catalogo --"] + vademecum_base

        item_sel = c1.selectbox("1. Catalogo frecuente", lista_base_inv)
        nuevo_item = c2.text_input("2. Escribir insumo nuevo")
        cantidad = c3.number_input("Cantidad", min_value=1, value=10, step=1)
        c4, c5 = st.columns([1, 1])
        _cat_input = c4.text_input("Categoria (opcional)", placeholder="Ej: Medicamentos, Descartables")
        _costo_input = c5.number_input("Costo unitario $ (opcional)", min_value=0.0, value=0.0, step=1.0, format="%.2f")

        if st.form_submit_button("Sumar al stock", width='stretch', type="primary"):
            item_final = nuevo_item.strip().title() if nuevo_item.strip() else item_sel
            if item_final and item_final != "-- Seleccionar del catalogo --":
                try:
                    empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                    if empresa_uuid:
                        from core.database import supabase
                        res = supabase.table("inventario").select("id, stock_actual, stock_minimo, costo_unitario").eq("empresa_id", empresa_uuid).eq("nombre", item_final).execute()
                        if res.data:
                            existente = res.data[0]
                            _upd = {"stock_actual": existente["stock_actual"] + cantidad}
                            if _cat_input.strip():
                                _upd["categoria"] = _cat_input.strip()
                            if _costo_input > 0:
                                _upd["costo_unitario"] = _costo_input
                            supabase.table("inventario").update(_upd).eq("id", existente["id"]).execute()
                        else:
                            datos_sql = {"empresa_id": empresa_uuid, "nombre": item_final, "stock_actual": cantidad}
                            if _cat_input.strip():
                                datos_sql["categoria"] = _cat_input.strip()
                            if _costo_input > 0:
                                datos_sql["costo_unitario"] = _costo_input
                            insert_inventario(datos_sql)
                        log_event("inventario_sql_insert_update", f"Item: {item_final}")
                except Exception as e:
                    log_event("error_inventario_sql", str(e))

                encontrado = False
                if "inventario_db" not in st.session_state:
                    st.session_state["inventario_db"] = []
                for i in st.session_state["inventario_db"]:
                    if i.get("item", "").lower() == item_final.lower() and i.get("empresa") == mi_empresa:
                        i["stock"] = int(i.get("stock") or 0) + cantidad
                        if _cat_input.strip():
                            i["categoria"] = _cat_input.strip()
                        if _costo_input > 0:
                            i["costo_unitario"] = _costo_input
                        encontrado = True
                        break
                if not encontrado:
                    _entry = {"item": item_final, "stock": cantidad, "empresa": mi_empresa}
                    if _cat_input.strip():
                        _entry["categoria"] = _cat_input.strip()
                    if _costo_input > 0:
                        _entry["costo_unitario"] = _costo_input
                    st.session_state.setdefault("inventario_db", []).append(_entry)

                from core.database import _trim_db_list
                _trim_db_list("inventario_db", 1000)
                guardar_datos(spinner=True)
                queue_toast(f"Se agregaron {cantidad} unidades de {item_final}.")
                st.rerun()

    st.divider()

    if inv_mio:
        import pandas as pd
        df_stock = pd.DataFrame(inv_mio).rename(columns={
            "item": "Insumo", "stock": "Stock Actual", "stock_minimo": "Stock Minimo",
            "categoria": "Categoria", "costo_unitario": "Costo Unit.",
        })

        # ── Búsqueda, categoría y filtro de criticidad ──────────────
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
        df_filtrado["Stock Actual"] = pd.to_numeric(df_filtrado["Stock Actual"], errors="coerce").fillna(0).astype(int)
        if _busq_inv:
            df_filtrado = df_filtrado[df_filtrado["Insumo"].str.lower().str.contains(_busq_inv, na=False)]
        if _cat_sel != "Todas":
            df_filtrado = df_filtrado[df_filtrado.get("Categoria", "") == _cat_sel]
        if _filtro_crit == "Crítico":
            df_filtrado = df_filtrado[df_filtrado["Stock Actual"] <= df_filtrado.get("Stock Minimo", 10)]
        elif _filtro_crit == "Bajo":
            _b = df_filtrado["Stock Minimo"].fillna(10) * 2
            df_filtrado = df_filtrado[(df_filtrado["Stock Actual"] > df_filtrado["Stock Minimo"].fillna(10)) & (df_filtrado["Stock Actual"] <= _b)]
        elif _filtro_crit == "Normal (>25)":
            df_filtrado = df_filtrado[df_filtrado["Stock Actual"] > 25]
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
            sm = row.get("Stock Minimo", 10)
            return sm if sm > 0 else 10

        def colorear_stock(row):
            stock = row["Stock Actual"]
            umbral = _row_umbral(row)
            if stock <= umbral:
                return ["background-color: #3c1f1f; color: #ffb4b4; font-weight: bold"] * len(row)
            if stock <= umbral * 2:
                return ["background-color: #3c3217; color: #ffe08a; font-weight: 600"] * len(row)
            return ["background-color: #122033; color: #ffffff"] * len(row)

        _cols_tabla = ["Insumo", "Stock Actual", "Stock Minimo"]
        if "Categoria" in df_filtrado.columns and df_filtrado["Categoria"].notna().any():
            _cols_tabla.append("Categoria")
        if "Costo Unit." in df_filtrado.columns and (pd.to_numeric(df_filtrado["Costo Unit."], errors="coerce").fillna(0) > 0).any():
            _cols_tabla.append("Costo Unit.")

        styled = (
            df_filtrado.sort_values(by="Stock Actual", ascending=True)[_cols_tabla]
            .head(limite_stock)
            .style.apply(colorear_stock, axis=1)
        )
        with lista_plegable("Tabla de stock actual", count=len(df_filtrado), expanded=False, height=520):
            st.dataframe(styled, width='stretch', hide_index=True, height=496)
    else:
        bloque_estado_vacio(
            "Inventario vacío",
            "No hay insumos cargados para esta clínica.",
            sugerencia="Usá Ingreso de mercadería arriba: catálogo o insumo nuevo y cantidad.",
        )

    st.divider()

    if inv_mio:
        with lista_plegable("Ajuste manual, corrección y baja de insumos", expanded=False, height=None):
            st.markdown("#### Ajuste manual y correccion")
            item_a_editar = st.selectbox("Seleccionar insumo a corregir", [i["item"] for i in inv_mio], key="edit_sel")
            _item_data = next((i for i in inv_mio if i["item"] == item_a_editar), {})
            _s_act = _item_data.get("stock", 0)
            _s_min = int(_item_data.get("stock_minimo", 0) or 0)
            _costo = float(_item_data.get("costo_unitario", 0) or 0)
            c_aj1, c_aj2, c_aj3, c_aj4 = st.columns([1, 1, 1, 1])
            nuevo_stock = c_aj1.number_input("Stock real", min_value=0, value=_s_act, key="new_stock")
            nuevo_min = c_aj2.number_input("Stock mínimo", min_value=0, value=_s_min, key="new_min")
            nuevo_costo = c_aj3.number_input("Costo unitario $", min_value=0.0, value=_costo, step=0.5, format="%.2f", key="new_costo")
            if c_aj4.button("Guardar cambios", width='stretch', type="primary"):
                cambios = {"stock_actual": nuevo_stock, "stock_minimo": nuevo_min, "costo_unitario": nuevo_costo}
                try:
                    empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                    if empresa_uuid:
                        from core.database import supabase
                        res = supabase.table("inventario").select("id").eq("empresa_id", empresa_uuid).eq("nombre", item_a_editar).execute()
                        if res.data:
                            supabase.table("inventario").update(cambios).eq("id", res.data[0]["id"]).execute()
                        log_event("inventario_sql_update", f"Item: {item_a_editar}")
                except Exception as e:
                    log_event("error_inventario_sql_update", str(e))
                if "inventario_db" in st.session_state:
                    for i in st.session_state["inventario_db"]:
                        if i["item"] == item_a_editar and i.get("empresa") == mi_empresa:
                            i["stock"] = nuevo_stock
                            i["stock_minimo"] = nuevo_min
                            i["costo_unitario"] = nuevo_costo
                            break
                guardar_datos(spinner=True)
                queue_toast(f"{item_a_editar}: stock={nuevo_stock}, mínimo={nuevo_min}, costo=${nuevo_costo:.2f}")
                st.rerun()

            col_del1, col_del2 = st.columns([3, 1])
            del_item = col_del1.selectbox("Eliminar insumo por completo", [i["item"] for i in inv_mio], key="del_sel")
            confirmar = col_del1.checkbox("Confirmar eliminacion definitiva", key="conf_del_item")
            if col_del2.button("Eliminar insumo", width='stretch', type="secondary", disabled=not confirmar):
                # 1. Eliminar en SQL (Dual-Write)
                try:
                    empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                    if empresa_uuid:
                        from core.database import supabase
                        if supabase is not None:
                            res = supabase.table("inventario").select("id").eq("empresa_id", empresa_uuid).eq("nombre", del_item).execute()
                            if res.data:
                                supabase.table("inventario").delete().eq("id", res.data[0]["id"]).execute()
                            log_event("inventario_sql_delete", f"Item: {del_item}")
                        else:
                            log_event("inventario_sql_delete", "Supabase offline; se elimina solo en JSON local")
                except Exception as e:
                    log_event("error_inventario_sql_delete", str(e))

                # 2. Eliminar en JSON (Legacy)
                if "inventario_db" in st.session_state:
                    st.session_state["inventario_db"] = [
                        i for i in st.session_state["inventario_db"] if not (i["item"] == del_item and i.get("empresa") == mi_empresa)
                    ]
                guardar_datos(spinner=True)
                queue_toast(f"Se elimino {del_item} del inventario.")
                st.rerun()
