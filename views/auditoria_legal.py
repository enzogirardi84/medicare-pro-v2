import pandas as pd
import streamlit as st


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

    st.dataframe(
        df.iloc[::-1],
        use_container_width=True,
        hide_index=True,
    )

    csv_data = df.iloc[::-1].to_csv(index=False, encoding="utf-8-sig")
    st.download_button(
        "Descargar CSV auditoria legal",
        data=csv_data,
        file_name="auditoria_legal.csv",
        mime="text/csv",
        use_container_width=True,
    )
