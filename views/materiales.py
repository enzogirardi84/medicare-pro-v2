import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros


def _restaurar_stock(mi_empresa, insumo, cantidad):
    for item in st.session_state.get("inventario_db", []):
        if item.get("item") == insumo and item.get("empresa") == mi_empresa:
            item["stock"] = item.get("stock", 0) + cantidad
            return
    if insumo and cantidad > 0:
        st.session_state.setdefault("inventario_db", []).append(
            {"item": insumo, "stock": cantidad, "empresa": mi_empresa}
        )


def render_materiales(paciente_sel, mi_empresa, user):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Registro de materiales descartables</h2>
            <p class="mc-hero-text">Descuenta insumos del stock y los deja registrados en la historia del paciente. Esta pantalla esta pensada para que el personal cargue rapido y con el menor margen de error posible.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Elegir insumo</span>
                <span class="mc-chip">Descontar cantidad</span>
                <span class="mc-chip">Guardar en historia</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Insumo", "Elegi del inventario de la empresa."),
            ("Stock", "El descuento actualiza existencias al instante."),
            ("Historia", "El consumo queda en el legajo del paciente."),
        ]
    )
    st.caption(
        "El consumo se registra por paciente y descuenta del inventario de tu clinica. Si no hay stock cargado, entra antes a **Inventario**."
    )

    inv_mi_empresa = sorted(
        [i for i in st.session_state.get("inventario_db", []) if i.get("empresa") == mi_empresa],
        key=lambda x: x.get("item", "").lower(),
    )

    if not inv_mi_empresa:
        bloque_estado_vacio(
            "Sin stock en inventario",
            "No hay insumos cargados para tu clínica.",
            sugerencia="Entrá al módulo Inventario y cargá mercadería antes de registrar consumos.",
        )
    else:
        st.markdown(
            """
            <div class="mc-callout">
                <strong>Sugerencia:</strong> registrar el consumo apenas termina la practica ayuda a mantener el stock real y evita olvidos al cierre del dia.
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("form_mat", clear_on_submit=True):
            c1, c2 = st.columns([3, 1])
            insumo_sel = c1.selectbox("Seleccionar insumo utilizado", [i["item"] for i in inv_mi_empresa], key="select_insumo")
            cant_usada = c2.number_input("Cantidad", min_value=1, value=1, step=1)
            stock_disponible = next((i.get("stock", 0) for i in inv_mi_empresa if i.get("item") == insumo_sel), 0)
            st.caption(f"Stock disponible: {stock_disponible} unidad(es)")
            if st.form_submit_button("Registrar consumo", use_container_width=True, type="primary"):
                stock_actualizado = False
                for i in st.session_state["inventario_db"]:
                    if i["item"] == insumo_sel and i.get("empresa") == mi_empresa:
                        stock_actual = i.get("stock", 0)
                        if stock_actual < cant_usada:
                            st.error(f"Stock insuficiente para registrar {cant_usada}. Solo hay {stock_actual} unidad(es) disponibles.")
                            break
                        i["stock"] = stock_actual - cant_usada
                        stock_actualizado = True
                        break
                if stock_actualizado:
                    st.session_state["consumos_db"].append(
                        {
                            "paciente": paciente_sel,
                            "insumo": insumo_sel,
                            "cantidad": cant_usada,
                            "fecha": ahora().strftime("%d/%m/%Y %H:%M"),
                            "firma": user["nombre"],
                            "empresa": mi_empresa,
                        }
                    )
                    guardar_datos()
                    st.success(f"{cant_usada} x {insumo_sel} registrado correctamente.")
                    st.rerun()
                else:
                    st.error("Error al actualizar el stock.")

    cons_paciente = [c for c in st.session_state.get("consumos_db", []) if c.get("paciente") == paciente_sel]
    if cons_paciente:
        st.divider()
        st.markdown("#### Materiales registrados para este paciente")
        col_chk, col_btn = st.columns([1.2, 2.8])
        confirmar_borrado = col_chk.checkbox("Confirmar", key="conf_del_consumo")
        if col_btn.button("Borrar ultimo consumo", use_container_width=True, disabled=not confirmar_borrado):
            ultimo_consumo = cons_paciente[-1]
            st.session_state["consumos_db"].remove(ultimo_consumo)
            _restaurar_stock(mi_empresa, ultimo_consumo.get("insumo"), int(ultimo_consumo.get("cantidad", 0) or 0))
            guardar_datos()
            st.success("Consumo eliminado correctamente.")
            st.rerun()

        limite = seleccionar_limite_registros(
            "Consumos a mostrar",
            len(cons_paciente),
            key="materiales_limite_consumos",
            default=50,
            opciones=(10, 20, 50, 100, 200, 500),
        )
        df_cons = pd.DataFrame(cons_paciente[-limite:])
        if not df_cons.empty:
            df_cons["fecha_dt"] = pd.to_datetime(df_cons["fecha"], format="%d/%m/%Y %H:%M", errors="coerce")
            df_cons = df_cons.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt", "paciente", "empresa"], errors="ignore")
            df_cons = df_cons.rename(
                columns={
                    "fecha": "Fecha y Hora",
                    "insumo": "Insumo Utilizado",
                    "cantidad": "Cantidad",
                    "firma": "Registrado por",
                }
            )
            mostrar_dataframe_con_scroll(df_cons, height=380)
    else:
        bloque_estado_vacio(
            "Sin consumos registrados",
            "Todavía no hay materiales descartables cargados para este paciente.",
            sugerencia="Cuando haya inventario, usá el formulario de arriba para descontar y dejar traza.",
        )
