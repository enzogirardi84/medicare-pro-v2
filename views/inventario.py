import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.utils import cargar_json_asset


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

    inv_mio = [i for i in st.session_state.get("inventario_db", []) if i.get("empresa") == mi_empresa]
    stock_critico = [i for i in inv_mio if i.get("stock", 0) <= 10]

    if stock_critico:
        st.markdown("#### Stock critico")
        with st.container(height=260, border=True):
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
                encontrado = False
                for i in st.session_state["inventario_db"]:
                    if i.get("item", "").lower() == item_final.lower() and i.get("empresa") == mi_empresa:
                        i["stock"] = i.get("stock", 0) + cantidad
                        encontrado = True
                        break

                if not encontrado:
                    st.session_state["inventario_db"].append({"item": item_final, "stock": cantidad, "empresa": mi_empresa})

                guardar_datos()
                st.success(f"Se agregaron {cantidad} unidades de {item_final}.")
                st.rerun()

    st.divider()

    if inv_mio:
        st.markdown("#### Stock actual")
        df_stock = pd.DataFrame(inv_mio).rename(columns={"item": "Insumo", "stock": "Stock Actual"})

        def colorear_stock(row):
            stock = row["Stock Actual"]
            if stock <= 10:
                return ["background-color: #3c1f1f; color: #ffb4b4; font-weight: bold"] * len(row)
            if stock <= 25:
                return ["background-color: #3c3217; color: #ffe08a; font-weight: 600"] * len(row)
            return ["background-color: #122033; color: #ffffff"] * len(row)

        styled = df_stock[["Insumo", "Stock Actual"]].style.apply(colorear_stock, axis=1)
        with st.container(height=520, border=True):
            st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info("Aun no hay insumos cargados en el inventario.")

    st.divider()

    if inv_mio:
        st.markdown("#### Ajuste manual y correccion")
        col1, col2, col3 = st.columns([2, 1, 1])
        item_a_editar = col1.selectbox("Seleccionar insumo a corregir", [i["item"] for i in inv_mio], key="edit_sel")
        stock_actual = next((i.get("stock", 0) for i in inv_mio if i["item"] == item_a_editar), 0)
        nuevo_stock = col2.number_input("Nuevo stock real", min_value=0, value=stock_actual, key="new_stock")

        if col3.button("Actualizar stock", use_container_width=True):
            for i in st.session_state["inventario_db"]:
                if i["item"] == item_a_editar and i.get("empresa") == mi_empresa:
                    i["stock"] = nuevo_stock
                    break
            guardar_datos()
            st.success(f"Stock actualizado a {nuevo_stock} unidades.")
            st.rerun()

        col_del1, col_del2 = st.columns([3, 1])
        del_item = col_del1.selectbox("Eliminar insumo por completo", [i["item"] for i in inv_mio], key="del_sel")
        confirmar = col_del1.checkbox("Confirmar eliminacion definitiva", key="conf_del_item")
        if col_del2.button("Eliminar insumo", use_container_width=True, type="secondary", disabled=not confirmar):
            st.session_state["inventario_db"] = [
                i for i in st.session_state["inventario_db"] if not (i["item"] == del_item and i.get("empresa") == mi_empresa)
            ]
            guardar_datos()
            st.success(f"Se elimino {del_item} del inventario.")
            st.rerun()
