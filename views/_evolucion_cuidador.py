"""Panel de evolucion asistida basado en Patrones Funcionales de Marjory Gordon."""

import streamlit as st
from core.utils import ahora, registrar_auditoria_legal
from core.database import guardar_datos
from core.alert_toasts import queue_toast


def _generar_texto_evolucion(
    ta_sistolica, ta_diastolica, fc, temperatura,
    higiene, movilidad,
    animo, dolor_presente, dolor_eva,
    alimentacion, curaciones,
    diuresis, deposicion,
    descanso,
    medicacion_administrada,
    observaciones_extra,
) -> str:
    parrafos = []

    # Signos vitales
    sv_partes = []
    if ta_sistolica and ta_diastolica:
        sv_partes.append(f"TA {ta_sistolica}/{ta_diastolica} mmHg")
    if fc:
        sv_partes.append(f"FC {fc} lpm")
    if temperatura:
        sv_partes.append(f"Temp {temperatura} C")
    if sv_partes:
        parrafos.append("Signos vitales: " + ", ".join(sv_partes) + ".")

    # Estado neurologico
    mapa_animo = {
        "Despierto y tranquilo": "Paciente vigil y tranquilo",
        "Somnoliento": "Paciente somnoliento pero reagible al llamado",
        "Apatico": "Paciente apatico, con poca respuesta a estimulos",
        "Irritable": "Paciente irritable durante la evaluacion",
        "Desorientado": "Paciente desorientado en tiempo y espacio",
    }
    if animo in mapa_animo:
        parrafos.append(mapa_animo[animo] + ".")

    # Dolor
    if dolor_presente and dolor_eva:
        parrafos.append(f"Refiere dolor, escala EVA {int(dolor_eva)}/10.")
    elif dolor_presente:
        parrafos.append("Refiere dolor al momento de la evaluacion.")
    else:
        parrafos.append("Sin signos de dolor al momento de la evaluacion.")

    # Alimentacion
    mapa_alimentacion = {
        "Comio toda su porcion": "Tolera dieta por via oral sin complicaciones, ingiere la totalidad de la porcion",
        "Comio poco": "Ingesta oral reducida, tolera parcialmente la dieta",
        "No quiso comer": "Rechaza la alimentacion por via oral",
        "Alimentacion por sonda": "Recibe alimentacion por sonda nasogastrica o gastrostomia sin incidentes",
    }
    if alimentacion in mapa_alimentacion:
        parrafos.append(mapa_alimentacion[alimentacion] + ".")

    # Curaciones
    if curaciones:
        parrafos.append("Se realizan curaciones planas segun indicacion, sin signos de infeccion.")

    # Higiene
    mapa_higiene = {
        "Se bano solo": "Higiene personal realizada de forma autonoma",
        "Bano en cama": "Se realizo higiene en cama con asistencia del personal",
        "Cambio de panial": "Se realizo cambio de panial, piel integra sin lesiones",
    }
    if higiene in mapa_higiene:
        parrafos.append(mapa_higiene[higiene] + ".")

    # Movilidad
    mapa_movilidad = {
        "Reposo en cama": "Paciente en reposo absoluto en cama",
        "Camino con ayuda": "Deambula con asistencia de una persona o andador",
        "Camino solo": "Deambula de forma autonoma sin dificultad",
    }
    if movilidad in mapa_movilidad:
        parrafos.append(mapa_movilidad[movilidad] + ".")

    # Diuresis
    mapa_diuresis = {
        "Orino bien": "Diuresis conservada, orina espontanea sin alteraciones",
        "No orino": "No registra diuresis en el turno",
        "Tiene sonda": "Porta sonda vesical, diuresis conservada",
    }
    if diuresis in mapa_diuresis:
        parrafos.append(mapa_diuresis[diuresis] + ".")

    # Deposicion
    if deposicion:
        parrafos.append("Deposicion presente, caracteristicas dentro de parametros.")
    else:
        parrafos.append("No registra deposicion en el turno.")

    # Descanso
    mapa_descanso = {
        "Durmio bien toda la noche": "Descanso nocturno conservado",
        "Le costo dormir": "Descanso nocturno fragmentado, con dificultad para conciliar el sueno",
        "Estuvo inquieto": "Descanso nocturno interrumpido por inquietud o malestar",
    }
    if descanso in mapa_descanso:
        parrafos.append(mapa_descanso[descanso] + ".")

    # Medicacion
    if medicacion_administrada:
        parrafos.append("Se administra medicacion segun indicacion correspondiente al horario, sin eventualidades.")

    # Observaciones
    if observaciones_extra and observaciones_extra.strip():
        parrafos.append(f"Observaciones: {observaciones_extra.strip()}.")

    final = " ".join(parrafos)
    final = final.strip()

    if not final:
        return "Sin registros en este turno."

    if not final.endswith("."):
        final += "."

    return final


def _render_panel_cuidador(paciente_sel, user, puede_registrar):
    st.markdown("##### Registro inteligente de evolucion")
    st.caption("Completá el estado del paciente por patrones. Al guardar se genera un texto profesional automaticamente.")

    if not puede_registrar:
        st.caption("La carga de evoluciones queda deshabilitada para este rol.")
        return

    with st.form("evol_cuidador", clear_on_submit=False):
        p1, p2, p3 = st.columns(3)
        p4, p5, p6 = st.columns(3)

        with p1:
            st.markdown("**Actividad y Ejercicio**")
            ta_sistolica = st.number_input("TA sist (mmHg)", min_value=0, max_value=300, value=120, step=1, key="evc_ta_sis")
            ta_diastolica = st.number_input("TA dias (mmHg)", min_value=0, max_value=200, value=80, step=1, key="evc_ta_dias")
            fc = st.number_input("FC (lpm)", min_value=0, max_value=300, value=80, step=1, key="evc_fc")
            temperatura = st.number_input("Temp (C)", min_value=34.0, max_value=42.0, value=36.5, step=0.1, key="evc_temp")
            st.markdown("")
            higiene = st.selectbox("Higiene", ["", "Se bano solo", "Bano en cama", "Cambio de panial"], key="evc_higiene")
            movilidad = st.selectbox("Movilidad", ["", "Reposo en cama", "Camino con ayuda", "Camino solo"], key="evc_movilidad")

        with p2:
            st.markdown("**Cognitivo - Perceptivo**")
            animo = st.selectbox(
                "Estado neurologico / Animo",
                ["", "Despierto y tranquilo", "Somnoliento", "Apatico", "Irritable", "Desorientado"],
                key="evc_animo",
            )
            dolor_presente = st.checkbox("Refiere dolor", key="evc_dolor_check")
            dolor_eva = 0
            if dolor_presente:
                dolor_eva = st.slider("Escala EVA (1-10)", min_value=1, max_value=10, value=5, key="evc_dolor_eva")
            st.markdown("")
            st.markdown("**Nutricional - Metabolico**")
            alimentacion = st.selectbox(
                "Alimentacion",
                ["", "Comio toda su porcion", "Comio poco", "No quiso comer", "Alimentacion por sonda"],
                key="evc_alimentacion",
            )
            curaciones = st.checkbox("Se realizaron curaciones planas", key="evc_curaciones")

        with p3:
            st.markdown("**Eliminacion**")
            diuresis = st.selectbox("Diuresis (Orina)", ["", "Orino bien", "No orino", "Tiene sonda"], key="evc_diuresis")
            deposicion = st.checkbox("Hizo deposicion", key="evc_deposicion")
            st.markdown("")
            st.markdown("**Sueno - Descanso**")
            descanso = st.selectbox(
                "Descanso",
                ["", "Durmio bien toda la noche", "Le costo dormir", "Estuvo inquieto"],
                key="evc_descanso",
            )

        st.divider()
        st.markdown("**Medicacion**")
        medicacion_administrada = st.checkbox(
            "Se administro la medicacion correspondiente al turno",
            value=False,
            key="evc_med_check",
        )
        if medicacion_administrada:
            st.caption("Queda registrado en la evolucion que la medicacion fue administrada segun indicacion.")

        st.divider()
        observaciones_extra = st.text_area(
            "Observaciones (opcional)",
            placeholder="Si paso algo fuera de lo comun, describilo aca con tus palabras.",
            height=80,
            key="evc_obs",
        )

        st.divider()
        preview_btn = st.form_submit_button("Previsualizar texto profesional", width='stretch', type="secondary")
        guardar_btn = st.form_submit_button("Guardar evolucion", width='stretch', type="primary")

    if preview_btn or guardar_btn:
        texto_generado = _generar_texto_evolucion(
            ta_sistolica=ta_sistolica,
            ta_diastolica=ta_diastolica,
            fc=fc,
            temperatura=temperatura,
            higiene=higiene,
            movilidad=movilidad,
            animo=animo,
            dolor_presente=dolor_presente,
            dolor_eva=dolor_eva,
            alimentacion=alimentacion,
            curaciones=curaciones,
            diuresis=diuresis,
            deposicion=deposicion,
            descanso=descanso,
            medicacion_administrada=medicacion_administrada,
            observaciones_extra=observaciones_extra,
        )

        if preview_btn:
            st.markdown("### Vista previa del texto profesional")
            st.text_area(
                "Texto generado",
                value=texto_generado,
                height=200,
                disabled=True,
                label_visibility="collapsed",
            )

        if guardar_btn:
            if not any([ta_sistolica, ta_diastolica, fc, temperatura,
                        higiene, movilidad, animo,
                        dolor_presente, dolor_eva,
                        alimentacion, curaciones,
                        diuresis, deposicion, descanso,
                        medicacion_administrada]) and not observaciones_extra.strip():
                st.error("Debe completar al menos un campo antes de guardar.")
            else:
                fecha_n = ahora().strftime("%d/%m/%Y %H:%M")
                if "evoluciones_db" not in st.session_state or not isinstance(st.session_state["evoluciones_db"], list):
                    st.session_state["evoluciones_db"] = []

                st.session_state["evoluciones_db"].append({
                    "paciente": paciente_sel,
                    "nota": texto_generado,
                    "fecha": fecha_n,
                    "firma": user.get("nombre", "Sistema"),
                    "plantilla": "Registro inteligente",
                    "tipo_evolucion": "cuidador",
                    "cuidador_data": {
                        "ta_sistolica": ta_sistolica,
                        "ta_diastolica": ta_diastolica,
                        "fc": fc,
                        "temperatura": temperatura,
                        "higiene": higiene,
                        "movilidad": movilidad,
                        "animo": animo,
                        "dolor_presente": dolor_presente,
                        "dolor_eva": dolor_eva,
                        "alimentacion": alimentacion,
                        "curaciones": curaciones,
                        "diuresis": diuresis,
                        "deposicion": deposicion,
                        "descanso": descanso,
                        "medicacion_administrada": medicacion_administrada,
                        "observaciones_extra": observaciones_extra.strip(),
                    },
                })
                from core.database import _trim_db_list
                _trim_db_list("evoluciones_db", 500)

                registrar_auditoria_legal(
                    "Evolucion Clinica",
                    paciente_sel,
                    "Nueva evolucion inteligente",
                    user.get("nombre", ""),
                    user.get("matricula", ""),
                    "Se registro evolucion mediante panel inteligente.",
                )
                guardar_datos(spinner=True)

                try:
                    from core.nextgen_sync import sync_visita_evolucion_to_nextgen
                    sync_visita_evolucion_to_nextgen(paciente_sel, texto_generado[:500])
                except Exception:
                    from core.app_logging import log_event
                    log_event("evolucion_cuidador", "nextgen_sync_skip")

                queue_toast("Evolucion guardada correctamente.")
                st.rerun()
