import time
from html import escape

import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import bloque_estado_vacio
from core.utils import cargar_json_asset, seleccionar_limite_registros


CATALOGO_PLACEHOLDER = "-- Seleccionar del catalogo --"


def _stock_num(item) -> int:
    try:
        return int(item.get("stock", 0) or 0)
    except Exception:
        return 0


def _maybe_toast_inventory_status(total_items, sin_stock, stock_bajo):
    firma = f"{total_items}|{sin_stock}|{stock_bajo}"
    ultima_firma = st.session_state.get("_mc_inventory_toast_signature")
    ultimo_ts = float(st.session_state.get("_mc_inventory_toast_ts") or 0.0)
    ahora_ts = time.time()
    if firma == ultima_firma and ahora_ts - ultimo_ts < 45:
        return

    if total_items == 0:
        mensaje = "Inventario vacio. Carga el primer insumo para empezar a monitorear stock."
    elif sin_stock or stock_bajo:
        mensaje = f"Insumos: {sin_stock} sin stock, {stock_bajo} con stock bajo (<=10 u)."
    else:
        mensaje = f"Inventario estable: {total_items} item(s) en rango."

    st.toast(mensaje, icon=":material/inventory_2:")
    st.session_state["_mc_inventory_toast_signature"] = firma
    st.session_state["_mc_inventory_toast_ts"] = ahora_ts


def _render_inventory_hero(inv_mio, stock_critico, sin_stock, stock_bajo):
    total_items = len(inv_mio)
    total_unidades = sum(_stock_num(item) for item in inv_mio)
    estables = max(0, total_items - len(stock_critico))

    st.markdown(
        f"""
        <div class="mc-hero mc-hero--inventory">
            <div class="mc-hero-headline-row">
                <span class="mc-chip">Farmacia y logistica</span>
                <span class="mc-chip {'mc-chip-danger' if sin_stock else 'mc-chip-success'}">{sin_stock} sin stock</span>
                <span class="mc-chip {'mc-chip-warning' if stock_bajo else 'mc-chip-success'}">{stock_bajo} con stock bajo</span>
            </div>
            <h2 class="mc-hero-title">Inventario y stock de farmacia</h2>
            <p class="mc-hero-text">
                Controla medicamentos e insumos con una vista mas clara, priorizando faltantes,
                reposicion rapida y correcciones seguras del stock real.
            </p>
            <div class="mc-inventory-hero-stats">
                <div class="mc-inventory-hero-stat">
                    <span class="mc-inventory-hero-stat-value">{total_items}</span>
                    <span class="mc-inventory-hero-stat-label">items cargados</span>
                </div>
                <div class="mc-inventory-hero-stat">
                    <span class="mc-inventory-hero-stat-value">{total_unidades}</span>
                    <span class="mc-inventory-hero-stat-label">unidades totales</span>
                </div>
                <div class="mc-inventory-hero-stat">
                    <span class="mc-inventory-hero-stat-value">{len(stock_critico)}</span>
                    <span class="mc-inventory-hero-stat-label">alertas activas</span>
                </div>
                <div class="mc-inventory-hero-stat">
                    <span class="mc-inventory-hero-stat-value">{estables}</span>
                    <span class="mc-inventory-hero-stat-label">items estables</span>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_inventory_alert_banner(stock_critico, sin_stock, stock_bajo):
    if not stock_critico:
        st.markdown(
            """
            <div class="mc-inventory-banner mc-inventory-banner--ok">
                <div class="mc-inventory-banner-main">
                    <span class="mc-inventory-banner-kicker">Estado general</span>
                    <div class="mc-inventory-banner-title">Stock saludable en este momento</div>
                    <p class="mc-inventory-banner-copy">No hay insumos en cero ni por debajo del umbral critico. Puedes seguir usando la carga rapida para reponer o ampliar catalogo.</p>
                </div>
                <div class="mc-inventory-banner-side">
                    <span class="mc-chip mc-chip-success">Todo en rango</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        return

    items_html = []
    for item in stock_critico[:6]:
        stock = _stock_num(item)
        modifier = "mc-stock-alert-card--danger" if stock <= 0 else "mc-stock-alert-card--warning"
        estado = "Sin stock" if stock <= 0 else f"{stock} u disponibles"
        items_html.append(
            f"""
            <div class="mc-stock-alert-card {modifier}">
                <div class="mc-stock-alert-title">{escape(str(item.get("item", "Insumo"))[:56])}</div>
                <div class="mc-stock-alert-meta">{estado}</div>
            </div>
            """
        )

    st.markdown(
        f"""
        <div class="mc-inventory-banner mc-inventory-banner--danger">
            <div class="mc-inventory-banner-main">
                <span class="mc-inventory-banner-kicker">Atencion: faltantes o stock bajo</span>
                <div class="mc-inventory-banner-title">{len(stock_critico)} item(s) requieren accion</div>
                <p class="mc-inventory-banner-copy">
                    Hay <strong>{sin_stock}</strong> sin stock y <strong>{stock_bajo}</strong> con nivel critico (<=10 u).
                    Revisa el detalle, corrige existencias o ingresa reposicion desde el formulario.
                </p>
                <div class="mc-critical-banner-chip-row">
                    <span class="mc-chip mc-chip-danger">Reposicion prioritaria</span>
                    <span class="mc-chip">Ajuste rapido</span>
                    <span class="mc-chip">Control visual</span>
                </div>
            </div>
            <div class="mc-inventory-banner-side">
                {''.join(items_html)}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_inventario(mi_empresa):
    inv_mio = [item for item in st.session_state.get("inventario_db", []) if item.get("empresa") == mi_empresa]
    stock_critico = [item for item in inv_mio if _stock_num(item) <= 10]
    sin_stock = sum(1 for item in inv_mio if _stock_num(item) <= 0)
    stock_bajo = sum(1 for item in inv_mio if 0 < _stock_num(item) <= 10)
    _maybe_toast_inventory_status(len(inv_mio), sin_stock, stock_bajo)

    _render_inventory_hero(inv_mio, stock_critico, sin_stock, stock_bajo)
    _render_inventory_alert_banner(stock_critico, sin_stock, stock_bajo)

    try:
        vademecum_base = cargar_json_asset("vademecum.json")
    except Exception:
        vademecum_base = []

    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>Carga guiada</h4><p>Usa el catalogo sugerido para reducir errores de tipeo y acelerar reposiciones.</p></div>
            <div class="mc-card"><h4>Nuevo insumo</h4><p>Si un material todavia no existe, puedes crearlo en el momento y dejarlo listo para proximas cargas.</p></div>
            <div class="mc-card"><h4>Control de alerta</h4><p>Las tarjetas superiores priorizan faltantes y stock bajo para que el equipo actue antes de quedarse sin insumos.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    st.caption(
        "La franja superior resume el estado del deposito. Debajo puedes reponer, revisar el stock completo y hacer correcciones manuales."
    )

    if stock_critico:
        with st.expander(f"Detalle de faltantes y stock bajo ({len(stock_critico)})", expanded=True):
            cards = []
            for item in stock_critico:
                stock = _stock_num(item)
                estado = "Sin stock" if stock <= 0 else f"Stock bajo: {stock} u"
                detalle = "Reponer hoy" if stock <= 0 else "Conviene reponer o verificar consumo"
                clase = "mc-stock-alert-card--danger" if stock <= 0 else "mc-stock-alert-card--warning"
                cards.append(
                    f"""
                    <div class="mc-stock-alert-card {clase}">
                        <div class="mc-stock-alert-title">{escape(str(item.get("item", "Insumo"))[:64])}</div>
                        <div class="mc-stock-alert-meta">{estado}</div>
                        <div class="mc-stock-alert-note">{detalle}</div>
                    </div>
                    """
                )
            st.markdown(f'<div class="mc-stock-alert-grid">{"".join(cards)}</div>', unsafe_allow_html=True)

    with st.form("form_inv", clear_on_submit=True):
        st.markdown("### Reposicion rapida")
        c1, c2, c3 = st.columns([2, 2, 1])
        lista_base_inv = [CATALOGO_PLACEHOLDER] + vademecum_base

        item_sel = c1.selectbox("1. Catalogo frecuente", lista_base_inv)
        nuevo_item = c2.text_input("2. Escribir insumo nuevo")
        cantidad = c3.number_input("Cantidad", min_value=1, value=10, step=1)

        if st.form_submit_button("Sumar al stock", use_container_width=True, type="primary"):
            item_final = nuevo_item.strip().title() if nuevo_item.strip() else item_sel
            if item_final and item_final != CATALOGO_PLACEHOLDER:
                encontrado = False
                for item in st.session_state["inventario_db"]:
                    if item.get("item", "").lower() == item_final.lower() and item.get("empresa") == mi_empresa:
                        item["stock"] = _stock_num(item) + cantidad
                        encontrado = True
                        break

                if not encontrado:
                    st.session_state["inventario_db"].append({"item": item_final, "stock": cantidad, "empresa": mi_empresa})

                guardar_datos()
                st.success(f"Se agregaron {cantidad} unidades de {item_final}.")
                st.rerun()

    st.divider()

    if inv_mio:
        st.markdown("### Stock actual")
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
            if stock <= 0:
                return ["background-color: #471515; color: #fecaca; font-weight: 800"] * len(row)
            if stock <= 10:
                return ["background-color: #3c1f1f; color: #ffb4b4; font-weight: 700"] * len(row)
            if stock <= 25:
                return ["background-color: #3c3217; color: #ffe08a; font-weight: 600"] * len(row)
            return ["background-color: #122033; color: #ffffff"] * len(row)

        df_ordenado = df_stock.sort_values(by="Stock Actual", ascending=True)[["Insumo", "Stock Actual"]].head(limite_stock)
        styled = df_ordenado.style.apply(colorear_stock, axis=1)
        tabla_height = min(520, max(220, 96 + (len(df_ordenado) * 35)))
        with st.container(border=True):
            st.caption("Ordenado de menor a mayor stock para detectar faltantes mas rapido.")
            st.dataframe(styled, use_container_width=True, hide_index=True, height=tabla_height)
    else:
        bloque_estado_vacio(
            "Inventario vacio",
            "No hay insumos cargados para esta clinica.",
            sugerencia="Usa Reposicion rapida para ingresar tu primer item y empezar a monitorear stock.",
        )

    st.divider()

    if inv_mio:
        st.markdown("### Ajuste manual y correccion")
        st.caption("Usa esta seccion para corregir diferencias de conteo real o limpiar insumos que ya no se utilizan.")

        col1, col2, col3 = st.columns([2, 1, 1])
        item_a_editar = col1.selectbox("Seleccionar insumo a corregir", [item["item"] for item in inv_mio], key="edit_sel")
        stock_actual = next((_stock_num(item) for item in inv_mio if item["item"] == item_a_editar), 0)
        nuevo_stock = col2.number_input("Nuevo stock real", min_value=0, value=stock_actual, key="new_stock")

        if col3.button("Actualizar stock", use_container_width=True):
            for item in st.session_state["inventario_db"]:
                if item["item"] == item_a_editar and item.get("empresa") == mi_empresa:
                    item["stock"] = nuevo_stock
                    break
            guardar_datos()
            st.success(f"Stock actualizado a {nuevo_stock} unidades.")
            st.rerun()

        col_del1, col_del2 = st.columns([3, 1])
        del_item = col_del1.selectbox("Eliminar insumo por completo", [item["item"] for item in inv_mio], key="del_sel")
        confirmar = col_del1.checkbox("Confirmar eliminacion definitiva", key="conf_del_item")
        if col_del2.button("Eliminar insumo", use_container_width=True, type="secondary", disabled=not confirmar):
            st.session_state["inventario_db"] = [
                item
                for item in st.session_state["inventario_db"]
                if not (item["item"] == del_item and item.get("empresa") == mi_empresa)
            ]
            guardar_datos()
            st.success(f"Se elimino {del_item} del inventario.")
            st.rerun()
