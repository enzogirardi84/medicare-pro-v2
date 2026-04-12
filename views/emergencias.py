import base64
import io
from uuid import uuid4

import pandas as pd
import streamlit as st
from PIL import Image

from core.clinical_exports import build_emergency_pdf_bytes
from core.database import guardar_datos
from core.utils import ahora, decodificar_base64_seguro, mostrar_dataframe_con_scroll, registrar_auditoria_legal, seleccionar_limite_registros

CANVAS_DISPONIBLE = False
try:
    from streamlit_drawable_canvas import st_canvas

    CANVAS_DISPONIBLE = True
except ImportError:
    pass


EVENTO_CATEGORIAS = {
    "Cardiovascular": [
        "IAM / Infarto agudo de miocardio",
        "Dolor toracico de probable origen cardiaco",
        "Arritmia / palpitaciones",
        "Paro cardiorrespiratorio",
        "Insuficiencia cardiaca aguda / edema agudo de pulmon",
        "Crisis hipertensiva",
        "Sindrome coronario agudo",
    ],
    "Neurologico": [
        "ACV / Stroke",
        "Convulsion",
        "TEC grave",
        "TEC moderado",
        "TEC leve",
        "Perdida de conocimiento / sincope",
        "Deficit neurologico agudo",
        "Cefalea intensa / alarma neurologica",
    ],
    "Respiratorio": [
        "Dificultad respiratoria",
        "Insuficiencia respiratoria aguda",
        "Broncoespasmo / crisis asmatica",
        "EPOC reagudizado",
        "Neumonia / foco respiratorio",
        "Paro respiratorio",
        "Saturacion critica",
    ],
    "Trauma": [
        "Caida de propia altura",
        "Politrauma",
        "Trauma de craneo",
        "Trauma de torax",
        "Trauma abdominal",
        "Fractura cerrada",
        "Fractura expuesta",
        "Herida cortante / sangrado activo",
        "Quemadura",
    ],
    "Metabolico y toxico": [
        "Hipoglucemia",
        "Hiperglucemia",
        "Cetoacidosis / descompensacion diabetica",
        "Intoxicacion medicamentosa",
        "Intoxicacion alcoholica",
        "Intoxicacion alimentaria / toxica",
        "Alteracion hidroelectrolitica",
    ],
    "Infeccioso / sepsis": [
        "Fiebre de origen desconocido",
        "Sepsis sospechada",
        "Shock septico",
        "Infeccion urinaria complicada",
        "Celulitis / infeccion de piel",
        "Infeccion respiratoria aguda",
    ],
    "Obstetrico": [
        "Trabajo de parto",
        "Metrorragia / sangrado obstetrico",
        "Dolor abdominal en embarazo",
        "Preeclampsia / eclampsia",
        "Control obstetrico urgente",
    ],
    "Pediatrico": [
        "Fiebre alta en nino",
        "Convulsion febril",
        "Dificultad respiratoria pediatrica",
        "Trauma pediatrico",
        "Deshidratacion",
        "Reaccion alergica",
    ],
    "Psiquiatrico y conducta": [
        "Agitacion psicomotriz",
        "Intento de suicidio",
        "Crisis de angustia / panico",
        "Riesgo para si o terceros",
        "Desorientacion / alteracion conductual",
    ],
    "Traslados": [
        "Traslado asistencial",
        "Derivacion cronica",
        "Traslado programado",
        "Traslado interhospitalario",
        "Alta complejidad / UTI movil",
        "Derivacion a guardia",
        "Derivacion a internacion",
        "Retorno a domicilio",
    ],
    "General": [
        "Descompensacion general",
        "Dolor abdominal",
        "Hemorragia",
        "Reaccion alergica",
        "Deshidratacion",
        "Consulta clinica urgente",
    ],
}


def _firma_a_b64(canvas_result):
    if not canvas_result or canvas_result.image_data is None:
        return ""
    img = Image.fromarray(canvas_result.image_data.astype("uint8"), "RGBA")
    fondo = Image.new("RGB", img.size, (255, 255, 255))
    fondo.paste(img, mask=img.split()[-1])
    buf = io.BytesIO()
    fondo.save(buf, format="JPEG", optimize=True, quality=65)
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def _badge_html(texto, clase):
    return f"<span class='mc-chip {clase}'>{texto}</span>"


def _triage_meta(grado):
    mapping = {
        "Grado 1 - Rojo": {"prioridad": "Critica", "codigo": "Rojo", "clase": "mc-chip-danger"},
        "Grado 2 - Amarillo": {"prioridad": "Alta", "codigo": "Amarillo", "clase": "mc-chip-warning"},
        "Grado 3 - Verde": {"prioridad": "Media", "codigo": "Verde", "clase": "mc-chip-success"},
    }
    return mapping.get(grado, {"prioridad": "Media", "codigo": "Verde", "clase": ""})


def render_emergencias(paciente_sel, mi_empresa, user):
    if not paciente_sel:
        st.info("Selecciona un paciente para registrar una emergencia o traslado.")
        return

    detalles = st.session_state.get("detalles_pacientes_db", {}).get(paciente_sel, {})
    eventos = [x for x in st.session_state.get("emergencias_db", []) if x.get("paciente") == paciente_sel]
    activos = [x for x in eventos if x.get("triage_grado") in {"Grado 1 - Rojo", "Grado 2 - Amarillo"}]
    traslados = [x for x in eventos if x.get("ambulancia_solicitada")]

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Emergencias y ambulancia</h2>
            <p class="mc-hero-text">Modulo operativo y legal para registrar alertas criticas, triage, solicitud de movil,
            parte prehospitalario, traslado y recepcion del paciente con trazabilidad profesional.</p>
            <div class="mc-chip-row">
                <span class="mc-chip mc-chip-danger">Grado 1 rojo</span>
                <span class="mc-chip mc-chip-warning">Grado 2 amarillo</span>
                <span class="mc-chip mc-chip-success">Grado 3 verde</span>
                <span class="mc-chip">Ambulancia</span>
                <span class="mc-chip">PDF legal</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Eventos registrados", len(eventos))
    m2.metric("Triage rojo/amarillo", len(activos))
    m3.metric("Traslados solicitados", len(traslados))
    m4.metric("Ultimo evento", eventos[-1]["fecha_evento"] if eventos else "Sin eventos")

    st.markdown(
        """
        <div class="mc-grid-3">
            <div class="mc-card"><h4>1. Alerta inmediata</h4><p>Deja asentado el tipo de urgencia, prioridad, domicilio y hora exacta del inicio del evento.</p></div>
            <div class="mc-card"><h4>2. Triage por grados</h4><p>Clasifica rapido en Grado 1 rojo, Grado 2 amarillo o Grado 3 verde con impacto operativo inmediato.</p></div>
            <div class="mc-card"><h4>3. Traslado trazable</h4><p>Guarda movil, tiempos de respuesta, destino, familiar notificado y PDF imprimible.</p></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    vista = st.radio(
        "Vista del modulo",
        ["Registrar evento", "Panel operativo", "Historial y PDF"],
        horizontal=False,
        label_visibility="collapsed",
        key="emergencias_vista_radio",
    )

    if vista == "Registrar evento":
        st.markdown("### Nuevo evento critico o traslado")
        with st.container(border=True):
            fecha_actual = ahora()
            c1, c2, c3 = st.columns([2, 2, 1])
            categoria_evento = c1.selectbox("Categoria principal", list(EVENTO_CATEGORIAS.keys()))
            patologias_categoria = EVENTO_CATEGORIAS.get(categoria_evento, ["Evento no clasificado"])
            tipo_evento = c2.selectbox("Patologia / motivo presuntivo", patologias_categoria)
            triage_grado = c3.selectbox(
                "Clasificacion de triage",
                ["Grado 1 - Rojo", "Grado 2 - Amarillo", "Grado 3 - Verde"],
                index=1,
            )
            triage_info = _triage_meta(triage_grado)
            codigo_alerta = st.text_input("Color / codigo", value=triage_info["codigo"], disabled=True)

            st.markdown(
                f"""
                <div class="mc-note">
                    <strong>Triage actual:</strong> <span class="mc-chip {triage_info['clase']}">{triage_grado}</span><br>
                    <strong>Prioridad operativa:</strong> {triage_info['prioridad']}<br>
                    <strong>Uso sugerido:</strong> {"Activacion inmediata de movil y medico" if triage_grado == "Grado 1 - Rojo" else "Atencion prioritaria y monitoreo cercano" if triage_grado == "Grado 2 - Amarillo" else "Control y seguimiento programado / demora segura"}
                </div>
                """,
                unsafe_allow_html=True,
            )

            c4, c5, c6 = st.columns(3)
            fecha_evento = c4.date_input("Fecha del evento", value=fecha_actual.date())
            hora_evento = c5.time_input("Hora del evento", value=fecha_actual.time().replace(microsecond=0))
            tipo_traslado = c6.selectbox(
                "Tipo de traslado",
                [
                    "Sin traslado confirmado",
                    "Traslado asistencial",
                    "Derivacion cronica",
                    "Traslado interhospitalario",
                    "Alta complejidad / UTI movil",
                    "Derivacion a guardia",
                    "Retorno a domicilio",
                ],
            )

            motivo = st.text_area("Resumen del cuadro y descripcion inicial", height=90)
            direccion_evento = st.text_input("Domicilio / lugar del evento", value=detalles.get("direccion", ""))

            st.markdown("#### Triage inicial")
            t1, t2, t3, t4 = st.columns(4)
            presion = t1.text_input("Presion arterial", placeholder="120/80")
            fc = t2.text_input("Frecuencia cardiaca", placeholder="78 lpm")
            saturacion = t3.text_input("Saturacion O2", placeholder="98%")
            temperatura = t4.text_input("Temperatura", placeholder="36.5 C")
            t5, t6, t7 = st.columns(3)
            glucemia = t5.text_input("Glucemia", placeholder="110 mg/dl")
            dolor = t6.selectbox("Dolor (EVA)", [str(x) for x in range(11)], index=0)
            conciencia = t7.selectbox("Estado de conciencia", ["Alerta", "Somnoliento", "Confuso", "No responde"])
            observaciones = st.text_area("Observaciones clinicas", height=90)

            st.markdown("#### Ambulancia, traslado y recepcion")
            a1, a2, a3 = st.columns(3)
            ambulancia_solicitada = a1.checkbox("Solicitar ambulancia", value=triage_info["prioridad"] in {"Alta", "Critica"})
            movil = a2.text_input("Movil / empresa", placeholder="Emerger / privado / SAME")
            destino = a3.text_input("Destino", placeholder="Clinica / hospital / guardia")
            a4, a5, a6 = st.columns(3)
            hora_solicitud = a4.text_input("Hora de solicitud", value=fecha_actual.strftime("%H:%M"))
            hora_arribo = a5.text_input("Hora de arribo", placeholder="HH:MM")
            hora_salida = a6.text_input("Hora de salida / entrega", placeholder="HH:MM")
            receptor = st.text_input("Profesional receptor / institucion receptora")
            familiar_notificado = st.text_input("Familiar o responsable notificado")

            st.markdown("#### Parte asistencial y legal")
            procedimientos = st.text_area("Procedimientos realizados", height=90)
            medicacion_administrada = st.text_area("Medicacion administrada", height=90)
            respuesta = st.text_area("Respuesta del paciente", height=80)
            observaciones_legales = st.text_area("Observaciones legales / cadena de custodia / conformidad", height=80)

            p1, p2 = st.columns(2)
            profesional = p1.text_input("Profesional a cargo", value=user.get("nombre", ""))
            matricula = p2.text_input("Matricula profesional", value=user.get("matricula", ""))

            firma_canvas = None
            if CANVAS_DISPONIBLE:
                st.caption("Firma digital del profesional interviniente")
                firma_canvas = st_canvas(
                    key="firma_emergencias",
                    background_color="#ffffff",
                    height=140,
                    drawing_mode="freedraw",
                    stroke_width=3,
                    stroke_color="#000000",
                    display_toolbar=True,
                )

            if st.button("Guardar evento critico", use_container_width=True, type="primary"):
                if not motivo.strip():
                    st.error("Debes indicar el motivo principal del evento.")
                elif not profesional.strip() or not matricula.strip():
                    st.error("Debes registrar profesional y matricula para dejar respaldo legal.")
                else:
                    nuevo = {
                        "id": str(uuid4()),
                        "paciente": paciente_sel,
                        "empresa": mi_empresa,
                        "fecha_evento": fecha_evento.strftime("%d/%m/%Y"),
                        "hora_evento": hora_evento.strftime("%H:%M"),
                        "categoria_evento": categoria_evento,
                        "tipo_evento": tipo_evento,
                        "tipo_traslado": tipo_traslado,
                        "triage_grado": triage_grado,
                        "prioridad": triage_info["prioridad"],
                        "codigo_alerta": codigo_alerta,
                        "motivo": motivo.strip(),
                        "direccion_evento": direccion_evento.strip(),
                        "presion_arterial": presion.strip(),
                        "fc": fc.strip(),
                        "saturacion": saturacion.strip(),
                        "temperatura": temperatura.strip(),
                        "glucemia": glucemia.strip(),
                        "dolor": dolor,
                        "conciencia": conciencia,
                        "observaciones": observaciones.strip(),
                        "ambulancia_solicitada": ambulancia_solicitada,
                        "movil": movil.strip(),
                        "hora_solicitud": hora_solicitud.strip(),
                        "hora_arribo": hora_arribo.strip(),
                        "hora_salida": hora_salida.strip(),
                        "destino": destino.strip(),
                        "receptor": receptor.strip(),
                        "familiar_notificado": familiar_notificado.strip(),
                        "procedimientos": procedimientos.strip(),
                        "medicacion_administrada": medicacion_administrada.strip(),
                        "respuesta": respuesta.strip(),
                        "observaciones_legales": observaciones_legales.strip(),
                        "profesional": profesional.strip(),
                        "matricula": matricula.strip(),
                        "firma_b64": _firma_a_b64(firma_canvas),
                        "creado_en": ahora().strftime("%d/%m/%Y %H:%M:%S"),
                        "creado_por": user.get("nombre", ""),
                    }
                    st.session_state["emergencias_db"].append(nuevo)
                    registrar_auditoria_legal(
                        "Emergencia",
                        paciente_sel,
                        "Evento critico registrado",
                        profesional.strip(),
                        matricula.strip(),
                        f"{categoria_evento} | {tipo_evento} | {triage_grado} | Traslado: {tipo_traslado}",
                    )
                    guardar_datos()
                    st.success("Evento de emergencia guardado con trazabilidad legal.")
                    st.rerun()

    elif vista == "Panel operativo":
        st.markdown("### Panel operativo del paciente")
        with st.container(border=True):
            st.markdown(
                f"""
                <div class="mc-note">
                    <strong>Paciente:</strong> {paciente_sel}<br>
                    <strong>Domicilio:</strong> {detalles.get("direccion", "S/D")}<br>
                    <strong>Telefono:</strong> {detalles.get("telefono", "S/D")}<br>
                    <strong>Alergias:</strong> {detalles.get("alergias", "Sin datos")}
                </div>
                """,
                unsafe_allow_html=True,
            )

        recientes = list(reversed(eventos[-6:]))
        if not recientes:
            st.info("Todavia no hay eventos de emergencia o ambulancia registrados para este paciente.")
        else:
            for evento in recientes:
                titulo = f"{evento.get('fecha_evento', '')} {evento.get('hora_evento', '')} | {evento.get('tipo_evento', '')}"
                with st.container(border=True):
                    col_info, col_badges = st.columns([4, 2])
                    col_info.markdown(f"#### {titulo}")
                    col_info.markdown(evento.get("motivo", ""))
                    badges = [
                        _badge_html(evento.get("triage_grado", "S/D"), _triage_meta(evento.get("triage_grado", "")).get("clase", "")),
                        _badge_html(evento.get("prioridad", "S/D"), ""),
                        _badge_html("Ambulancia" if evento.get("ambulancia_solicitada") else "Sin movil", ""),
                    ]
                    col_badges.markdown(" ".join(badges), unsafe_allow_html=True)
                    col_info.caption(
                        f"Categoria: {evento.get('categoria_evento', 'S/D')} | Profesional: {evento.get('profesional', 'S/D')} | Matricula: {evento.get('matricula', 'S/D')} | Destino: {evento.get('destino', 'S/D')} | Traslado: {evento.get('tipo_traslado', 'S/D')}"
                    )
                    if evento.get("firma_b64"):
                        try:
                            firma_bytes = decodificar_base64_seguro(evento["firma_b64"])
                            if firma_bytes:
                                col_badges.image(firma_bytes, caption="Firma profesional", width=180)
                        except Exception:
                            pass

    else:
        st.markdown("### Historial, tiempos y PDF")
        if not eventos:
            st.info("No hay eventos registrados para exportar.")
            return

        limite = seleccionar_limite_registros(
            "Eventos a mostrar",
            len(eventos),
            key="emergencias_historial_limite",
            default=20,
            opciones=(5, 10, 20, 30, 50, 100, 200, 500),
        )

        registros = list(reversed(eventos[-limite:]))
        resumen_df = pd.DataFrame(
            [
                {
                    "Fecha": f"{x.get('fecha_evento', '')} {x.get('hora_evento', '')}",
                    "Categoria": x.get("categoria_evento", ""),
                    "Tipo": x.get("tipo_evento", ""),
                    "Triage": x.get("triage_grado", ""),
                    "Prioridad": x.get("prioridad", ""),
                    "Traslado": x.get("tipo_traslado", ""),
                    "Movil": x.get("movil", ""),
                    "Destino": x.get("destino", ""),
                    "Profesional": x.get("profesional", ""),
                }
                for x in registros
            ]
        )
        mostrar_dataframe_con_scroll(resumen_df, height=380)

        with st.container(height=520):
            for idx, evento in enumerate(registros):
                with st.container(border=True):
                    c1, c2 = st.columns([3, 1])
                    c1.markdown(
                        f"**{evento.get('fecha_evento', '')} {evento.get('hora_evento', '')}** | {evento.get('tipo_evento', '')}"
                    )
                    c1.caption(
                        f"Categoria: {evento.get('categoria_evento', 'S/D')} | Triage: {evento.get('triage_grado', 'S/D')} | Prioridad: {evento.get('prioridad', 'S/D')} | Traslado: {evento.get('tipo_traslado', 'S/D')} | Profesional: {evento.get('profesional', 'S/D')}"
                    )
                    c1.markdown(evento.get("motivo", ""))
                    if evento.get("ambulancia_solicitada"):
                        c1.info(
                            f"Movil: {evento.get('movil', 'S/D')} | Solicitud: {evento.get('hora_solicitud', 'S/D')} | "
                            f"Arribo: {evento.get('hora_arribo', 'S/D')} | Destino: {evento.get('destino', 'S/D')}"
                        )
                    pdf_bytes = build_emergency_pdf_bytes(
                        st.session_state,
                        paciente_sel,
                        mi_empresa,
                        evento,
                        {"nombre": evento.get("profesional", ""), "matricula": evento.get("matricula", "")},
                    )
                    nombre_arch = (
                        f"Emergencia_{paciente_sel.split(' - ')[0].replace(' ', '_')}_"
                        f"{evento.get('fecha_evento', '').replace('/','')}_{idx + 1}.pdf"
                    )
                    c2.download_button(
                        "Descargar PDF",
                        data=pdf_bytes,
                        file_name=nombre_arch,
                        mime="application/pdf",
                        use_container_width=True,
                        key=f"pdf_emerg_{idx}",
                    )
