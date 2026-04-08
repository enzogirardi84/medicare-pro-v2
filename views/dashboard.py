from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from core.utils import (
    ahora,
    calcular_estado_agenda,
    mostrar_dataframe_con_scroll,
    parse_agenda_datetime,
    parse_fecha_hora,
    seleccionar_limite_registros,
)


def _filtrar_empresa(items, mi_empresa, rol):
    if rol == "SuperAdmin":
        return list(items)
    return [x for x in items if x.get("empresa") == mi_empresa]


def _sumar_importe(registros):
    claves = ("monto", "importe", "total", "facturado", "valor")
    total = 0.0
    for item in registros:
        for clave in claves:
            valor = item.get(clave)
            if valor in ("", None):
                continue
            try:
                total += float(str(valor).replace(",", "."))
                break
            except Exception:
                continue
    return round(total, 2)


def render_dashboard(mi_empresa, rol):
    st.markdown(
        f"""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Dashboard ejecutivo</h2>
            <p class="mc-hero-text">Lectura rapida del servicio, agenda, actividad operativa y alertas clinicas para {mi_empresa}.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Pacientes activos</span>
                <span class="mc-chip">Agenda y urgencias</span>
                <span class="mc-chip">Productividad por profesional</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    pacientes = _filtrar_empresa(
        [
            {
                "paciente": p,
                **st.session_state.get("detalles_pacientes_db", {}).get(p, {}),
            }
            for p in st.session_state.get("pacientes_db", [])
        ],
        mi_empresa,
        rol,
    )
    if not pacientes:
        st.warning("No hay pacientes cargados para esta empresa.")
        return

    agenda = _filtrar_empresa(st.session_state.get("agenda_db", []), mi_empresa, rol)
    checkins = _filtrar_empresa(st.session_state.get("checkin_db", []), mi_empresa, rol)
    emergencias = _filtrar_empresa(st.session_state.get("emergencias_db", []), mi_empresa, rol)
    facturacion = _filtrar_empresa(st.session_state.get("facturacion_db", []), mi_empresa, rol)
    balance = _filtrar_empresa(st.session_state.get("balance_db", []), mi_empresa, rol)
    indicaciones = [
        x
        for x in st.session_state.get("indicaciones_db", [])
        if any(x.get("paciente") == paciente["paciente"] for paciente in pacientes)
    ]

    ahora_local = ahora().replace(tzinfo=None)
    hoy = ahora_local.date()
    proximas_48h_limite = ahora_local + timedelta(hours=48)
    hace_30_dias = ahora_local - timedelta(days=30)

    activos = sum(1 for x in pacientes if x.get("estado", "Activo") == "Activo")
    altas = sum(1 for x in pacientes if x.get("estado") == "De Alta")

    agenda_enriquecida = []
    for item in agenda:
        enriched = dict(item)
        enriched["_fecha_dt"] = parse_agenda_datetime(item)
        enriched["estado_calc"] = calcular_estado_agenda(item, now=ahora_local)
        agenda_enriquecida.append(enriched)

    visitas_hoy = [
        x
        for x in checkins
        if "LLEGADA" in str(x.get("tipo", "")).upper()
        and parse_fecha_hora(x.get("fecha_hora", "")).date() == hoy
    ]
    pendientes_hoy = [x for x in agenda_enriquecida if x["_fecha_dt"].date() == hoy and x["estado_calc"] in {"Pendiente", "En curso", "Vencida"}]
    proximas_48 = [x for x in agenda_enriquecida if x["_fecha_dt"] != datetime.min and ahora_local <= x["_fecha_dt"] <= proximas_48h_limite]
    urgencias_30 = [x for x in emergencias if parse_fecha_hora(f"{x.get('fecha_evento', '')} {x.get('hora_evento', '')}") >= hace_30_dias]
    meds_suspendidas = [x for x in indicaciones if str(x.get("estado_receta", "Activa")) in {"Suspendida", "Modificada"}]
    fact_mes = _sumar_importe(facturacion)
    balance_actual = sum(float(x.get("balance", 0) or 0) for x in balance[-30:])

    fila_1 = st.columns(4)
    fila_1[0].metric("Pacientes activos", activos)
    fila_1[1].metric("Pacientes de alta", altas)
    fila_1[2].metric("Visitas hoy", len(visitas_hoy))
    fila_1[3].metric("Pendientes hoy", len(pendientes_hoy))

    fila_2 = st.columns(4)
    fila_2[0].metric("Proximas 48h", len(proximas_48))
    fila_2[1].metric("Urgencias 30 dias", len(urgencias_30))
    fila_2[2].metric("Cambios de medicacion", len(meds_suspendidas))
    fila_2[3].metric("Balance registrado", f"{balance_actual:.0f}")

    if fact_mes:
        st.caption(f"Facturacion cargada en el sistema: ${fact_mes:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))

    st.divider()
    st.markdown("#### Vista operativa")

    if agenda_enriquecida:
        agenda_estado = (
            pd.DataFrame(agenda_enriquecida)
            .groupby("estado_calc")
            .size()
            .reset_index(name="Cantidad")
            .rename(columns={"estado_calc": "Estado"})
        )
    else:
        agenda_estado = pd.DataFrame(columns=["Estado", "Cantidad"])

    if visitas_hoy:
        df_visitas_hoy = pd.DataFrame(visitas_hoy)
        df_visitas_hoy["fecha_dt"] = df_visitas_hoy["fecha_hora"].apply(parse_fecha_hora)
        visitas_prof = (
            df_visitas_hoy.groupby("profesional")
            .size()
            .reset_index(name="Visitas")
            .rename(columns={"profesional": "Profesional"})
            .sort_values("Visitas", ascending=False)
        )
    else:
        visitas_prof = pd.DataFrame(columns=["Profesional", "Visitas"])

    if urgencias_30:
        df_urg = pd.DataFrame(urgencias_30)
        urg_chart = (
            df_urg.groupby("triage_grado")
            .size()
            .reset_index(name="Eventos")
            .rename(columns={"triage_grado": "Triage"})
        )
    else:
        urg_chart = pd.DataFrame(columns=["Triage", "Eventos"])

    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.caption("Agenda por estado")
        if not agenda_estado.empty:
            st.bar_chart(agenda_estado.set_index("Estado")["Cantidad"], use_container_width=True)
        else:
            st.info("Todavia no hay agenda cargada.")
    with col_g2:
        st.caption("Visitas del dia por profesional")
        if not visitas_prof.empty:
            st.bar_chart(visitas_prof.set_index("Profesional")["Visitas"], use_container_width=True)
        else:
            st.info("Todavia no hay visitas registradas hoy.")

    if not urg_chart.empty:
        st.caption("Urgencias por triage (ultimos 30 dias)")
        st.bar_chart(urg_chart.set_index("Triage")["Eventos"], use_container_width=True)

    st.divider()
    st.markdown("#### Listados ejecutivos")

    col_l1, col_l2 = st.columns(2)
    with col_l1:
        st.caption("Agenda prioritaria")
        if agenda_enriquecida:
            df_ag = pd.DataFrame(agenda_enriquecida)
            df_ag["Fecha y Hora"] = df_ag["_fecha_dt"].apply(lambda x: x.strftime("%d/%m/%Y %H:%M") if x != datetime.min else "Sin fecha")
            df_ag = df_ag.rename(columns={"paciente": "Paciente", "profesional": "Profesional", "estado_calc": "Estado"})
            df_ag = df_ag[["Fecha y Hora", "Paciente", "Profesional", "Estado"]].sort_values("Fecha y Hora")
            limite_ag = seleccionar_limite_registros(
                "Agenda a mostrar",
                len(df_ag),
                key=f"dash_agenda_limit_{mi_empresa}_{rol}",
                default=12,
                opciones=(6, 12, 20, 30, 50),
            )
            mostrar_dataframe_con_scroll(df_ag.head(limite_ag), height=340)
        else:
            st.info("No hay agenda disponible.")

    with col_l2:
        st.caption("Cambios recientes de medicacion")
        if meds_suspendidas:
            df_med = pd.DataFrame(meds_suspendidas)
            estado_base = df_med["estado_receta"] if "estado_receta" in df_med.columns else pd.Series(["Activa"] * len(df_med))
            df_med["Estado"] = estado_base.fillna("Activa")

            profesional_estado = (
                df_med["profesional_estado"]
                if "profesional_estado" in df_med.columns
                else pd.Series([""] * len(df_med))
            )
            medico_nombre = (
                df_med["medico_nombre"]
                if "medico_nombre" in df_med.columns
                else pd.Series([""] * len(df_med))
            )
            df_med["Profesional"] = profesional_estado.fillna("").replace("", pd.NA).fillna(medico_nombre.fillna("")).replace("", "Sin profesional")

            df_med = df_med.rename(columns={"fecha_estado": "Fecha", "med": "Indicacion"})
            if "Fecha" not in df_med.columns:
                df_med["Fecha"] = df_med.get("fecha", "S/D")
            if "Indicacion" not in df_med.columns:
                df_med["Indicacion"] = df_med.get("med", "Sin detalle")
            df_med = df_med[["Fecha", "Indicacion", "Estado", "Profesional"]].sort_values("Fecha", ascending=False)
            limite_med = seleccionar_limite_registros(
                "Cambios a mostrar",
                len(df_med),
                key=f"dash_med_limit_{mi_empresa}_{rol}",
                default=10,
                opciones=(5, 10, 20, 30),
            )
            mostrar_dataframe_con_scroll(df_med.head(limite_med), height=340)
        else:
            st.success("No hay suspensiones o modificaciones de medicacion registradas.")
