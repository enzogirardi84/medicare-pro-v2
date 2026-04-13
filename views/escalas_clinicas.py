import pandas as pd
import streamlit as st

from core.database import guardar_datos
from core.view_helpers import aviso_sin_paciente, bloque_mc_grid_tarjetas
from core.utils import ahora, mostrar_dataframe_con_scroll, registrar_auditoria_legal, seleccionar_limite_registros


def _glasgow(ocular, verbal, motora):
    return ocular + verbal + motora


def _braden(sensorial, humedad, actividad, movilidad, nutricion, friccion):
    return sensorial + humedad + actividad + movilidad + nutricion + friccion


def _interpretacion_visual(escala, puntaje, resumen):
    base = {
        "titulo": resumen,
        "detalle": "Lectura automatica del puntaje para apoyar la decision clinica.",
        "color": "#38bdf8",
        "fondo": "rgba(56, 189, 248, 0.12)",
    }
    recomendaciones = {
        "Glasgow": {
            "Compromiso severo": ("#ef4444", "Monitoreo intensivo y aviso medico inmediato."),
            "Compromiso moderado": ("#f59e0b", "Revalorar neurologia y seguimiento estrecho."),
            "Leve / normal": ("#22c55e", "Continuar control evolutivo segun cuadro clinico."),
        },
        "Braden": {
            "Alto riesgo UPP": ("#ef4444", "Rotacion, alivio de presion y vigilancia de piel."),
            "Riesgo moderado": ("#f59e0b", "Implementar medidas preventivas y control diario."),
            "Bajo riesgo": ("#22c55e", "Mantener prevencion basica y reevaluacion periodica."),
        },
        "Barthel": {
            "Dependencia total": ("#ef4444", "Requiere apoyo integral y plan intensivo de cuidados."),
            "Dependencia severa": ("#f59e0b", "Priorizar asistencia funcional y seguimiento familiar."),
            "Dependencia leve/moderada": ("#38bdf8", "Promover autonomia supervisada y reevaluacion."),
            "Independiente": ("#22c55e", "Mantener control periodico y objetivos de sostén."),
        },
        "EVA": {
            "Sin dolor": ("#22c55e", "Sin analgesia adicional inmediata."),
            "Dolor leve": ("#38bdf8", "Continuar seguimiento del dolor y respuesta clinica."),
            "Dolor moderado": ("#f59e0b", "Revisar analgesia indicada y reevaluar pronto."),
            "Dolor severo": ("#ef4444", "Escalar manejo del dolor y notificar conducta medica."),
        },
    }
    color, detalle = recomendaciones.get(escala, {}).get(resumen, (base["color"], base["detalle"]))
    base["color"] = color
    base["detalle"] = detalle
    base["fondo"] = {
        "#ef4444": "rgba(239, 68, 68, 0.14)",
        "#f59e0b": "rgba(245, 158, 11, 0.16)",
        "#22c55e": "rgba(34, 197, 94, 0.14)",
    }.get(color, "rgba(56, 189, 248, 0.12)")
    return base


def render_escalas_clinicas(paciente_sel, user):
    if not paciente_sel:
        aviso_sin_paciente()
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
    bloque_mc_grid_tarjetas(
        [
            ("Glasgow / Braden", "Neurologia y riesgo de UPP con lectura automatica."),
            ("Barthel / EVA", "Dependencia funcional y escala de dolor."),
            ("Historial", "Cada registro queda vinculado al paciente."),
        ]
    )
    st.caption(
        "Elegi la escala en el selector; el bloque de abajo cambia los campos. Al guardar, el puntaje y la lectura sugerida quedan en el historial del paciente."
    )

    escala = st.radio("Escala", ["Glasgow", "Braden", "Barthel", "EVA"], horizontal=False)

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
        card = _interpretacion_visual(escala, puntaje, resumen)
        st.markdown(
            f"""
            <div style="border:1px solid {card['color']}; background:{card['fondo']}; border-radius:18px; padding:16px 18px; margin:8px 0 12px 0;">
                <div style="font-size:0.82rem; letter-spacing:0.08em; text-transform:uppercase; color:{card['color']}; font-weight:700;">Interpretacion automatica</div>
                <div style="font-size:1.15rem; font-weight:700; color:#f8fafc; margin-top:4px;">{card['titulo']}</div>
                <div style="font-size:0.98rem; color:#cbd5e1; margin-top:6px;">{card['detalle']}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

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

    limite = seleccionar_limite_registros(
        "Escalas a mostrar",
        len(registros),
        key=f"limite_escalas_{paciente_sel}",
        default=30,
    )
    mostrar_dataframe_con_scroll(
        pd.DataFrame(registros[-limite:]).drop(columns=["paciente"], errors="ignore").iloc[::-1],
        height=420,
    )
