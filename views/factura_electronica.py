from __future__ import annotations

import pandas as pd
import streamlit as st

from core.alert_toasts import queue_toast
from core.app_logging import log_event
from core.database import guardar_datos
from core.utils import ahora, mostrar_dataframe_con_scroll, seleccionar_limite_registros
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio, bloque_mc_grid_tarjetas


TIPOS_COMPROBANTE = [
    'Factura A', 'Factura B', 'Factura C',
    'Nota de debito', 'Nota de credito', 'Recibo',
    'Presupuesto',
]

ESTADOS_COMPROBANTE = ['Emitido', 'Pendiente', 'Anulado', 'Vencido']


def render_factura_electronica(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Factura Electronica</h2>
            <p class="mc-hero-text">Generacion de comprobantes electronicos. Sin integracion real con AFIP. Los comprobantes quedan registrados en el sistema.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Comprobantes</span>
                <span class="mc-chip">Facturacion</span>
                <span class="mc-chip">Historial</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ('Generar', 'Crea facturas, notas y recibos electronicos.'),
            ('Historial', 'Comprobantes emitidos por paciente.'),
            ('Estado', 'Controla comprobantes emitidos, pendientes y anulados.'),
        ]
    )
    st.caption(
        'Los comprobantes se almacenan localmente. No hay validacion ni envio a AFIP.'
    )

    if 'factura_electronica_db' not in st.session_state:
        st.session_state['factura_electronica_db'] = []

    fe_db = st.session_state['factura_electronica_db']
    fe_paciente = [f for f in fe_db if f.get('paciente') == paciente_sel]

    tab_generar, tab_historial = st.tabs(['Generar comprobante', 'Historial'])

    with tab_generar:
        with st.form('fe_form', clear_on_submit=True):
            col1, col2 = st.columns(2)
            tipo = col1.selectbox('Tipo de comprobante', TIPOS_COMPROBANTE)
            fecha_emision = col2.date_input('Fecha de emision', value=ahora().date())
            col3, col4 = st.columns(2)
            monto = col3.number_input('Monto ($)', min_value=0.0, step=100.0, value=0.0)
            estado = col4.selectbox('Estado', ESTADOS_COMPROBANTE, index=0)
            concepto = st.text_area('Concepto / Detalle', placeholder='Detalle del comprobante...')

            if st.form_submit_button('Emitir comprobante', width='stretch', type='primary'):
                if monto <= 0:
                    st.error('El monto debe ser mayor a $0.')
                elif not concepto.strip():
                    st.error('El concepto es obligatorio.')
                else:
                    registro = {
                        'paciente': paciente_sel,
                        'tipo_comprobante': tipo,
                        'monto': monto,
                        'fecha_emision': fecha_emision.strftime('%d/%m/%Y'),
                        'estado': estado,
                        'concepto': concepto.strip(),
                        'empresa': mi_empresa,
                        'operador': user.get('nombre', 'Sistema'),
                        'fecha_registro': ahora().isoformat(),
                    }
                    fe_db.append(registro)
                    guardar_datos(spinner=True)
                    queue_toast(f'{tipo} emitido por ${monto:,.2f}.')
                    log_event('factura_electronica_emitir', f'{tipo} ${monto} - {paciente_sel}')
                    st.rerun()

    with tab_historial:
        if fe_paciente:
            st.caption(f'Comprobantes de **{paciente_sel}**')
            df_fe = pd.DataFrame(fe_paciente)
            df_mostrar = df_fe.rename(columns={
                'fecha_emision': 'Fecha', 'tipo_comprobante': 'Tipo',
                'monto': 'Monto ($)', 'estado': 'Estado', 'concepto': 'Concepto',
            }).drop(columns=['paciente', 'empresa', 'operador', 'fecha_registro'], errors='ignore')

            limite = seleccionar_limite_registros(
                'Comprobantes a mostrar', len(df_mostrar),
                key='fe_limite', default=30, opciones=(10, 20, 30, 50, 100),
            )
            mostrar_dataframe_con_scroll(df_mostrar.tail(limite).iloc[::-1], height=400)

            total_emitido = sum(f.get('monto', 0) for f in fe_paciente if f.get('estado') == 'Emitido')
            total_pendiente = sum(f.get('monto', 0) for f in fe_paciente if f.get('estado') == 'Pendiente')
            col_t1, col_t2 = st.columns(2)
            col_t1.metric('Total emitido', f'${total_emitido:,.2f}')
            col_t2.metric('Total pendiente', f'${total_pendiente:,.2f}')
        else:
            bloque_estado_vacio(
                'Sin comprobantes',
                'No hay comprobantes electronicos para este paciente.',
                sugerencia='Genera un comprobante en la pestana Generar comprobante.',
            )
