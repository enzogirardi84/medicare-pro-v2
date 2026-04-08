import pandas as pd
import streamlit as st

from core.export_utils import dataframe_csv_bytes, sanitize_filename_component
from core.utils import mostrar_dataframe_con_scroll, seleccionar_limite_registros


def render_auditoria_legal(mi_empresa, user):
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Auditoria legal central</h2>
            <p class="mc-hero-text">Concentra eventos clinicos y documentales con valor legal: medicacion, consentimientos, emergencias, escalas y cuidados.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Trazabilidad</span>
                <span class="mc-chip">Actor y matricula</span>
                <span class="mc-chip">Paciente</span>
                <span class="mc-chip">Fecha y hora</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    df = pd.DataFrame(st.session_state.get("auditoria_legal_db", []))
    if df.empty:
        st.info("Todavia no hay eventos legales registrados.")
        return

    filtro = st.text_input("Buscar por paciente, accion, actor o detalle")
    if filtro:
        mask = df.astype(str).apply(lambda x: x.str.contains(filtro, case=False, na=False)).any(axis=1)
        df = df[mask]

    if "paciente" in df.columns:
        pacientes = ["Todos"] + sorted(df["paciente"].dropna().unique().tolist())
        paciente_sel = st.selectbox("Paciente", pacientes)
        if paciente_sel != "Todos":
            df = df[df["paciente"] == paciente_sel]

    limite = seleccionar_limite_registros(
        "Eventos a mostrar",
        len(df),
        key=f"auditoria_legal_{mi_empresa}_{user.get('nombre', '')}",
        default=50,
    )
    mostrar_dataframe_con_scroll(df.tail(limite).iloc[::-1], height=460)

    csv_data = dataframe_csv_bytes(df.iloc[::-1])
    st.download_button(
        "Descargar CSV auditoria legal",
        data=csv_data,
        file_name=f"auditoria_legal_{sanitize_filename_component(mi_empresa, 'empresa')}.csv",
        mime="text/csv",
        use_container_width=True,
    )
