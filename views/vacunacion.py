from __future__ import annotations

from datetime import timedelta

import pandas as pd
import streamlit as st

from core.alert_toasts import queue_toast
from core.app_logging import log_event
from core.database import guardar_datos
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas


VACUNAS_CALENDARIO = [
    'BCG', 'Hepatitis B', 'Pentavalente', 'IPV (Salk)',
    'Neumococo conjugada', 'Rotavirus', 'Triple viral (SPR)',
    'Varicela', 'Fiebre amarilla', 'Antigripal',
    'COVID-19', 'Doble adultos (dT)', 'Triple bacteriana acelular (dTpa)',
    'VPH', 'Hepatitis A', 'Meningococo',
]


def render_vacunacion(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Vacunacion</h2>
            <p class="mc-hero-text">Calendario de vacunas, registro de dosis aplicadas y control de proximas dosis del paciente.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Calendario</span>
                <span class="mc-chip">Dosis aplicadas</span>
                <span class="mc-chip">Proximas dosis</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ('Registrar dosis', 'Carga vacuna aplicada con lote y aplicador.'),
            ('Historial', 'Visualiza el esquema de vacunacion del paciente.'),
            ('Proximas dosis', 'Recordatorio de dosis siguientes segun calendario.'),
        ]
    )
    st.caption(
        'Registra cada dosis aplicada con numero de lote y profesional que aplica. '
        'El sistema calcula automaticamente las proximas dosis segun el calendario.'
    )

    if 'vacunacion_db' not in st.session_state:
        st.session_state['vacunacion_db'] = []

    vac_db = st.session_state['vacunacion_db']
    vac_paciente = [r for r in vac_db if r.get('paciente') == paciente_sel]

    tab_registrar, tab_historial, tab_proximas = st.tabs(['Registrar dosis', 'Historial', 'Proximas dosis'])

    with tab_registrar:
        with st.form('vac_form', clear_on_submit=True):
            col1, col2 = st.columns(2)
            vacuna = col1.selectbox('Vacuna', VACUNAS_CALENDARIO)
            dosis = col2.selectbox('Dosis', ['Unica', '1ra dosis', '2da dosis', '3ra dosis', 'Refuerzo 1', 'Refuerzo 2'])
            col3, col4 = st.columns(2)
            fecha_aplicacion = col3.date_input('Fecha de aplicacion', value=ahora().date())
            lote = col4.text_input('Numero de lote')
            aplicador = st.text_input('Aplicador / Profesional', value=user.get('nombre', ''))

            if st.form_submit_button('Guardar dosis', width='stretch', type='primary'):
                if not lote.strip():
                    st.error('El numero de lote es obligatorio.')
                elif not aplicador.strip():
                    st.error('El nombre del aplicador es obligatorio.')
                else:
                    registro = {
                        'paciente': paciente_sel,
                        'vacuna': vacuna,
                        'dosis': dosis,
                        'fecha_aplicacion': fecha_aplicacion.strftime('%d/%m/%Y'),
                        'lote': lote.strip(),
                        'aplicador': aplicador.strip(),
                        'empresa': mi_empresa,
                        'fecha_registro': ahora().isoformat(),
                    }
                    vac_db.append(registro)
                    guardar_datos(spinner=True)
                    queue_toast(f'{vacuna} - {dosis} registrada.')
                    log_event('vacunacion_guardar', f'{vacuna} {dosis} - {paciente_sel}')
                    st.rerun()

    with tab_historial:
        if vac_paciente:
            st.caption(f'Esquema de vacunacion de **{paciente_sel}**')
            df_vac = pd.DataFrame(vac_paciente)
            df_mostrar = df_vac.rename(columns={
                'fecha_aplicacion': 'Fecha', 'vacuna': 'Vacuna',
                'dosis': 'Dosis', 'lote': 'Lote', 'aplicador': 'Aplicador',
            }).drop(columns=['paciente', 'empresa', 'fecha_registro'], errors='ignore')

            limite = seleccionar_limite_registros(
                'Registros a mostrar', len(df_mostrar),
                key='vac_limite', default=30, opciones=(10, 20, 30, 50, 100),
            )
            mostrar_dataframe_con_scroll(df_mostrar.tail(limite).iloc[::-1], height=400)
        else:
            bloque_estado_vacio(
                'Sin registro de vacunas',
                'No se encontraron dosis aplicadas para este paciente.',
                sugerencia='Registra la primera dosis en la pestana Registrar dosis.',
            )

    with tab_proximas:
        if vac_paciente:
            st.caption('Proximas dosis estimadas segun calendario:')
            ultimas = {}
            for r in vac_paciente:
                vac = r['vacuna']
                if vac not in ultimas or r['fecha_aplicacion'] > ultimas[vac]['fecha_aplicacion']:
                    ultimas[vac] = r

            if ultimas:
                for vac, reg in ultimas.items():
                    try:
                        fecha_ult = datetime.strptime(reg['fecha_aplicacion'], '%d/%m/%Y')
                    except Exception:
                        continue
                    prox = fecha_ult + timedelta(days=365)
                    with st.container(border=True):
                        st.markdown(f'**{vac}** - Ultima: {reg["fecha_aplicacion"]} ({reg["dosis"]})')
                        st.caption(f'Proxima dosis estimada: {prox.strftime("%d/%m/%Y")}')
            else:
                st.info('No hay datos suficientes para estimar proximas dosis.')
        else:
            bloque_estado_vacio(
                'Sin datos de vacunacion',
                'No hay registros previos para estimar proximas dosis.',
                sugerencia='Registra las vacunas aplicadas para recibir recordatorios.',
            )
