from __future__ import annotations

import pandas as pd
import streamlit as st

from core.utils import filtrar_registros_empresa, mapa_detalles_pacientes, mostrar_dataframe_con_scroll
from core.view_helpers import aviso_sin_paciente, bloque_estado_vacio


def render_portal_paciente(paciente_sel, mi_empresa, user, rol):
    if not paciente_sel:
        aviso_sin_paciente()
        return

    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Portal del Paciente</h2>
            <p class="mc-hero-text">Vista resumen para mostrar al paciente: evoluciones, indicaciones, estudios y datos del legajo. Modo solo lectura.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Lectura</span>
                <span class="mc-chip">Resumen clinico</span>
                <span class="mc-chip">Sin edicion</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.info(
        'Esta es una vista de solo lectura para compartir con el paciente. '
        'No se pueden realizar modificaciones desde este modulo.'
    )

    detalles = mapa_detalles_pacientes(st.session_state).get(paciente_sel, {})
    if detalles:
        st.markdown('#### Datos del paciente')
        col_d1, col_d2, col_d3 = st.columns(3)
        col_d1.markdown(f'**Nombre:** {detalles.get("nombre", "S/D")}')
        col_d2.markdown(f'**DNI:** {detalles.get("dni", "S/D")}')
        col_d3.markdown(f'**Obra social:** {detalles.get("obra_social", "S/D")}')
        col_d4, col_d5, col_d6 = st.columns(3)
        col_d4.markdown(f'**Edad:** {detalles.get("edad", "S/D")}')
        col_d5.markdown(f'**Direccion:** {detalles.get("direccion", "S/D")}')
        col_d6.markdown(f'**Telefono:** {detalles.get("telefono", "S/D")}')
    else:
        st.caption('No se encontraron datos adicionales del paciente.')
    st.divider()

    tab_evoluciones, tab_indicaciones, tab_estudios = st.tabs(
        ['Evoluciones', 'Indicaciones', 'Estudios']
    )

    with tab_evoluciones:
        st.markdown('#### Evoluciones clinicas')
        evoluciones = [
            e for e in st.session_state.get('evoluciones_db', [])
            if e.get('paciente') == paciente_sel
        ]
        if evoluciones:
            for e in reversed(evoluciones[-20:]):
                with st.container(border=True):
                    st.markdown(f'**{e.get("fecha", "S/F")}** - {e.get("profesional", "S/D")}')
                    st.caption(e.get('texto', '')[:300])
        else:
            bloque_estado_vacio(
                'Sin evoluciones',
                'No hay evoluciones registradas para este paciente.',
            )

    with tab_indicaciones:
        st.markdown('#### Indicaciones medicas')
        indicaciones = [
            ind for ind in st.session_state.get('indicaciones_db', [])
            if ind.get('paciente') == paciente_sel
            and str(ind.get('estado_receta', 'Activa')).strip().lower() == 'activa'
        ]
        if indicaciones:
            for ind in indicaciones:
                with st.container(border=True):
                    st.markdown(
                        f'**{ind.get("medicamento", ind.get("descripcion", "S/D"))}**'
                    )
                    st.caption(
                        f'{ind.get("dosis", "")} {ind.get("frecuencia", "")} - '
                        f'Via: {ind.get("via", "S/D")}'
                    )
        else:
            bloque_estado_vacio(
                'Sin indicaciones activas',
                'No hay indicaciones activas para mostrar.',
            )

    with tab_estudios:
        st.markdown('#### Estudios realizados')
        estudios = [
            est for est in st.session_state.get('estudios_db', [])
            if est.get('paciente') == paciente_sel
        ]
        if estudios:
            df_est = pd.DataFrame(estudios)
            cols_mostrar = [c for c in ['fecha', 'estudio', 'resultado'] if c in df_est.columns]
            if cols_mostrar:
                mostrar_dataframe_con_scroll(
                    df_est[cols_mostrar].tail(30).iloc[::-1], height=350
                )
        else:
            bloque_estado_vacio(
                'Sin estudios',
                'No hay estudios registrados para este paciente.',
            )
