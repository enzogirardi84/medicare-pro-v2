"""Turnos Online - Gestion de agenda con profesional manual."""
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
    '11:00', '11:30', '12:00',
    '14:00', '14:30', '15:00', '15:30', '16:00', '16:30',
    '17:00', '17:30', '18:00',
]


def render_turnos_online(mi_empresa, rol):
    st.markdown("""
        <div class="mc-hero">
            <h2 class="mc-hero-title">Turnos Online</h2>
            <p class="mc-hero-text">Crea slots, asigna turnos a pacientes y administra la agenda con profesionales cargados manualmente.</p>
        </div>
    """, unsafe_allow_html=True)

    if 'turnos_online_db' not in st.session_state:
        st.session_state['turnos_online_db'] = []
    turnos_db = st.session_state['turnos_online_db']

    pacientes = filtrar_registros_empresa(
        st.session_state.get('pacientes_db', []), mi_empresa, rol
    )
    lista_pacientes = []
    for p in (pacientes or []):
        if isinstance(p, dict):
            lista_pacientes.append(p.get('id', str(p)))
        elif isinstance(p, str):
            lista_pacientes.append(p)

    tabs = st.tabs(['Crear slots', 'Reservar turno', 'Administrar'])

    # ============ TAB: CREAR SLOTS ============
    with tabs[0]:
        with st.form('agenda_form', clear_on_submit=True):
            st.markdown('##### Nuevo slot')
            c1, c2 = st.columns(2)
            profesional = c1.text_input('Profesional *', placeholder='Ej: Dr. Juan Perez')
            fecha = c2.date_input('Fecha', value=ahora().date() + timedelta(days=1))
            horarios = st.multiselect('Horarios disponibles *', HORARIOS_DISPONIBLES, default=HORARIOS_DISPONIBLES[:4])

            if st.form_submit_button('Guardar slots', width='stretch', type='primary'):
                if not profesional.strip():
                    st.error('El nombre del profesional es obligatorio.')
                elif not horarios:
                    st.error('Debes seleccionar al menos un horario.')
                else:
                    for h in horarios:
                        turnos_db.append({
                            'profesional': profesional.strip(),
                            'fecha': fecha.strftime('%d/%m/%Y'),
                            'horario': h,
                            'paciente': '',
                            'estado': 'Disponible',
                            'empresa': mi_empresa,
                            'fecha_registro': ahora().isoformat(),
                        })
                    guardar_datos(spinner=True)
                    queue_toast(f'{len(horarios)} slots creados para {profesional.strip()} el {fecha.strftime("%d/%m/%Y")}.')
                    log_event('turnos_slots', f'{profesional.strip()} {fecha}')
                    st.rerun()

    # ============ TAB: RESERVAR ============
    with tabs[1]:
        disponibles = [t for t in turnos_db if t.get('estado') == 'Disponible']
        if not disponibles:
            bloque_estado_vacio(
                'Sin slots disponibles',
                'No hay horarios disponibles para reservar.',
                sugerencia='Crea slots en la pestana Crear slots.',
            )
        else:
            st.markdown(f'##### {len(disponibles)} slots disponibles')
            with st.form('reservar_form', clear_on_submit=True):
                # Mostrar slots en un selectbox con info clara
                slot_opciones = [
                    f'{s["profesional"]} - {s["fecha"]} {s["horario"]}'
                    for s in disponibles
                ]
                slot_sel = st.selectbox('Seleccionar turno', slot_opciones)
                slot_idx = slot_opciones.index(slot_sel)

                st.caption(f'Profesional: {disponibles[slot_idx]["profesional"]}')
                st.caption(f'Fecha: {disponibles[slot_idx]["fecha"]} - {disponibles[slot_idx]["horario"]} hs')

                if lista_pacientes:
                    paciente_turno = st.selectbox('Paciente', [''] + lista_pacientes)
                    if not paciente_turno:
                        paciente_turno = st.text_input('O ingresa el nombre manualmente', placeholder='Nombre del paciente')
                else:
                    paciente_turno = st.text_input('Paciente *', placeholder='Nombre del paciente')

                if st.form_submit_button('Reservar turno', width='stretch', type='primary'):
                    if not paciente_turno or (isinstance(paciente_turno, str) and not paciente_turno.strip()):
                        st.error('Debes ingresar un paciente.')
                    else:
                        disponibles[slot_idx]['paciente'] = paciente_turno.strip() if isinstance(paciente_turno, str) else paciente_turno
                        disponibles[slot_idx]['estado'] = 'Reservado'
                        disponibles[slot_idx]['reservado_por'] = st.session_state.get('u_actual', {}).get('nombre', 'Sistema')
                        guardar_datos(spinner=True)
                        queue_toast(f'Turno reservado para {paciente_turno}.')
                        log_event('turnos_reservar', f'{paciente_turno}')
                        st.rerun()

    # ============ TAB: ADMINISTRAR ============
    with tabs[2]:
        reservados = [t for t in turnos_db if t.get('estado') == 'Reservado']
        cancelados = [t for t in turnos_db if t.get('estado') == 'Cancelado']

        if not reservados and not cancelados:
            bloque_estado_vacio(
                'Sin movimientos',
                'No hay turnos reservados ni cancelados.',
            )
        else:
            if reservados:
                st.markdown(f'##### Turnos reservados ({len(reservados)})')
                for i, t in enumerate(reservados):
                    with st.container(border=True):
                        cols = st.columns([2, 1, 1, 1])
                        cols[0].markdown(f'**{t["profesional"]}**')
                        cols[1].markdown(f'{t["fecha"]}')
                        cols[2].markdown(f'{t["horario"]} hs')
                        cols[3].markdown(f'{t["paciente"]}')
                        if st.button('Cancelar', key=f'can_{i}', width='content'):
                            t['estado'] = 'Cancelado'
                            t['paciente'] = ''
                            guardar_datos(spinner=True)
                            queue_toast('Turno cancelado.')
                            st.rerun()

            if cancelados:
                with st.expander(f'Historial de cancelaciones ({len(cancelados)})', expanded=False):
                    df_can = pd.DataFrame(cancelados)
                    df_mostrar = df_can.rename(columns={
                        'fecha': 'Fecha', 'horario': 'Horario',
                        'profesional': 'Profesional',
                    }).drop(columns=['empresa', 'fecha_registro', 'reservado_por', 'paciente', 'estado'], errors='ignore')
                    mostrar_dataframe_con_scroll(df_mostrar.tail(20).iloc[::-1], height=200)

            # Resumen
            with st.expander('Ver todos los slots', expanded=False):
                if turnos_db:
                    df_all = pd.DataFrame(turnos_db)
                    df_all = df_all.rename(columns={
                        'fecha': 'Fecha', 'horario': 'Horario',
                        'profesional': 'Profesional', 'paciente': 'Paciente',
                        'estado': 'Estado',
                    }).drop(columns=['empresa', 'fecha_registro', 'reservado_por'], errors='ignore')
                    mostrar_dataframe_con_scroll(df_all.tail(50).iloc[::-1], height=300)
