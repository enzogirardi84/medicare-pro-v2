import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros


def render_materiales(paciente_sel, mi_empresa, user):
    if not paciente_sel:
        st.info("Selecciona un paciente en el menu lateral.")
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

    inv_mi_empresa = sorted(
        [i for i in st.session_state.get("inventario_db", []) if i.get("empresa") == mi_empresa],
        key=lambda x: x.get("item", "").lower(),
    )

    if not inv_mi_empresa:
        st.warning("No hay insumos cargados en el inventario. Ve a Inventario primero.")
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
            if st.form_submit_button("Registrar consumo", use_container_width=True, type="primary"):
                stock_actualizado = False
                for i in st.session_state["inventario_db"]:
                    if i["item"] == insumo_sel and i.get("empresa") == mi_empresa:
                        stock_actual = i.get("stock", 0)
                        if stock_actual < cant_usada:
                            st.warning(f"Stock insuficiente. Quedaran {stock_actual - cant_usada} unidades.")
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
        if st.button("Borrar ultimo consumo", use_container_width=True):
            if st.checkbox("Confirmar borrado", key="conf_del_consumo"):
                st.session_state["consumos_db"].remove(cons_paciente[-1])
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
        st.info("Aun no se han registrado consumos de materiales para este paciente.")
