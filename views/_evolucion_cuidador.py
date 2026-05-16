"""Panel de evolucion para cuidadores. Convierte selecciones simples en texto profesional."""

import streamlit as st
from core.utils import ahora, registrar_auditoria_legal
from core.database import guardar_datos
from core.alert_toasts import queue_toast


def _generar_texto_evolucion_cuidador(
    ta_sistolica, ta_diastolica, fc, temperatura,
    animo, alimentacion, higiene, eliminacion,
    medicacion_administrada,
    observaciones_extra,
) -> str:
    partes = []

    if ta_sistolica and ta_diastolica:
        partes.append(f"Tension arterial {ta_sistolica}/{ta_diastolica} mmHg")
    if fc:
        partes.append(f"frecuencia cardiaca {fc} lpm")
    if temperatura:
        partes.append(f"temperatura {temperatura} °C")

    sv_text = ""
    if partes:
        sv_text = "Signos vitales: " + ", ".join(partes) + ". "

    estado_partes = []

    mapa_animo = {
        "Despierto": "Paciente despierto y consciente",
        "Somnoliento": "Paciente somnoliento pero reagible al llamado",
        "Tranquilo": "Paciente tranquilo y colaborador",
        "Irritable": "Paciente irritable durante la evaluacion",
    }
    if animo in mapa_animo:
        estado_partes.append(mapa_animo[animo])

    mapa_alimentacion = {
        "Comio todo": "Tolera dieta por via oral sin complicaciones",
        "Comio poco": "Ingesta oral reducida, tolera parcialmente la dieta",
        "No quiso comer": "Rechaza la alimentacion por via oral",
        "Alimentacion por sonda": "Recibe alimentacion por sonda nasogastrica/gastrostomia sin incidentes",
    }
    if alimentacion in mapa_alimentacion:
        estado_partes.append(mapa_alimentacion[alimentacion])

    mapa_higiene = {
        "Se bano solo": "Higiene personal realizada de forma autonoma",
        "Bano en cama": "Se realizo higiene en cama con asistencia del personal",
        "Cambio de panial": "Se realizo cambio de panial, piel integra sin lesiones",
    }
    if higiene in mapa_higiene:
        estado_partes.append(mapa_higiene[higiene])

    mapa_eliminacion = {
        "Orino bien": "Diuresis conservada, orina espontanea sin alteraciones",
        "No orino": "No registra diuresis en el turno",
        "Hizo deposicion": "Deposicion presente, caracteristicas dentro de parametros",
        "No hizo deposicion": "No registra deposicion en el turno",
    }
    if eliminacion in mapa_eliminacion:
        estado_partes.append(mapa_eliminacion[eliminacion])

    estado_text = ". ".join(estado_partes)
    if estado_text:
        estado_text += ". "

    med_text = ""
    if medicacion_administrada:
        med_text = "Se administra medicacion segun indicacion correspondiente al horario, sin eventualidades. "

    obs_text = ""
    if observaciones_extra and observaciones_extra.strip():
        obs_text = f"Observaciones: {observaciones_extra.strip()}. "

    final = sv_text + estado_text + med_text + obs_text
    final = final.strip()

    if not final:
        return "Sin registros en este turno."

    if not final.endswith("."):
        final += "."

    return final


def _render_panel_cuidador(paciente_sel, user, puede_registrar):
    st.markdown("##### Registro de evolucion para cuidadores")
    st.caption("Completá el estado del paciente de forma sencilla. Al guardar se genera un texto profesional.")

    if not puede_registrar:
        st.caption("La carga de evoluciones queda deshabilitada para este rol.")
        return

    with st.form("evol_cuidador", clear_on_submit=False):
        st.markdown("**Signos vitales**")
        sv_cols = st.columns(4)
        ta_sistolica = sv_cols[0].number_input("TA sistolica (mmHg)", min_value=0, max_value=300, value=120, step=1, key="evc_ta_sis")
        ta_diastolica = sv_cols[0].number_input("TA diastolica (mmHg)", min_value=0, max_value=200, value=80, step=1, key="evc_ta_dias")
        fc = sv_cols[1].number_input("Frec. cardiaca (lpm)", min_value=0, max_value=300, value=80, step=1, key="evc_fc")
        temperatura = sv_cols[2].number_input("Temperatura (°C)", min_value=34.0, max_value=42.0, value=36.5, step=0.1, key="evc_temp")
        sv_cols[3].markdown("")  # spacer

        st.divider()
        st.markdown("**Estado general**")

        c_est1, c_est2 = st.columns(2)
        animo = c_est1.selectbox("Animo / Neurologico", ["", "Despierto", "Somnoliento", "Tranquilo", "Irritable"], key="evc_animo")
        alimentacion = c_est2.selectbox("Alimentacion", ["", "Comio todo", "Comio poco", "No quiso comer", "Alimentacion por sonda"], key="evc_alimentacion")

        c_est3, c_est4 = st.columns(2)
        higiene = c_est3.selectbox("Higiene", ["", "Se bano solo", "Bano en cama", "Cambio de panial"], key="evc_higiene")
        eliminacion = c_est4.selectbox("Eliminacion", ["", "Orino bien", "No orino", "Hizo deposicion", "No hizo deposicion"], key="evc_eliminacion")

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
            "Observaciones extra (opcional)",
            placeholder="Si paso algo fuera de lo comun, describilo aca con tus palabras.",
            height=100,
            key="evc_obs",
        )

        st.divider()
        preview_btn = st.form_submit_button("Previsualizar texto profesional", width='stretch', type="secondary")
        guardar_btn = st.form_submit_button("Guardar evolucion", width='stretch', type="primary")

    if preview_btn or guardar_btn:
        texto_generado = _generar_texto_evolucion_cuidador(
            ta_sistolica=ta_sistolica,
            ta_diastolica=ta_diastolica,
            fc=fc,
            temperatura=temperatura,
            animo=animo,
            alimentacion=alimentacion,
            higiene=higiene,
            eliminacion=eliminacion,
            medicacion_administrada=medicacion_administrada,
            observaciones_extra=observaciones_extra,
        )

        if preview_btn:
            st.info("### Vista previa del texto profesional")
            st.markdown(f"```\n{texto_generado}\n```")

        if guardar_btn:
            if texto_generado == "Sin registros en este turno." and not observaciones_extra.strip():
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
                    "plantilla": "Cuidador",
                    "tipo_evolucion": "cuidador",
                    "cuidador_data": {
                        "ta_sistolica": ta_sistolica,
                        "ta_diastolica": ta_diastolica,
                        "fc": fc,
                        "temperatura": temperatura,
                        "animo": animo,
                        "alimentacion": alimentacion,
                        "higiene": higiene,
                        "eliminacion": eliminacion,
                        "medicacion_administrada": medicacion_administrada,
                        "observaciones_extra": observaciones_extra.strip(),
                    },
                })
                from core.database import _trim_db_list
                _trim_db_list("evoluciones_db", 500)

                registrar_auditoria_legal(
                    "Evolucion Clinica",
                    paciente_sel,
                    "Nueva evolucion de cuidador",
                    user.get("nombre", ""),
                    user.get("matricula", ""),
                    "Se registro evolucion mediante panel de cuidador.",
                )
                guardar_datos(spinner=True)

                try:
                    from core.nextgen_sync import sync_visita_evolucion_to_nextgen
                    sync_visita_evolucion_to_nextgen(paciente_sel, texto_generado[:500])
                except Exception:
                    from core.app_logging import log_event
                    log_event("evolucion_cuidador", "nextgen_sync_skip")

                queue_toast("Evolucion de cuidador guardada correctamente.")
                st.rerun()
