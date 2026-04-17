from core.alert_toasts import queue_toast
import pandas as pd
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
                        "id_sql": i.get("id")
                    })
    except Exception as e:
        log_event("error_leer_inventario_sql", str(e))

    # 2. Fallback a JSON si SQL falla o esta vacio
    if not inv_mio:
        inv_mio = [i for i in st.session_state.get("inventario_db", []) if i.get("empresa") == mi_empresa]
        
    stock_critico = [i for i in inv_mio if i.get("stock", 0) <= 10]

    if stock_critico:
        with lista_plegable("Stock crítico (≤10 unidades)", count=len(stock_critico), expanded=False, height=260):
            for item in stock_critico[:80]:
                st.error(f"{item.get('item')} -> quedan {item.get('stock', 0)} unidades")

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

        if st.form_submit_button("Sumar al stock", use_container_width=True, type="primary"):
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
                    st.error(f"Error al guardar en SQL: {e}")

                # 2. Guardar en JSON (Legacy)
                encontrado = False
                if "inventario_db" not in st.session_state:
                    st.session_state["inventario_db"] = []
                    
                for i in st.session_state["inventario_db"]:
                    if i.get("item", "").lower() == item_final.lower() and i.get("empresa") == mi_empresa:
                        i["stock"] = i.get("stock", 0) + cantidad
                        encontrado = True
                        break

                if not encontrado:
                    st.session_state["inventario_db"].append({"item": item_final, "stock": cantidad, "empresa": mi_empresa})

                guardar_datos(spinner=True)
                queue_toast(f"Se agregaron {cantidad} unidades de {item_final}.")
                st.rerun()

    st.divider()

    if inv_mio:
        df_stock = pd.DataFrame(inv_mio).rename(columns={"item": "Insumo", "stock": "Stock Actual"})
        limite_stock = seleccionar_limite_registros(
            "Insumos a mostrar",
            len(df_stock),
            key="inventario_limite_stock",
            default=50,
            opciones=(10, 20, 50, 100, 200, 500),
        )

        def colorear_stock(row):
            stock = row["Stock Actual"]
            if stock <= 10:
                return ["background-color: #3c1f1f; color: #ffb4b4; font-weight: bold"] * len(row)
            if stock <= 25:
                return ["background-color: #3c3217; color: #ffe08a; font-weight: 600"] * len(row)
            return ["background-color: #122033; color: #ffffff"] * len(row)

        styled = (
            df_stock.sort_values(by="Stock Actual", ascending=True)[["Insumo", "Stock Actual"]]
            .head(limite_stock)
            .style.apply(colorear_stock, axis=1)
        )
        with lista_plegable("Tabla de stock actual", count=len(df_stock), expanded=False, height=520):
            st.dataframe(styled, use_container_width=True, hide_index=True, height=496)
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

            if col3.button("Actualizar stock", use_container_width=True):
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
                    st.error(f"Error al actualizar en SQL: {e}")

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
            if col_del2.button("Eliminar insumo", use_container_width=True, type="secondary", disabled=not confirmar):
                # 1. Eliminar en SQL (Dual-Write)
                try:
                    empresa_uuid = _obtener_uuid_empresa(mi_empresa)
                    if empresa_uuid:
                        from core.database import supabase
                        res = supabase.table("inventario").select("id").eq("empresa_id", empresa_uuid).eq("nombre", del_item).execute()
                        if res.data:
                            supabase.table("inventario").delete().eq("id", res.data[0]["id"]).execute()
                        log_event("inventario_sql_delete", f"Item: {del_item}")
                except Exception as e:
                    log_event("error_inventario_sql_delete", str(e))
                    st.error(f"Error al eliminar en SQL: {e}")

                # 2. Eliminar en JSON (Legacy)
                if "inventario_db" in st.session_state:
                    st.session_state["inventario_db"] = [
                        i for i in st.session_state["inventario_db"] if not (i["item"] == del_item and i.get("empresa") == mi_empresa)
                    ]
                guardar_datos(spinner=True)
                queue_toast(f"Se elimino {del_item} del inventario.")
                st.rerun()
