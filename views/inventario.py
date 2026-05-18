from core.alert_toasts import queue_toast
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import bloque_estado_vacio, lista_plegable
from core.utils import cargar_json_asset, seleccionar_limite_registros
from core.db_sql import get_inventario_by_empresa, insert_inventario
from core.nextgen_sync import _obtener_uuid_empresa
from core.app_logging import log_event


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

    # ── Métricas globales ──────────────────────────────────────
    if inv_mio:
        _mc1, _mc2, _mc3, _mc4 = st.columns(4)
        _mc1.metric("Items en inventario", len(inv_mio))
        _mc2.metric("🔴 Stock crítico", len(stock_critico), help="Segun stock_minimo de cada item o ≤10 por defecto")
        _mc3.metric("🟡 Stock bajo", len(stock_bajo), help="Por debajo del doble del stock_minimo o ≤25 por defecto")
        _mc4.metric("Unidades totales", total_unidades)

    # ── Ranking insumos más consumidos ─────────────────────────
    from collections import Counter
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
            with st.expander("📊 Top insumos más consumidos", expanded=False):
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

        if st.form_submit_button("Sumar al stock", width='stretch', type="primary"):
            item_final = nuevo_item.strip().title() if nuevo_item.strip() else item_sel
            if item_final and item_final != "-- Seleccionar del catalogo --":
                # 1. Guardar en SQL (Dual-Write)
                try:
                    empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                    if empresa_uuid:
                        # Buscar si ya existe en SQL
                        from core.database import supabase
                        res = supabase.table("inventario").select("id, stock_actual").eq("empresa_id", empresa_uuid).eq("nombre", item_final).execute()
                        if res.data:
                            # Actualizar stock
                            nuevo_stock_sql = res.data[0]["stock_actual"] + cantidad
                            supabase.table("inventario").update({"stock_actual": nuevo_stock_sql}).eq("id", res.data[0]["id"]).execute()
                        else:
                            # Insertar nuevo
                            datos_sql = {
                                "empresa_id": empresa_uuid,
                                "nombre": item_final,
                                "stock_actual": cantidad
                            }
                            insert_inventario(datos_sql)
                        log_event("inventario_sql_insert_update", f"Item: {item_final}")
                except Exception as e:
                    log_event("error_inventario_sql", str(e))

                # 2. Guardar en JSON (Legacy)
                encontrado = False
                if "inventario_db" not in st.session_state:
                    st.session_state["inventario_db"] = []
                    
                for i in st.session_state["inventario_db"]:
                    if i.get("item", "").lower() == item_final.lower() and i.get("empresa") == mi_empresa:
                        i["stock"] = int(i.get("stock") or 0) + cantidad
                        encontrado = True
                        break

                if not encontrado:
                    st.session_state.setdefault("inventario_db", [])
                    st.session_state["inventario_db"].append({"item": item_final, "stock": cantidad, "empresa": mi_empresa})

                from core.database import _trim_db_list
                _trim_db_list("inventario_db", 1000)
                guardar_datos(spinner=True)
                queue_toast(f"Se agregaron {cantidad} unidades de {item_final}.")
                st.rerun()

    st.divider()

    if inv_mio:
        import pandas as pd
        df_stock = pd.DataFrame(inv_mio).rename(columns={"item": "Insumo", "stock": "Stock Actual", "stock_minimo": "Stock Minimo"})

        # ── Búsqueda y filtro de criticidad ────────────────────────
        _col_b, _col_f = st.columns([2, 1])
        _busq_inv = _col_b.text_input(
            "🔍 Buscar insumo",
            placeholder="Nombre del insumo...",
            key="inventario_busqueda",
        ).strip().lower()
        _filtro_crit = _col_f.selectbox(
            "Mostrar",
            ["Todos", "Solo críticos (≤10)", "Stock bajo (≤25)", "Stock normal (>25)"],
            key="inventario_filtro",
        )
        df_filtrado = df_stock.copy()
        df_filtrado["Stock Actual"] = pd.to_numeric(df_filtrado["Stock Actual"], errors="coerce").fillna(0).astype(int)
        if _busq_inv:
            df_filtrado = df_filtrado[df_filtrado["Insumo"].str.lower().str.contains(_busq_inv, na=False)]
        if _filtro_crit == "Solo críticos (≤10)":
            df_filtrado = df_filtrado[df_filtrado["Stock Actual"] <= 10]
        elif _filtro_crit == "Stock bajo (≤25)":
            df_filtrado = df_filtrado[(df_filtrado["Stock Actual"] > 10) & (df_filtrado["Stock Actual"] <= 25)]
        elif _filtro_crit == "Stock normal (>25)":
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
            sm = row.get("stock_minimo", 10)
            return sm if sm > 0 else 10

        def colorear_stock(row):
            stock = row["Stock Actual"]
            umbral = _row_umbral(row)
            if stock <= umbral:
                return ["background-color: #3c1f1f; color: #ffb4b4; font-weight: bold"] * len(row)
            if stock <= umbral * 2:
                return ["background-color: #3c3217; color: #ffe08a; font-weight: 600"] * len(row)
            return ["background-color: #122033; color: #ffffff"] * len(row)

        styled = (
            df_filtrado.sort_values(by="Stock Actual", ascending=True)[["Insumo", "Stock Actual", "Stock Minimo"]]
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
            col1, col2, col3 = st.columns([2, 1, 1])
            item_a_editar = col1.selectbox("Seleccionar insumo a corregir", [i["item"] for i in inv_mio], key="edit_sel")
            stock_actual = next((i.get("stock", 0) for i in inv_mio if i["item"] == item_a_editar), 0)
            nuevo_stock = col2.number_input("Nuevo stock real", min_value=0, value=stock_actual, key="new_stock")

            if col3.button("Actualizar stock", width='stretch'):
                # 1. Actualizar en SQL (Dual-Write)
                try:
                    empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                    if empresa_uuid:
                        from core.database import supabase
                        res = supabase.table("inventario").select("id").eq("empresa_id", empresa_uuid).eq("nombre", item_a_editar).execute()
                        if res.data:
                            supabase.table("inventario").update({"stock_actual": nuevo_stock}).eq("id", res.data[0]["id"]).execute()
                        log_event("inventario_sql_update", f"Item: {item_a_editar}")
                except Exception as e:
                    log_event("error_inventario_sql_update", str(e))

                # 2. Actualizar en JSON (Legacy)
                if "inventario_db" in st.session_state:
                    for i in st.session_state["inventario_db"]:
                        if i["item"] == item_a_editar and i.get("empresa") == mi_empresa:
                            i["stock"] = nuevo_stock
                            break
                guardar_datos(spinner=True)
                queue_toast(f"Stock actualizado a {nuevo_stock} unidades.")
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
