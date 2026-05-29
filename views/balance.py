from __future__ import annotations

from core.app_logging import log_event
from core.alert_toasts import queue_toast
import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core._patient_index import get_patient_records
from features.balance import formato_shift_ml, totales_balance_hidrico_ml
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas, lista_plegable
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros


def render_balance(paciente_sel, user):
    from core.ui_liviano import headers_sugieren_equipo_liviano
    es_movil = headers_sugieren_equipo_liviano() or st.session_state.get("mc_liviano_modo") == "on"
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
        if not es_movil:
            col_meta1, col_meta2, col_meta3 = st.columns(3)
        else:
            col_meta1, col_meta2, col_meta3 = st.container(), st.container(), st.container()
        fecha_bal = col_meta1.date_input("Fecha de control", value=ahora().date(), label_visibility="collapsed", key=f"fecha_bal_{paciente_sel}")
        hora_bal_str = col_meta2.text_input("Hora exacta (HH:MM)", value=ahora().strftime("%H:%M"), label_visibility="collapsed", key=f"hora_bal_{paciente_sel}")
        turno = col_meta3.selectbox("Turno de guardia", ["Manana (06 a 14hs)", "Tarde (14 a 22hs)", "Noche (22 a 06hs)"], label_visibility="collapsed")

        st.divider()
        if not es_movil:
            c1, c2 = st.columns(2)
        else:
            c1, c2 = st.container(), st.container()
        with c1:
            st.markdown("#### Ingresos (ml)")
            i_oral = st.number_input("Oral / Enteral", min_value=0, step=50, value=0)
            i_par = st.number_input("Parenteral / Medicacion", min_value=0, step=50, value=0)
        with c2:
            st.markdown("#### Egresos (ml)")
            e_orina = st.number_input("Diuresis", min_value=0, step=50, value=0)
            e_dren = st.number_input("Drenajes / Sondas", min_value=0, step=50, value=0)
            e_perd = st.number_input("Perdidas insensibles / Catarsis", min_value=0, step=50, value=0)

        if st.form_submit_button("Guardar balance y calcular shift", width='stretch', type="primary"):
            hora_limpia = hora_bal_str.strip() if ":" in hora_bal_str else ahora().strftime("%H:%M")
            fecha_str = f"{fecha_bal.strftime('%d/%m/%Y')} {hora_limpia}"
            ingresos, egresos, balance = totales_balance_hidrico_ml(
                i_oral=i_oral,
                i_par=i_par,
                e_orina=e_orina,
                e_dren=e_dren,
                e_perd=e_perd,
            )

            st.session_state.setdefault("balance_db", [])
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
                    "firma": user.get("nombre", "Sistema"),
                }
            )
            from core.database import _trim_db_list
            _trim_db_list("balance_db", 500)
            if guardar_datos(spinner=True):
                queue_toast(f"Balance guardado. Shift actual: {'+' if balance >= 0 else ''}{balance} ml")
            else:
                log_event("balance", "error_guardar")
                st.error("Error al guardar el balance. Revisá la conexión.")
            st.rerun()

    blp = get_patient_records("balance_db", paciente_sel)

    if not blp:
        bloque_estado_vacio(
            "Sin balances hidricos",
            "Todavía no hay registros de balance para este paciente.",
            sugerencia="Usá el formulario de arriba: ingresos y egresos en ml, turno y Guardar.",
        )
        return

    # ── Resumen del día actual ───────────────────────────────────────────
    hoy_str = ahora().strftime("%d/%m/%Y")
    blp_hoy = [x for x in blp if str(x.get("fecha", "")).startswith(hoy_str)]
    if blp_hoy:
        ing_hoy = sum((x.get("ingresos") or 0) for x in blp_hoy)
        egr_hoy = sum((x.get("egresos") or 0) for x in blp_hoy)
        bal_hoy = sum((x.get("balance") or 0) for x in blp_hoy)
        st.markdown(f"##### Resumen del día — {hoy_str}")
        if not es_movil:
            _d1, _d2 = st.columns(2)
        else:
            _d1, _d2 = st.container(), st.container()
        _d1.metric("Turnos hoy", len(blp_hoy))
        _d1.metric("Ingresos hoy", f"{ing_hoy} ml")
        _d2.metric("Egresos hoy", f"{egr_hoy} ml")
        _d2.metric(
            "Balance hoy",
            f"{bal_hoy:+} ml",
            delta="Retención" if bal_hoy > 500 else ("Pérdida" if bal_hoy < -500 else "Neutro"),
            delta_color="inverse" if bal_hoy > 500 else ("normal" if bal_hoy < -500 else "off"),
        )

    # ── Alertas de balance acumulado crítico ──────────────────────────
    df_temp = pd.DataFrame(blp)
    neto_3 = int(df_temp["balance"].tail(3).sum()) if len(df_temp) >= 1 else 0
    neto_total = int(df_temp["balance"].sum())
    if neto_3 > 1500:
        log_event("balance", f"error: Balance positivo acumulado (retencion): +{neto_3} ml en ultimos 3 turnos.")
        st.error(f"🔴 Balance positivo acumulado (retención): **+{neto_3} ml** en los últimos 3 turnos. Evaluar diurético.")
    elif neto_3 < -1500:
        log_event("balance", f"error: Balance negativo acumulado (perdida severa): {neto_3} ml en ultimos 3 turnos.")
        st.error(f"🔴 Balance negativo acumulado (pérdida severa): **{neto_3} ml** en los últimos 3 turnos. Evaluar reposición.")
    elif neto_3 > 800:
        st.warning(f"🟡 Balance positivo moderado: **+{neto_3} ml** en los últimos 3 turnos.")
    elif neto_3 < -800:
        st.warning(f"🟡 Balance negativo moderado: **{neto_3} ml** en los últimos 3 turnos.")

    # ── Alerta de tendencia consecutiva ─────────────────────────────
    if len(blp) >= 3:
        _ultimos3 = list(df_temp["balance"].tail(3))
        if all(b < 0 for b in _ultimos3):
            log_event("balance", f"error: Tendencia negativa en ultimos 3 turnos ({', '.join(f'{b:+}' for b in _ultimos3)} ml).")
            st.error(f"🔴 Tendencia negativa: los últimos **3 turnos** fueron negativos ({', '.join(f'{b:+}' for b in _ultimos3)} ml). Evaluar reposición hidrosálina.")
        elif all(b > 0 for b in _ultimos3):
            st.warning(f"🟡 Tendencia positiva: los últimos **3 turnos** fueron positivos ({', '.join(f'{b:+}' for b in _ultimos3)} ml). Vigilar retención.")

    st.divider()
    st.markdown("#### Historial de balances hidricos")

    ultimo = df_temp["balance"].iloc[-1] if not df_temp.empty else 0
    penultimo = df_temp["balance"].iloc[-2] if len(df_temp) >= 2 else None
    _delta_shift = int(ultimo) - int(penultimo) if penultimo is not None else None

    if not es_movil:
        col_met1, col_met2 = st.columns(2)
    else:
        col_met1, col_met2 = st.container(), st.container()
    col_met1.metric(
        "Ultimo shift",
        f"{ultimo:+} ml",
        delta=f"{_delta_shift:+} ml vs anterior" if _delta_shift is not None else None,
        delta_color="inverse",
    )
    _ult_ing = int(df_temp["ingresos"].iloc[-1]) if not df_temp.empty else 0
    _ult_egr = int(df_temp["egresos"].iloc[-1]) if not df_temp.empty else 0
    col_met1.metric("Ingresos último turno", f"{_ult_ing} ml")
    col_met2.metric("Egresos último turno", f"{_ult_egr} ml")
    col_met2.metric("Balance neto (ult. 3 turnos)", f"{neto_3:+} ml")

    if len(df_temp) >= 2:
        st.markdown("#### Gráficos")
        df_chart = df_temp.copy()
        df_chart["etiqueta"] = df_chart["fecha"]

        # Gráfico de tendencia diaria agrupada
        try:
            df_chart["fecha_solo"] = pd.to_datetime(df_chart["fecha"], format="%d/%m/%Y %H:%M", errors="coerce").dt.date.astype(str)
            df_diario = df_chart.groupby("fecha_solo", sort=True).agg(
                balance=("balance", "sum"),
                ingresos=("ingresos", "sum"),
                egresos=("egresos", "sum"),
            ).tail(10)
            col_chart0 = st.columns(1)[0]
            col_chart0.caption("Tendencia de balance neto por día (suma de turnos)")
            col_chart0.bar_chart(
                df_diario[["balance"]],
                width='stretch',
                color="#6366f1",
            )
        except Exception as _exc:
            log_event("balance_charts", f"fallo_render_graficos:{type(_exc).__name__}:{_exc}")

        if not es_movil:
            col_chart1, col_chart2 = st.columns(2)
        else:
            col_chart1, col_chart2 = st.container(), st.container()
        with col_chart1:
            st.caption("Ingresos vs egresos (últimos 8 turnos)")
            st.bar_chart(
                df_chart.set_index("etiqueta")[["ingresos", "egresos"]].tail(8),
                width='stretch',
                color=["#38bdf8", "#f97316"],
            )
        with col_chart2:
            st.caption("Evolucion del shift por turno")
            st.area_chart(
                df_chart.set_index("etiqueta")["balance"].tail(8),
                width='stretch',
                color="#22c55e",
            )

    # ── Búsqueda en historial ────────────────────────────────────────────
    _busq_bal = st.text_input(
        "🔍 Buscar en historial",
        placeholder="Turno, profesional o fecha...",
        key="balance_busqueda",
    ).strip().lower()
    blp_filtrado = blp
    if _busq_bal:
        blp_filtrado = [
            b for b in blp
            if _busq_bal in str(b.get("turno", "")).lower()
            or _busq_bal in str(b.get("firma", "")).lower()
            or _busq_bal in str(b.get("fecha", "")).lower()
        ]
        st.caption(f"{len(blp_filtrado)} resultado(s) para '{_busq_bal}'")

    df_bal = pd.DataFrame(blp_filtrado).convert_dtypes()
    for bcol in ["ingresos", "egresos", "balance"]:
        if bcol in df_bal.columns:
            df_bal[bcol] = pd.to_numeric(df_bal[bcol], errors="coerce").fillna(0)
    df_bal["fecha_dt"] = pd.to_datetime(df_bal["fecha"], format="%d/%m/%Y %H:%M", errors="coerce")
    df_bal = df_bal.sort_values(by="fecha_dt", ascending=False).drop(columns=["fecha_dt"], errors="ignore")
    df_bal["ingresos_str"] = df_bal["ingresos"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "0") + " ml"
    df_bal["egresos_str"] = df_bal["egresos"].apply(lambda x: f"{x:.0f}" if pd.notna(x) else "0") + " ml"

    df_bal["Shift (Resultado)"] = df_bal["balance"].apply(formato_shift_ml)
    df_mostrar = df_bal.rename(columns={"fecha": "Fecha y hora", "turno": "Turno", "firma": "Profesional", "ingresos_str": "Ingresos", "egresos_str": "Egresos"})
    df_mostrar = df_mostrar.drop(columns=["ingresos", "egresos", "balance"], errors="ignore")
    limite = seleccionar_limite_registros(
        "Balances a mostrar",
        len(df_mostrar),
        key="balance_limite_historial",
        default=30,
        opciones=(10, 20, 30, 50, 100, 200, 500),
    )

    with lista_plegable("Historial de balances (tabla)", count=min(limite, len(df_mostrar)), expanded=False, height=480):
        mostrar_dataframe_con_scroll(
            df_mostrar.head(limite)[["Fecha y hora", "Turno", "Ingresos", "Egresos", "Shift (Resultado)", "Profesional"]],
            height=430,
        )

    st.divider()
    if not es_movil:
        col_chk, col_btn = st.columns([1.2, 2.8])
    else:
        col_chk, col_btn = st.container(), st.container()
    confirmar_borrado = col_chk.checkbox("Confirmar", key="conf_del_balance")
    if col_btn.button("Borrar ultimo balance", width='stretch', type="secondary", disabled=not confirmar_borrado):
        try:
            st.session_state["balance_db"].remove(blp[-1])
        except ValueError:
            pass  # Intencional: item ya fue removido por otra operación concurrente
        guardar_datos(spinner=True)
        queue_toast("Ultimo balance eliminado.")
        st.rerun()
