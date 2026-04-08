import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.utils import ahora, registrar_auditoria_legal


def _glasgow(ocular, verbal, motora):
    return ocular + verbal + motora


def _braden(sensorial, humedad, actividad, movilidad, nutricion, friccion):
    return sensorial + humedad + actividad + movilidad + nutricion + friccion


def render_escalas_clinicas(paciente_sel, user):
    if not paciente_sel:
        st.info("Selecciona un paciente para registrar escalas clinicas.")
        return

    registros = [x for x in st.session_state.get("escalas_clinicas_db", []) if x.get("paciente") == paciente_sel]

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Escalas clinicas</h2>
            <p class="mc-hero-text">Registra puntajes estructurados para neurologia, riesgo de ulceras, dependencia y dolor con lectura rapida del estado del paciente.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Glasgow</span>
                <span class="mc-chip">Braden</span>
                <span class="mc-chip">Barthel</span>
                <span class="mc-chip">EVA</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    escala = st.radio("Escala", ["Glasgow", "Braden", "Barthel", "EVA"], horizontal=True)

    with st.container(border=True):
        st.markdown(f"### Registro de {escala}")
        resumen = ""
        puntaje = 0

        if escala == "Glasgow":
            c1, c2, c3 = st.columns(3)
            ocular = c1.selectbox("Respuesta ocular", [1, 2, 3, 4], index=3)
            verbal = c2.selectbox("Respuesta verbal", [1, 2, 3, 4, 5], index=4)
            motora = c3.selectbox("Respuesta motora", [1, 2, 3, 4, 5, 6], index=5)
            puntaje = _glasgow(ocular, verbal, motora)
            resumen = "Compromiso severo" if puntaje <= 8 else "Compromiso moderado" if puntaje <= 12 else "Leve / normal"
            st.metric("Puntaje Glasgow", puntaje)
        elif escala == "Braden":
            c1, c2, c3 = st.columns(3)
            sensorial = c1.selectbox("Percepcion sensorial", [1, 2, 3, 4], index=3)
            humedad = c2.selectbox("Humedad", [1, 2, 3, 4], index=3)
            actividad = c3.selectbox("Actividad", [1, 2, 3, 4], index=3)
            c4, c5, c6 = st.columns(3)
            movilidad = c4.selectbox("Movilidad", [1, 2, 3, 4], index=3)
            nutricion = c5.selectbox("Nutricion", [1, 2, 3, 4], index=3)
            friccion = c6.selectbox("Friccion / roce", [1, 2, 3], index=2)
            puntaje = _braden(sensorial, humedad, actividad, movilidad, nutricion, friccion)
            resumen = "Alto riesgo UPP" if puntaje <= 12 else "Riesgo moderado" if puntaje <= 16 else "Bajo riesgo"
            st.metric("Puntaje Braden", puntaje)
        elif escala == "Barthel":
            puntaje = st.slider("Indice de Barthel", min_value=0, max_value=100, value=60, step=5)
            resumen = "Dependencia total" if puntaje <= 20 else "Dependencia severa" if puntaje <= 60 else "Dependencia leve/moderada" if puntaje < 100 else "Independiente"
            st.metric("Puntaje Barthel", puntaje)
        else:
            puntaje = st.slider("Escala visual analogica del dolor", min_value=0, max_value=10, value=0, step=1)
            resumen = "Sin dolor" if puntaje == 0 else "Dolor leve" if puntaje <= 3 else "Dolor moderado" if puntaje <= 6 else "Dolor severo"
            st.metric("Puntaje EVA", puntaje)

        observaciones = st.text_area("Observaciones", height=90)
        st.info(f"Interpretacion: {resumen}")

        if st.button(f"Guardar {escala}", use_container_width=True, type="primary"):
            nuevo = {
                "paciente": paciente_sel,
                "fecha": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                "escala": escala,
                "puntaje": puntaje,
                "interpretacion": resumen,
                "observaciones": observaciones.strip(),
                "profesional": user.get("nombre", ""),
                "matricula": user.get("matricula", ""),
            }
            st.session_state["escalas_clinicas_db"].append(nuevo)
            registrar_auditoria_legal(
                "Escala Clinica",
                paciente_sel,
                f"Registro {escala}",
                user.get("nombre", ""),
                user.get("matricula", ""),
                f"Puntaje: {puntaje} | {resumen}",
            )
            guardar_datos()
            st.success(f"Escala {escala} guardada.")
            st.rerun()

    st.divider()
    st.markdown("### Historial de escalas")
    if not registros:
        st.info("Todavia no hay escalas registradas para este paciente.")
        return

    st.dataframe(
        pd.DataFrame(registros[-200:]).drop(columns=["paciente"], errors="ignore").iloc[::-1],
        use_container_width=True,
        hide_index=True,
    )
