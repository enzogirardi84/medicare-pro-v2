"""Panel de evolucion asistida basado en Patrones Funcionales de Marjory Gordon."""

import streamlit as st
from core.utils import ahora, registrar_auditoria_legal
from core.database import guardar_datos
from core.alert_toasts import queue_toast


def _generar_texto_evolucion(
    ta_sistolica, ta_diastolica, fc, temperatura,
    higiene, movilidad,
    animo, dolor_presente, dolor_eva,
    alimentacion,
    herida_mecanismo, herida_profundidad,
    herida_localizacion,
    herida_lecho, herida_exudado,
    herida_infeccion, herida_curacion,
    diuresis, deposicion,
    descanso,
    medicacion_administrada,
    observaciones_extra,
) -> str:
    parrafos = []

    sv_partes = []
    if ta_sistolica and ta_diastolica:
        sv_partes.append(f"TA {ta_sistolica}/{ta_diastolica} mmHg")
    if fc:
        sv_partes.append(f"FC {fc} lpm")
    if temperatura:
        sv_partes.append(f"Temp {temperatura} C")
    if sv_partes:
        parrafos.append("Signos vitales: " + ", ".join(sv_partes) + ".")

    mapa_animo = {
        "Despierto y tranquilo": "Paciente vigil y tranquilo",
        "Somnoliento": "Paciente somnoliento pero reagible al llamado",
        "Apatico": "Paciente apatico, con poca respuesta a estimulos",
        "Irritable": "Paciente irritable durante la evaluacion",
        "Desorientado": "Paciente desorientado en tiempo y espacio",
    }
    if animo in mapa_animo:
        parrafos.append(mapa_animo[animo] + ".")

    if dolor_presente and dolor_eva:
        parrafos.append(f"Refiere dolor, escala EVA {int(dolor_eva)}/10.")
    elif dolor_presente:
        parrafos.append("Refiere dolor al momento de la evaluacion.")
    else:
        parrafos.append("Sin signos de dolor al momento de la evaluacion.")

    mapa_alimentacion = {
        "Comio toda su porcion": "Tolera dieta por via oral sin complicaciones, ingiere la totalidad de la porcion",
        "Comio poco": "Ingesta oral reducida, tolera parcialmente la dieta",
        "No quiso comer": "Rechaza la alimentacion por via oral",
        "Alimentacion por sonda": "Recibe alimentacion por sonda nasogastrica o gastrostomia sin incidentes",
    }
    if alimentacion in mapa_alimentacion:
        parrafos.append(mapa_alimentacion[alimentacion] + ".")

    mapa_mecanismo = {
        "Incisas": "Herida incisa por objeto afilado, bordes limpios",
        "Contusas": "Herida contusa por impacto, con bordes irregulares y hematoma perilesional",
        "Punzantes": "Herida punzante con orificio de entrada puntiforme y riesgo de infeccion profunda",
        "Laceraciones": "Laceracion con bordes dentados e irregulares por friccion violenta",
        "Abrasiones": "Abrasion superficial por friccion, afecta solo epidermis",
        "Avulsiones": "Avulsion con desprendimiento parcial del tejido",
        "Ulceras": "Ulcera cronica con perdida de sustancia y cicatrizacion lenta",
    }
    if herida_mecanismo in mapa_mecanismo:
        txt = mapa_mecanismo[herida_mecanismo]
        if herida_profundidad:
            mapa_profundidad = {
                "Grado I": "Grado I (superficial, solo epidermis)",
                "Grado II": "Grado II (espesor parcial, epidermis y dermis)",
                "Grado III": "Grado III (espesor total, hasta tejido celular subcutaneo)",
                "Grado IV": "Grado IV (expone musculo, tendones u hueso)",
            }
            txt += ", " + mapa_profundidad.get(herida_profundidad, herida_profundidad)
        detalles_herida = []
        if herida_localizacion:
            detalles_herida.append(f"localizada en {herida_localizacion}")
        if detalles_herida:
            txt += ", " + ", ".join(detalles_herida)
        mapa_lecho = {
            "Granulacion": "lecho con tejido de granulacion",
            "Fibrina": "lecho cubierto de fibrina",
            "Necrotico": "lecho con tejido necrotico",
            "Mixto": "lecho mixto con tejido de granulacion y fibrina",
            "Epitelizacion": "lecho en fase de epitelizacion",
        }
        if herida_lecho in mapa_lecho:
            txt += ", " + mapa_lecho[herida_lecho]
        mapa_exudado = {
            "Seroso": "exudado seroso escaso",
            "Serohematico": "exudado serohematico",
            "Purulento": "exudado purulento",
            "Hemorragico": "exudado hemorragico",
            "Sin exudado": "sin exudado",
        }
        if herida_exudado in mapa_exudado:
            txt += ", " + mapa_exudado[herida_exudado]
        if herida_infeccion:
            txt += ", con signos de infeccion: " + herida_infeccion
        parrafos.append(txt + ".")
        if herida_curacion:
            parrafos.append(f"Se realiza {herida_curacion}.")

    mapa_higiene = {
        "Se baño solo": "Higiene personal realizada de forma autonoma",
        "Baño en cama": "Se realizo higiene en cama con asistencia del personal",
        "Cambio de pañal": "Se realizo cambio de pañal, piel integra sin lesiones",
    }
    if higiene in mapa_higiene:
        parrafos.append(mapa_higiene[higiene] + ".")

    mapa_movilidad = {
        "Reposo en cama": "Paciente en reposo absoluto en cama",
        "Camino con ayuda": "Deambula con asistencia de una persona o andador",
        "Camino solo": "Deambula de forma autonoma sin dificultad",
    }
    if movilidad in mapa_movilidad:
        parrafos.append(mapa_movilidad[movilidad] + ".")

    mapa_diuresis = {
        "Orino bien": "Diuresis conservada, orina espontanea sin alteraciones",
        "No orino": "No registra diuresis en el turno",
        "Tiene sonda vesical": "Porta sonda vesical, diuresis conservada",
        "Orina escasa": "Diuresis disminuida, orina escasa en el turno",
        "Orina frecuente": "Polaquiuria, micciones frecuentes en el turno",
        "Incontinencia urinaria": "Episodios de incontinencia urinaria en el turno",
        "Miccion dolorosa": "Refiere dolor o ardor al orinar",
    }
    if diuresis in mapa_diuresis:
        parrafos.append(mapa_diuresis[diuresis] + ".")

    mapa_deposicion = {
        "No hizo deposicion": "No registra deposicion en el turno",
        "Deposicion normal": "Deposicion presente, caracteristicas dentro de parametros",
        "Diarrea": "Deposiciones liquidas multiples en el turno",
        "Estrenimiento": "Estrenimiento, sin deposicion en mas de 72 horas",
        "Deposicion con esfuerzo": "Deposicion presente pero con esfuerzo",
        "Incontinencia fecal": "Episodios de incontinencia fecal en el turno",
    }
    if deposicion in mapa_deposicion:
        parrafos.append(mapa_deposicion[deposicion] + ".")

    mapa_descanso = {
        "Durmio bien toda la noche": "Descanso nocturno conservado",
        "Le costo dormir": "Descanso nocturno fragmentado, con dificultad para conciliar el sueno",
        "Estuvo inquieto": "Descanso nocturno interrumpido por inquietud o malestar",
    }
    if descanso in mapa_descanso:
        parrafos.append(mapa_descanso[descanso] + ".")

    if medicacion_administrada:
        parrafos.append("Se administra medicacion segun indicacion correspondiente al horario, sin eventualidades.")

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
    st.caption("Completá el estado del paciente por patrones funcionales. Al guardar se genera automaticamente un texto profesional.")

    if not puede_registrar:
        st.caption("La carga de evoluciones queda deshabilitada para este rol.")
        return

    with st.form("evol_cuidador", clear_on_submit=False):
        with st.expander("1. Actividad y Ejercicio", expanded=True):
            sv_cols = st.columns(4)
            ta_sistolica = sv_cols[0].number_input("TA sist (mmHg)", min_value=0, max_value=300, value=120, step=1, key="evc_ta_sis")
            ta_diastolica = sv_cols[0].number_input("TA dias (mmHg)", min_value=0, max_value=200, value=80, step=1, key="evc_ta_dias")
            fc = sv_cols[1].number_input("FC (lpm)", min_value=0, max_value=300, value=80, step=1, key="evc_fc")
            temperatura = sv_cols[2].number_input("Temp (C)", min_value=34.0, max_value=42.0, value=36.5, step=0.1, key="evc_temp")
            c_act1, c_act2 = st.columns(2)
            higiene = c_act1.selectbox("Higiene", ["", "Se baño solo", "Baño en cama", "Cambio de pañal"], key="evc_higiene")
            movilidad = c_act2.selectbox("Movilidad", ["", "Reposo en cama", "Camino con ayuda", "Camino solo"], key="evc_movilidad")

        with st.expander("2. Cognitivo - Perceptivo", expanded=False):
            animo = st.selectbox(
                "Estado neurologico / Animo",
                ["", "Despierto y tranquilo", "Somnoliento", "Apatico", "Irritable", "Desorientado"],
                key="evc_animo",
            )
            col_dolor1, col_dolor2 = st.columns([1, 2])
            dolor_presente = col_dolor1.checkbox("Refiere dolor", key="evc_dolor_check")
            dolor_eva = 0
            if dolor_presente:
                dolor_eva = col_dolor2.slider("Escala EVA (1-10)", min_value=1, max_value=10, value=5, key="evc_dolor_eva", help="1 = dolor minimo, 10 = dolor maximo")

        with st.expander("3. Nutricional - Metabolico", expanded=False):
            alimentacion = st.selectbox(
                "Alimentacion",
                ["", "Comio toda su porcion", "Comio poco", "No quiso comer", "Alimentacion por sonda"],
                key="evc_alimentacion",
            )

        with st.expander("6. Heridas y curaciones", expanded=False):
            st.caption("Completar solo si el paciente presenta alguna lesion o herida activa.")
            c_her1, c_her2 = st.columns(2)
            herida_mecanismo = c_her1.selectbox(
                "Clasificacion segun mecanismo",
                ["", "Incisas", "Contusas", "Punzantes", "Laceraciones", "Abrasiones", "Avulsiones", "Ulceras"],
                key="evc_herida_mec",
            )
            herida_profundidad = c_her2.selectbox(
                "Clasificacion segun profundidad",
                ["", "Grado I", "Grado II", "Grado III", "Grado IV"],
                key="evc_herida_prof",
            )
            herida_localizacion = st.text_input(
                "Localizacion de la herida",
                placeholder="Ej: sacro, talon derecho, pierna izquierda",
                key="evc_herida_loc",
            )
            c_her3, c_her4 = st.columns(2)
            herida_lecho = c_her3.selectbox(
                "Estado del lecho",
                ["", "Granulacion", "Fibrina", "Necrotico", "Mixto", "Epitelizacion"],
                key="evc_herida_lecho",
            )
            herida_exudado = c_her4.selectbox(
                "Tipo de exudado",
                ["", "Sin exudado", "Seroso", "Serohematico", "Purulento", "Hemorragico"],
                key="evc_herida_exud",
            )
            herida_infeccion = st.multiselect(
                "Signos de infeccion (opcional)",
                ["Eritema", "Edema", "Calor local", "Mal olor", "Secrecion purulenta", "Fiebre"],
                key="evc_herida_inf",
            )
            herida_curacion = st.text_input(
                "Tipo de curacion realizada",
                placeholder="Ej: curacion con solucion fisiologica y gasa esteril",
                key="evc_herida_cura",
            )

        with st.expander("4. Eliminacion", expanded=False):
            c_eli1, c_eli2 = st.columns(2)
            diuresis = c_eli1.selectbox(
                "Diuresis",
                ["", "Orino bien", "No orino", "Tiene sonda vesical", "Orina escasa", "Orina frecuente", "Incontinencia urinaria", "Miccion dolorosa"],
                key="evc_diuresis",
            )
            deposicion = c_eli2.selectbox(
                "Deposicion",
                ["", "No hizo deposicion", "Deposicion normal", "Diarrea", "Estrenimiento", "Deposicion con esfuerzo", "Incontinencia fecal"],
                key="evc_deposicion",
            )

        with st.expander("5. Sueno - Descanso", expanded=False):
            descanso = st.selectbox(
                "Descanso",
                ["", "Durmio bien toda la noche", "Le costo dormir", "Estuvo inquieto"],
                key="evc_descanso",
            )

        st.divider()
        st.markdown("**6. Medicacion**")
        medicacion_administrada = st.checkbox(
            "Se administro la medicacion correspondiente al turno",
            value=False,
            key="evc_med_check",
        )

        st.divider()
        observaciones_extra = st.text_area(
            "Observaciones (opcional)",
            placeholder="Si paso algo fuera de lo comun, describilo aca con tus palabras.",
            height=80,
            key="evc_obs",
        )

        st.divider()
        col_btn1, col_btn2, col_btn3 = st.columns([1, 1, 1])
        with col_btn2:
            preview_btn = st.form_submit_button("Previsualizar", width='stretch', type="secondary")
        with col_btn3:
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
            herida_mecanismo=herida_mecanismo,
            herida_profundidad=herida_profundidad,
            herida_localizacion=herida_localizacion,
            herida_lecho=herida_lecho,
            herida_exudado=herida_exudado,
            herida_infeccion=", ".join(herida_infeccion),
            herida_curacion=herida_curacion,
            diuresis=diuresis,
            deposicion=deposicion,
            descanso=descanso,
            medicacion_administrada=medicacion_administrada,
            observaciones_extra=observaciones_extra,
        )

        if preview_btn:
            st.markdown("### Vista previa del texto profesional")
            st.code(texto_generado, language="text", line_numbers=True)

        if guardar_btn:
            if not any([ta_sistolica, ta_diastolica, fc, temperatura,
                        higiene, movilidad, animo,
                        dolor_presente,
                        alimentacion,
                        herida_mecanismo, herida_profundidad,
                        herida_localizacion,
                        herida_lecho, herida_exudado, herida_infeccion, herida_curacion,
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
                        "herida_mecanismo": herida_mecanismo,
                        "herida_profundidad": herida_profundidad,
                        "herida_localizacion": herida_localizacion,
                        "herida_lecho": herida_lecho,
                        "herida_exudado": herida_exudado,
                        "herida_infeccion": ", ".join(herida_infeccion),
                        "herida_curacion": herida_curacion,
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
