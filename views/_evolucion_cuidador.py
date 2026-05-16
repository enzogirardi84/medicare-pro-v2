"""Panel de evolucion para cuidadores. Convierte selecciones simples en texto profesional."""

import streamlit as st
from core.utils import ahora, registrar_auditoria_legal
from core.database import guardar_datos
from core.alert_toasts import queue_toast


def _generar_texto_evolucion_cuidador(
    ta_sistolica, ta_diastolica, fc, temperatura, spo2,
    animo, alimentacion, higiene, eliminacion,
    respiracion, dolor, movilidad, piel, sueno, conducta,
    medicacion_administrada,
    observaciones_extra,
) -> str:
    partes = []

    if ta_sistolica and ta_diastolica:
        partes.append(f"TA {ta_sistolica}/{ta_diastolica} mmHg")
    if fc:
        partes.append(f"FC {fc} lpm")
    if temperatura:
        partes.append(f"T {temperatura} °C")
    if spo2:
        partes.append(f"SpO2 {spo2}%")

    sv_text = ""
    if partes:
        sv_text = "Signos vitales: " + ", ".join(partes) + ". "

    estado_partes = []

    mapa_animo = {
        "Despierto": "Paciente despierto y consciente",
        "Somnoliento": "Paciente somnoliento pero reagible al llamado",
        "Tranquilo": "Paciente tranquilo y colaborador",
        "Irritable": "Paciente irritable durante la evaluacion",
        "Desorientado": "Paciente desorientado en tiempo y espacio",
        "Ansioso": "Paciente ansioso durante la evaluacion",
    }
    if animo in mapa_animo:
        estado_partes.append(mapa_animo[animo])

    mapa_conducta = {
        "Cooperador": "Cooperador durante los cuidados",
        "Agitado": "Agitado durante la evaluacion",
        "Confuso": "Confuso, requiere contencion y reorientacion",
        "Desmotivado": "Desmotivado, con poca respuesta a estimulos",
        "Agresivo": "Agresivo, requiere contencion verbal y fisica",
    }
    if conducta in mapa_conducta:
        estado_partes.append(mapa_conducta[conducta])

    mapa_alimentacion = {
        "Comio todo": "Tolera dieta por via oral sin complicaciones",
        "Comio poco": "Ingesta oral reducida, tolera parcialmente la dieta",
        "No quiso comer": "Rechaza la alimentacion por via oral",
        "Alimentacion por sonda": "Recibe alimentacion por sonda nasogastrica o gastrostomia sin incidentes",
        "Dieta liquida": "Recibe dieta liquida, tolera sin complicaciones",
        "Dieta blanda": "Recibe dieta blanda, tolera adecuadamente",
        "Succion": "Alimentacion por succion, reflejo presente",
        "Requiere asistencia": "Requiere asistencia total para la alimentacion",
    }
    if alimentacion in mapa_alimentacion:
        estado_partes.append(mapa_alimentacion[alimentacion])

    mapa_higiene = {
        "Se bano solo": "Higiene personal realizada de forma autonoma",
        "Bano en cama": "Se realizo higiene en cama con asistencia del personal",
        "Cambio de panial": "Se realizo cambio de panial, piel integra sin lesiones",
        "Aseo parcial": "Se realizo aseo parcial, colabora con la higiene",
        "Rechaza higiene": "Rechaza la higiene, requiere insistencia",
    }
    if higiene in mapa_higiene:
        estado_partes.append(mapa_higiene[higiene])

    mapa_eliminacion = {
        "Orino bien": "Diuresis conservada, orina espontanea sin alteraciones",
        "No orino": "No registra diuresis en el turno",
        "Hizo deposicion": "Deposicion presente, caracteristicas dentro de parametros",
        "No hizo deposicion": "No registra deposicion en el turno",
        "Diarrea": "Deposiciones liquidas multiples en el turno",
        "Estrenimiento": "Estrenimiento, sin deposicion en mas de 72 horas",
        "Sonda vesical": "Porta sonda vesical, diuresis conservada",
        "Incontinencia": "Episodios de incontinencia urinaria o fecal en el turno",
    }
    if eliminacion in mapa_eliminacion:
        estado_partes.append(mapa_eliminacion[eliminacion])

    mapa_respiracion = {
        "Sin asistencia": "Respiracion espontanea sin asistencia, saturando adecuadamente",
        "Con oxigeno por canula": "Recibe oxigeno suplementario por canula nasal",
        "Con mascara": "Recibe oxigeno por mascara de reservorio",
        "Disnea en reposo": "Presenta disnea en reposo",
        "Disnea con esfuerzo": "Presenta disnea con esfuerzos minimos",
        "Tos productiva": "Tos productiva con expectoracion mucosa",
        "Tos seca": "Tos seca sin expectoracion",
        "Ventilacion mecanica": "Paciente en ventilacion mecanica",
    }
    if respiracion in mapa_respiracion:
        estado_partes.append(mapa_respiracion[respiracion])

    mapa_dolor = {
        "Sin dolor": "Sin signos de dolor al momento de la evaluacion",
        "Leve": "Refiere dolor leve, escala EVA 1-3",
        "Moderado": "Refiere dolor moderado, escala EVA 4-6",
        "Intenso": "Refiere dolor intenso, escala EVA 7-10",
        "No evaluable": "No es posible evaluar dolor por condicion del paciente",
    }
    if dolor in mapa_dolor:
        estado_partes.append(mapa_dolor[dolor])

    mapa_movilidad = {
        "Camina solo": "Deambula de forma autonoma sin dificultad",
        "Camina con ayuda": "Deambula con asistencia de una persona o andador",
        "En silla de ruedas": "Permanece en silla de ruedas, requiere asistencia para traslados",
        "En cama": "Paciente en reposo absoluto en cama",
        "Requiere movilizacion": "Requiere movilizacion asistida cada 2 horas",
    }
    if movilidad in mapa_movilidad:
        estado_partes.append(mapa_movilidad[movilidad])

    mapa_piel = {
        "Hidratada": "Piel hidratada, mucosa oral humeda, signo de pliegue negativo",
        "Seca": "Piel seca, mucosa oral discretamente seca",
        "Con lesiones": "Presenta lesion cutanea en observacion",
        "Con escaras": "Presenta ulcera por presion, se realizan curaciones segun protocolo",
        "Con eritema": "Presenta eritema en zona de presion, se realizan cambios posturales",
        "Edematosa": "Edema en miembros inferiores, signo de Godet positivo",
        "Cianotica": "Cianosis en extremidades",
        "Ictericia": "Coloracion icterica de piel y mucosas",
    }
    if piel in mapa_piel:
        estado_partes.append(mapa_piel[piel])

    mapa_sueno = {
        "Durmio bien": "Paciente refiere sueno reparador",
        "Durmio poco": "Paciente refiere sueno fragmentado o de corta duracion",
        "Insomnio": "Paciente refiere insomnio, no logro conciliar el sueno",
        "Somnolencia diurna": "Paciente somnoliento durante el dia",
        "Descanso interrumpido": "Descanso interrumpido por dolor o malestar",
    }
    if sueno in mapa_sueno:
        estado_partes.append(mapa_sueno[sueno])

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
    st.markdown("##### Registro inteligente de evolucion")
    st.caption("Completá el estado del paciente de forma sencilla. Al guardar se genera un texto profesional automaticamente.")

    if not puede_registrar:
        st.caption("La carga de evoluciones queda deshabilitada para este rol.")
        return

    with st.form("evol_cuidador", clear_on_submit=False):
        st.markdown("**Signos vitales**")
        sv_cols = st.columns(5)
        ta_sistolica = sv_cols[0].number_input("TA sist (mmHg)", min_value=0, max_value=300, value=120, step=1, key="evc_ta_sis")
        ta_diastolica = sv_cols[0].number_input("TA dias (mmHg)", min_value=0, max_value=200, value=80, step=1, key="evc_ta_dias")
        fc = sv_cols[1].number_input("FC (lpm)", min_value=0, max_value=300, value=80, step=1, key="evc_fc")
        temperatura = sv_cols[2].number_input("Temp (°C)", min_value=34.0, max_value=42.0, value=36.5, step=0.1, key="evc_temp")
        spo2 = sv_cols[3].number_input("SpO2 (%)", min_value=0, max_value=100, value=96, step=1, key="evc_spo2")
        sv_cols[4].markdown("")

        st.divider()
        st.markdown("**Estado general**")

        with st.expander("Neurologico y conducta", expanded=True):
            c1, c2 = st.columns(2)
            animo = c1.selectbox("Animo / Neurologico", ["", "Despierto", "Somnoliento", "Tranquilo", "Irritable", "Desorientado", "Ansioso"], key="evc_animo")
            conducta = c2.selectbox("Conducta", ["", "Cooperador", "Agitado", "Confuso", "Desmotivado", "Agresivo"], key="evc_conducta")

        with st.expander("Alimentacion e higiene", expanded=True):
            c1, c2 = st.columns(2)
            alimentacion = c1.selectbox("Alimentacion", ["", "Comio todo", "Comio poco", "No quiso comer", "Alimentacion por sonda", "Dieta liquida", "Dieta blanda", "Succion", "Requiere asistencia"], key="evc_alimentacion")
            higiene = c2.selectbox("Higiene", ["", "Se bano solo", "Bano en cama", "Cambio de panial", "Aseo parcial", "Rechaza higiene"], key="evc_higiene")

        with st.expander("Eliminacion", expanded=False):
            eliminacion = st.selectbox("Eliminacion", ["", "Orino bien", "No orino", "Hizo deposicion", "No hizo deposicion", "Diarrea", "Estrenimiento", "Sonda vesical", "Incontinencia"], key="evc_eliminacion")

        with st.expander("Respiracion y dolor", expanded=False):
            c1, c2 = st.columns(2)
            respiracion = c1.selectbox("Respiracion / Oxigeno", ["", "Sin asistencia", "Con oxigeno por canula", "Con mascara", "Disnea en reposo", "Disnea con esfuerzo", "Tos productiva", "Tos seca", "Ventilacion mecanica"], key="evc_respiracion")
            dolor = c2.selectbox("Dolor", ["", "Sin dolor", "Leve", "Moderado", "Intenso", "No evaluable"], key="evc_dolor")

        with st.expander("Movilidad y piel", expanded=False):
            c1, c2 = st.columns(2)
            movilidad = c1.selectbox("Movilidad / Deambulacion", ["", "Camina solo", "Camina con ayuda", "En silla de ruedas", "En cama", "Requiere movilizacion"], key="evc_movilidad")
            piel = c2.selectbox("Piel / Mucosas", ["", "Hidratada", "Seca", "Con lesiones", "Con escaras", "Con eritema", "Edematosa", "Cianotica", "Ictericia"], key="evc_piel")

        with st.expander("Sueno y descanso", expanded=False):
            sueno = st.selectbox("Sueno / Descanso", ["", "Durmio bien", "Durmio poco", "Insomnio", "Somnolencia diurna", "Descanso interrumpido"], key="evc_sueno")

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
            spo2=spo2,
            animo=animo,
            alimentacion=alimentacion,
            higiene=higiene,
            eliminacion=eliminacion,
            respiracion=respiracion,
            dolor=dolor,
            movilidad=movilidad,
            piel=piel,
            sueno=sueno,
            conducta=conducta,
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
            if not any([ta_sistolica, ta_diastolica, fc, temperatura, spo2,
                        animo, alimentacion, higiene, eliminacion,
                        respiracion, dolor, movilidad, piel, sueno, conducta,
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
                    "plantilla": "Cuidador",
                    "tipo_evolucion": "cuidador",
                    "cuidador_data": {
                        "ta_sistolica": ta_sistolica,
                        "ta_diastolica": ta_diastolica,
                        "fc": fc,
                        "temperatura": temperatura,
                        "spo2": spo2,
                        "animo": animo,
                        "conducta": conducta,
                        "alimentacion": alimentacion,
                        "higiene": higiene,
                        "eliminacion": eliminacion,
                        "respiracion": respiracion,
                        "dolor": dolor,
                        "movilidad": movilidad,
                        "piel": piel,
                        "sueno": sueno,
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

                queue_toast("Evolucion de cuidador guardada correctamente.")
                st.rerun()
