from __future__ import annotations

from datetime import datetime

import streamlit as st

from core.app_logging import log_event
from core.utils import ahora
from core.view_helpers import aviso_sin_paciente


RESPUESTAS_PREDEFINIDAS = {
    'horario': 'Nuestro horario de atencion es de lunes a viernes de 8:00 a 18:00 hs. Sabados de 9:00 a 13:00 hs.',
    'turno': 'Podes solicitar un turno desde el modulo Turnos Online o comunicandote al telefono de la clinica.',
    'consulta': 'El costo de la consulta medica domiciliaria es de $15.000. Incluye control de signos vitales y evaluacion clinica.',
    'medicamento': 'Para consultar sobre medicacion, revisa la seccion Indicaciones en el modulo de Recetas. Si necesitas ajustar dosis, contacta a tu medico de cabecera.',
    'emergencia': 'Si es una emergencia, llama al 107 (SAME) o acudi al hospital mas cercano. Este chat no reemplaza la atencion de emergencia.',
    'obra social': 'Trabajamos con la mayoria de las obras sociales y prepagas. Consulta en Recepcion si tu cobertura esta habilitada.',
    'domicilio': 'Realizamos visitas domiciliarias en un radio de 15 km alrededor de la clinica. El costo adicional depende de la distancia.',
    'estudio': 'Los resultados de estudios se entregan en un plazo de 48 a 72 hs habiles. Podes consultarlos en el modulo de Estudios.',
    'factura': 'Emitimos factura electronica para todas las prestaciones. Solicitala en el modulo Factura Electronica.',
    'vacuna': 'El calendario de vacunacion esta disponible en el modulo Vacunacion. Aplicamos todas las vacunas del calendario nacional.',
    'default': 'Gracias por tu consulta. Para mas informacion, contacta a nuestra recepcion al telefono de la clinica o visita cualquiera de los modulos del sistema.',
}


def _buscar_respuesta(mensaje):
    mensaje_lower = mensaje.lower()
    for clave, respuesta in RESPUESTAS_PREDEFINIDAS.items():
        if clave == 'default':
            continue
        if clave in mensaje_lower:
            return respuesta
    return RESPUESTAS_PREDEFINIDAS['default']


def render_chatbot_ia(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Chatbot IA</h2>
            <p class="mc-hero-text">Asistente virtual basado en reglas. Responde preguntas frecuentes sobre horarios, turnos, costos y servicios de la clinica.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Preguntas frecuentes</span>
                <span class="mc-chip">Respuestas automaticas</span>
                <span class="mc-chip">Sin IA externa</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.caption(
        'Este asistente responde con reglas predefinidas. No utiliza inteligencia artificial externa '
        'ni realiza llamadas a APIs. Escribe tu consulta y obtene una respuesta inmediata.'
    )

    if 'chatbot_ia_conversacion' not in st.session_state:
        st.session_state['chatbot_ia_conversacion'] = []

    conversacion = st.session_state['chatbot_ia_conversacion']

    st.markdown('#### Preguntas frecuentes')
    with st.expander('Ver temas disponibles'):
        temas = [
            'horario - Horarios de atencion',
            'turno - Como solicitar un turno',
            'consulta - Costo de consultas',
            'medicamento - Consultas sobre medicacion',
            'emergencia - En caso de emergencia',
            'obra social - Coberturas aceptadas',
            'domicilio - Visitas domiciliarias',
            'estudio - Resultados de estudios',
            'factura - Facturacion electronica',
            'vacuna - Calendario de vacunacion',
        ]
        for t in temas:
            st.markdown(f'- `{t.split(" - ")[0]}`: {t.split(" - ")[1]}')

    st.divider()

    # Mostrar conversacion
    chat_container = st.container(height=350, border=True)
    with chat_container:
        if conversacion:
            for msg in conversacion:
                if msg['rol'] == 'usuario':
                    st.markdown(f'**Tu:** {msg["texto"]}')
                else:
                    st.markdown(f'**Asistente:** {msg["texto"]}')
                    st.caption(msg.get('hora', ''))
        else:
            st.info('Escribe una pregunta en el campo de abajo para comenzar.')

    # Input de mensaje
    with st.form('chat_form', clear_on_submit=True):
        mensaje = st.text_input('Escribe tu consulta:', placeholder='Ej: horario, turno, consulta...')
        if st.form_submit_button('Enviar', width='stretch', type='primary'):
            if mensaje.strip():
                conversacion.append({
                    'rol': 'usuario',
                    'texto': mensaje.strip(),
                    'hora': ahora().strftime('%H:%M'),
                })
                respuesta = _buscar_respuesta(mensaje)
                conversacion.append({
                    'rol': 'asistente',
                    'texto': respuesta,
                    'hora': ahora().strftime('%H:%M'),
                })
                log_event('chatbot_ia_consulta', f'{paciente_sel}: {mensaje.strip()[:50]}')
                st.rerun()

    if conversacion:
        st.divider()
        if st.button('Limpiar conversacion', width='stretch'):
            st.session_state['chatbot_ia_conversacion'] = []
            st.rerun()
