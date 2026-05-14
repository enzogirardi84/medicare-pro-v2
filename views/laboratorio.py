from __future__ import annotations

from datetime import datetime

import pandas as pd
import streamlit as st

from core.alert_toasts import queue_toast
from core.app_logging import log_event
from core.database import guardar_datos
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas


def render_laboratorio(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Laboratorio</h2>
            <p class="mc-hero-text">Gestion de resultados de laboratorio: carga de analitos, historial por paciente y marcado de resultados vistos.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Analitos</span>
                <span class="mc-chip">Historial</span>
                <span class="mc-chip">Resultados vistos</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ('Subir resultados', 'Registra analitos, valores, unidad y rango de referencia.'),
            ('Historial', 'Visualiza resultados anteriores del paciente.'),
            ('Marcar como visto', 'Confirma que el resultado fue revisado.'),
        ]
    )
    st.caption(
        'Carga los valores de analitos con su unidad y rango de referencia. '
        'El historial se ordena por fecha descendente.'
    )

    if 'laboratorio_db' not in st.session_state:
        st.session_state['laboratorio_db'] = []

    lab_db = st.session_state['laboratorio_db']
    lab_paciente = [r for r in lab_db if r.get('paciente') == paciente_sel]

    tab_subir, tab_historial, tab_visto = st.tabs(['Subir resultados', 'Historial', 'Marcar como visto'])

    with tab_subir:
        with st.form('lab_form', clear_on_submit=True):
            col1, col2 = st.columns(2)
            fecha = col1.date_input('Fecha del analisis', value=ahora().date())
            analito = col2.text_input('Analito (ej: Hemoglobina, Glucosa)')
            col3, col4, col5 = st.columns(3)
            valor = col3.text_input('Valor obtenido')
            unidad = col4.text_input('Unidad (ej: g/dL, mg/dL)')
            rango = col5.text_input('Rango de referencia')
            observaciones = st.text_area('Observaciones', placeholder='Resultados adicionales o notas del laboratorio...')

            if st.form_submit_button('Guardar resultado', width='stretch', type='primary'):
                if not analito.strip():
                    st.error('El nombre del analito es obligatorio.')
                elif not valor.strip():
                    st.error('El valor del analito es obligatorio.')
                else:
                    registro = {
                        'paciente': paciente_sel,
                        'fecha': fecha.strftime('%d/%m/%Y'),
                        'analito': analito.strip(),
                        'valor': valor.strip(),
                        'unidad': unidad.strip(),
                        'rango_referencia': rango.strip(),
                        'observaciones': observaciones.strip(),
                        'visto': False,
                        'empresa': mi_empresa,
                        'registrado_por': user.get('nombre', 'Sistema'),
                        'fecha_registro': ahora().isoformat(),
                    }
                    lab_db.append(registro)
                    guardar_datos(spinner=True)
                    queue_toast(f'Resultado de {analito.strip()} guardado.')
                    log_event('laboratorio_guardar', f'{analito.strip()} - {paciente_sel}')
                    st.rerun()

    with tab_historial:
        if lab_paciente:
            st.caption(f'Mostrando resultados de **{paciente_sel}**')
            df_lab = pd.DataFrame(lab_paciente)
            df_mostrar = df_lab.rename(columns={
                'fecha': 'Fecha', 'analito': 'Analito', 'valor': 'Valor',
                'unidad': 'Unidad', 'rango_referencia': 'Rango ref.',
                'observaciones': 'Observaciones', 'visto': 'Visto',
            }).drop(columns=['paciente', 'empresa', 'registrado_por', 'fecha_registro'], errors='ignore')
            df_mostrar['Visto'] = df_mostrar['Visto'].apply(lambda x: 'Si' if x else 'No')

            limite = seleccionar_limite_registros(
                'Resultados a mostrar', len(df_mostrar),
                key='lab_limite', default=30, opciones=(10, 20, 30, 50, 100),
            )
            mostrar_dataframe_con_scroll(df_mostrar.tail(limite).iloc[::-1], height=400)
        else:
            bloque_estado_vacio(
                'Sin resultados de laboratorio',
                'No hay analitos registrados para este paciente.',
                sugerencia='Carga los resultados en la pestana Subir resultados.',
            )

    with tab_visto:
        if lab_paciente:
            no_vistos = [r for r in lab_paciente if not r.get('visto')]
            if no_vistos:
                st.caption('Resultados pendientes de revision:')
                for i, r in enumerate(no_vistos):
                    with st.container(border=True):
                        st.markdown(f'**{r["analito"]}** - {r["valor"]} {r["unidad"]} ({r["fecha"]})')
                        if st.checkbox('Marcar como visto', key=f'lab_visto_{i}'):
                            r['visto'] = True
                            guardar_datos(spinner=True)
                            queue_toast(f'{r["analito"]} marcado como visto.')
                            st.rerun()
            else:
                st.success('Todos los resultados fueron revisados.')
        else:
            bloque_estado_vacio(
                'Sin resultados pendientes',
                'No hay resultados de laboratorio para marcar.',
            )
