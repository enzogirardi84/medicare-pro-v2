from __future__ import annotations

from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

from core.alert_toasts import queue_toast
from core.app_logging import log_event
from core.database import guardar_datos
from core.utils import ahora, filtrar_registros_empresa, mostrar_dataframe_con_scroll, seleccionar_limite_registros
from core.view_helpers import bloque_estado_vacio, bloque_mc_grid_tarjetas


HORARIOS_DISPONIBLES = [
    '08:00', '08:30', '09:00', '09:30', '10:00', '10:30',
    '11:00', '11:30', '12:00', '12:30',
    '14:00', '14:30', '15:00', '15:30', '16:00', '16:30',
    '17:00', '17:30', '18:00',
]

PROFESIONALES_POR_DEFECTO = ['Dr. Garcia', 'Dra. Lopez', 'Dr. Martinez', 'Dra. Rodriguez']


def render_turnos_online(mi_empresa, rol):
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Turnos Online</h2>
            <p class="mc-hero-text">Gestion de agenda de turnos: slots disponibles, reservas y administracion de la agenda profesional.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Agenda</span>
                <span class="mc-chip">Slots disponibles</span>
                <span class="mc-chip">Reservas</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ('Agenda', 'Configura los slots disponibles por profesional.'),
            ('Reservar', 'Asigna turnos a pacientes desde el sistema.'),
            ('Administrar', 'Cancela o reprograma turnos existentes.'),
        ]
    )
    st.caption(
        'Los turnos se almacenan localmente. Puedes configurar los horarios disponibles '
        'y asignarlos a pacientes registrados.'
    )

    if 'turnos_online_db' not in st.session_state:
        st.session_state['turnos_online_db'] = []

    turnos_db = st.session_state['turnos_online_db']
    pacientes = filtrar_registros_empresa(
        st.session_state.get('pacientes_db', []), mi_empresa, rol
    )
    lista_pacientes = [p.get('id', p) for p in pacientes] if pacientes else []

    tab_agenda, tab_reservar, tab_admin = st.tabs(['Agenda', 'Reservar turno', 'Administrar'])

    with tab_agenda:
        st.markdown('#### Configurar slots disponibles')
        with st.form('agenda_form', clear_on_submit=True):
            col_a1, col_a2 = st.columns(2)
            profesional = col_a1.selectbox('Profesional', PROFESIONALES_POR_DEFECTO)
            fecha = col_a2.date_input('Fecha', value=ahora().date() + timedelta(days=1))
            horarios = st.multiselect('Horarios disponibles', HORARIOS_DISPONIBLES, default=HORARIOS_DISPONIBLES[:4])

            if st.form_submit_button('Guardar slots', width='stretch', type='primary'):
                if not horarios:
                    st.error('Debes seleccionar al menos un horario.')
                else:
                    for h in horarios:
                        turnos_db.append({
                            'profesional': profesional,
                            'fecha': fecha.strftime('%d/%m/%Y'),
                            'horario': h,
                            'paciente': '',
                            'estado': 'Disponible',
                            'empresa': mi_empresa,
                            'fecha_registro': ahora().isoformat(),
                        })
                    guardar_datos(spinner=True)
                    queue_toast(f'{len(horarios)} slots creados para {profesional} el {fecha.strftime("%d/%m/%Y")}.')
                    log_event('turnos_online_slots', f'{profesional} {fecha}')
                    st.rerun()

    with tab_reservar:
        st.markdown('#### Reservar turno')
        disponibles = [t for t in turnos_db if t.get('estado') == 'Disponible']
        if disponibles:
            with st.form('reservar_form', clear_on_submit=True):
                col_r1, col_r2 = st.columns(2)
                slot_idx = col_r1.selectbox(
                    'Seleccionar slot',
                    range(len(disponibles)),
                    format_func=lambda i: f'{disponibles[i]["profesional"]} - {disponibles[i]["fecha"]} {disponibles[i]["horario"]}',
                )
                if lista_pacientes:
                    paciente_turno = col_r2.selectbox('Paciente', lista_pacientes)
                else:
                    paciente_turno = col_r2.text_input('Nombre del paciente')
                    st.caption('No hay pacientes registrados. Ingresa el nombre manualmente.')

                if st.form_submit_button('Reservar turno', width='stretch', type='primary'):
                    if not paciente_turno:
                        st.error('Debes seleccionar o ingresar un paciente.')
                    else:
                        disponibles[slot_idx]['paciente'] = paciente_turno
                        disponibles[slot_idx]['estado'] = 'Reservado'
                        disponibles[slot_idx]['reservado_por'] = user.get('nombre', 'Sistema')
                        guardar_datos(spinner=True)
                        queue_toast(f'Turno reservado para {paciente_turno}.')
                        log_event('turnos_online_reservar', f'{paciente_turno} - slot {slot_idx}')
                        st.rerun()
        else:
            bloque_estado_vacio(
                'Sin slots disponibles',
                'No hay horarios disponibles para reservar.',
                sugerencia='Crea slots en la pestana Agenda.',
            )

    with tab_admin:
        st.markdown('#### Turnos reservados')
        reservados = [t for t in turnos_db if t.get('estado') == 'Reservado']
        if reservados:
            df_res = pd.DataFrame(reservados)
            df_mostrar = df_res.rename(columns={
                'fecha': 'Fecha', 'horario': 'Horario',
                'profesional': 'Profesional', 'paciente': 'Paciente',
            }).drop(columns=['empresa', 'fecha_registro', 'reservado_por', 'estado'], errors='ignore')

            limite = seleccionar_limite_registros(
                'Turnos a mostrar', len(df_mostrar),
                key='turnos_limite', default=30, opciones=(10, 20, 30, 50, 100),
            )
            mostrar_dataframe_con_scroll(df_mostrar.tail(limite).iloc[::-1], height=350)

            st.markdown('#### Cancelar turno')
            for i, t in enumerate(reservados):
                with st.container(border=True):
                    st.markdown(f'**{t["profesional"]}** - {t["fecha"]} {t["horario"]} - {t["paciente"]}')
                    if st.button('Cancelar turno', key=f'cancelar_turno_{i}', width='stretch'):
                        t['estado'] = 'Cancelado'
                        t['paciente'] = ''
                        guardar_datos(spinner=True)
                        queue_toast('Turno cancelado.')
                        st.rerun()
        else:
            bloque_estado_vacio(
                'Sin reservas',
                'No hay turnos reservados actualmente.',
            )
