import streamlit as st
import pandas as pd
from datetime import timedelta
from core.utils import ahora


def render_dashboard(mi_empresa, rol):
    st.markdown(f"<h3 style='color: #3b82f6;'>Panel de Gestion - {mi_empresa}</h3>", unsafe_allow_html=True)

    if not st.session_state["pacientes_db"]:
        st.warning("No hay pacientes cargados.")
        return

    checkins = st.session_state.get("checkin_db", [])
    if not checkins:
        st.info("El sistema esta listo para empezar a registrar visitas.")
        return

    llegadas = [c for c in checkins if "LLEGADA" in str(c.get("tipo", ""))]
    if rol == "Coordinador":
        llegadas = [c for c in llegadas if c.get("empresa") == mi_empresa]

    if not llegadas:
        st.info("Aun no se han registrado ingresos GPS en los domicilios.")
        return

    hace_una_semana = (ahora() - timedelta(days=7)).replace(tzinfo=None)
    visitas_recientes = []
    for item in llegadas:
        fecha_raw = item.get("fecha_hora", "")
        try:
            fecha_dt = pd.to_datetime(fecha_raw, format="%d/%m/%Y %H:%M:%S", errors="coerce")
            if pd.isna(fecha_dt):
                fecha_dt = pd.to_datetime(fecha_raw, format="%d/%m/%Y %H:%M", errors="coerce")
        except Exception:
            fecha_dt = pd.NaT

        if pd.notna(fecha_dt) and fecha_dt > hace_una_semana:
            visitas_recientes.append({
                "profesional": item.get("profesional", "Sin nombre"),
                "paciente": item.get("paciente", "Sin paciente"),
                "fecha_hora": fecha_raw,
            })

    if not visitas_recientes:
        st.info("No hay fichadas GPS en los ultimos 7 dias.")
        return

    df_visitas = pd.DataFrame(visitas_recientes)
    resumen = df_visitas["profesional"].value_counts().reset_index()
    resumen.columns = ["Profesional", "Visitas"]
    resumen = resumen.sort_values("Visitas", ascending=False).reset_index(drop=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Fichadas GPS (7 dias)", len(df_visitas))
    col2.metric("Profesionales activos", resumen["Profesional"].nunique())
    col3.metric("Promedio por profesional", round(len(df_visitas) / max(len(resumen), 1), 1))

    max_top = min(20, max(len(resumen), 1))
    if max_top <= 5:
        top_n = max_top
        st.caption(f"Mostrando {top_n} profesionales.")
    else:
        top_n = st.slider("Profesionales a mostrar", min_value=5, max_value=max_top, value=min(10, len(resumen)))
    st.dataframe(resumen.head(top_n), use_container_width=True, hide_index=True)

    if st.checkbox("Mostrar detalle de fichadas recientes", value=False):
        max_detalle = min(300, max(len(df_visitas), 1))
        if max_detalle <= 20:
            limite = max_detalle
            st.caption(f"Mostrando {limite} fichadas recientes.")
        else:
            limite = st.slider("Cantidad de fichadas recientes", min_value=20, max_value=max_detalle, value=min(80, len(df_visitas)))
        with st.container(height=460):
            st.dataframe(df_visitas.tail(limite).iloc[::-1], use_container_width=True, hide_index=True)
