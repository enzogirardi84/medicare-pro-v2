import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros


def render_balance(paciente_sel, user):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Balance hidrico</h2>
            <p class="mc-hero-text">Ingresos y egresos en ml por turno de guardia, con balance calculado y tabla historica acotada para no saturar el celular.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Turnos</span>
                <span class="mc-chip">Ingresos / egresos</span>
                <span class="mc-chip">Shift en ml</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ("Turno", "Agrupa ingresos y egresos por franja de guardia."),
            ("Balance", "El total neto se calcula al guardar cada registro."),
            ("Historial", "Consulta controles previos sin saturar la pantalla."),
        ]
    )
    st.caption(
        "Completa fecha, hora y turno; suma todos los ingresos y egresos del control y guarda. El shift en ml aparece abajo junto al historial y metricas de tendencia."
    )

    with st.form("bal", clear_on_submit=True):
        col_meta1, col_meta2, col_meta3 = st.columns(3)
        fecha_bal = col_meta1.date_input("Fecha de control", value=ahora().date(), key="fecha_bal")
        hora_bal_str = col_meta2.text_input("Hora exacta (HH:MM)", value=ahora().strftime("%H:%M"), key="hora_bal")
        turno = col_meta3.selectbox("Turno de guardia", ["Manana (06 a 14hs)", "Tarde (14 a 22hs)", "Noche (22 a 06hs)"])

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Ingresos (ml)")
            i_oral = st.number_input("Oral / Enteral", min_value=0, step=50, value=0)
            i_par = st.number_input("Parenteral / Medicacion", min_value=0, step=50, value=0)
        with c2:
            st.markdown("#### Egresos (ml)")
            e_orina = st.number_input("Diuresis", min_value=0, step=50, value=0)
            e_dren = st.number_input("Drenajes / Sondas", min_value=0, step=50, value=0)
            e_perd = st.number_input("Perdidas insensibles / Catarsis", min_value=0, step=50, value=0)

        if st.form_submit_button("Guardar balance y calcular shift", use_container_width=True, type="primary"):
            hora_limpia = hora_bal_str.strip() if ":" in hora_bal_str else ahora().strftime("%H:%M")
            fecha_str = f"{fecha_bal.strftime('%d/%m/%Y')} {hora_limpia}"
            ingresos = i_oral + i_par
            egresos = e_orina + e_dren + e_perd
            balance = ingresos - egresos

            st.session_state["balance_db"].append(
                {
                    "paciente": paciente_sel,
                    "turno": turno,
                    "i_oral": i_oral,
                    "i_par": i_par,
                    "e_orina": e_orina,
                    "e_dren": e_dren,
                    "e_perd": e_perd,
                    "ingresos": ingresos,
                    "egresos": egresos,
                    "balance": balance,
                    "fecha": fecha_str,
                    "firma": user["nombre"],
                }
            )
            guardar_datos()
            st.success(f"Balance guardado. Shift actual: {'+' if balance >= 0 else ''}{balance} ml")
            st.rerun()

    blp = [x for x in st.session_state.get("balance_db", []) if x.get("paciente") == paciente_sel]

    if not blp:
        bloque_estado_vacio(
            "Sin balances hidricos",
            "Todavía no hay registros de balance para este paciente.",
            sugerencia="Usá el formulario de arriba: ingresos y egresos en ml, turno y Guardar.",
        )
        return

    st.divider()
    st.markdown("#### Historial de balances hidricos")

    df_temp = pd.DataFrame(blp)
    ultimo = df_temp["balance"].iloc[-1] if not df_temp.empty else 0
    col_met1, col_met2, col_met3 = st.columns(3)
    col_met1.metric(
        "Ultimo shift",
        f"{ultimo:+} ml",
        delta="Retencion (alerta)" if ultimo > 0 else ("Perdida" if ultimo < 0 else "Neutro"),
        delta_color="inverse",
    )
    col_met2.metric("Total balances", len(blp))
    col_met3.metric("Balance neto (ultimos 3 turnos)", f"{sum(df_temp['balance'].tail(3)):+} ml")

    if len(df_temp) >= 2:
        st.markdown("#### Graficos rapidos")
        df_chart = df_temp.copy()
        df_chart["etiqueta"] = df_chart["fecha"]
        col_chart1, col_chart2 = st.columns(2)
        with col_chart1:
            st.caption("Ingresos vs egresos")
            st.bar_chart(
                df_chart.set_index("etiqueta")[["ingresos", "egresos"]].tail(8),
                use_container_width=True,
                color=["#38bdf8", "#f97316"],
            )
        with col_chart2:
            st.caption("Evolucion del shift")
            st.area_chart(
                df_chart.set_index("etiqueta")["balance"].tail(8),
                use_container_width=True,
                color="#22c55e",
            )

    df_bal = pd.DataFrame(blp)
    df_bal["fecha_dt"] = pd.to_datetime(df_bal["fecha"], format="%d/%m/%Y %H:%M", errors="coerce")
    df_bal = df_bal.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"], errors="ignore")
    df_bal["Ingresos"] = df_bal["ingresos"].astype(str) + " ml"
    df_bal["Egresos"] = df_bal["egresos"].astype(str) + " ml"

    def formato_shift(val):
        if val > 0:
            return f"+{val} ml"
        if val < 0:
            return f"{val} ml"
        return "0 ml"

    df_bal["Shift (Resultado)"] = df_bal["balance"].apply(formato_shift)
    df_mostrar = df_bal.rename(columns={"fecha": "Fecha y hora", "turno": "Turno", "firma": "Profesional"})
    limite = seleccionar_limite_registros(
        "Balances a mostrar",
        len(df_mostrar),
        key="balance_limite_historial",
        default=30,
        opciones=(10, 20, 30, 50, 100, 200, 500),
    )

    mostrar_dataframe_con_scroll(
        df_mostrar.head(limite)[["Fecha y hora", "Turno", "Ingresos", "Egresos", "Shift (Resultado)", "Profesional"]],
        height=450,
    )

    st.divider()
    col_chk, col_btn = st.columns([1.2, 2.8])
    confirmar_borrado = col_chk.checkbox("Confirmar", key="conf_del_balance")
    if col_btn.button("Borrar ultimo balance", use_container_width=True, type="secondary", disabled=not confirmar_borrado):
        st.session_state["balance_db"].remove(blp[-1])
        guardar_datos()
        st.success("Ultimo balance eliminado.")
        st.rerun()
