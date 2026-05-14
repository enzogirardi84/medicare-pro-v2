from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from core.app_logging import log_event
from core.utils import ahora, es_control_total, filtrar_registros_empresa, mapa_detalles_pacientes, parse_fecha_hora
from core.view_helpers import bloque_estado_vacio, bloque_mc_grid_tarjetas


def _contar_por_mes(registros, campo_fecha='fecha'):
    conteo = Counter()
    for r in registros:
        try:
            dt = parse_fecha_hora(r.get(campo_fecha, ''))
            if dt and dt != datetime.min:
                mes = dt.strftime('%Y-%m')
                conteo[mes] += 1
        except Exception:
            continue
    return conteo


def render_estadisticas(mi_empresa, rol):
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Estadisticas y graficos</h2>
            <p class="mc-hero-text">Panel visual con metricas clave de la clinica: pacientes, facturacion, evoluciones y stock.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Pacientes por mes</span>
                <span class="mc-chip">Facturacion</span>
                <span class="mc-chip">Stock</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas(
        [
            ('Pacientes', 'Altas mensuales y total de activos.'),
            ('Facturacion', 'Evolucion de montos facturados en el tiempo.'),
            ('Operaciones', 'Evoluciones registradas y stock critico.'),
        ]
    )
    st.caption(
        'Los graficos usan datos cargados en el sistema. Filtran automaticamente por la empresa seleccionada.'
    )

    pacientes = filtrar_registros_empresa(
        st.session_state.get('pacientes_db', []), mi_empresa, rol
    )
    # pacientes pueden ser strings (IDs) - convertir a dicts con detalles
    _detalles = mapa_detalles_pacientes(st.session_state)
    pacientes_dicts = []
    for p in pacientes:
        if isinstance(p, dict):
            pacientes_dicts.append(p)
        elif isinstance(p, str):
            if p in _detalles:
                d = dict(_detalles[p])
                d['id'] = p
                pacientes_dicts.append(d)
            else:
                # String ID sin detalles: crear un dict basico
                pacientes_dicts.append({'id': p, 'estado': 'Activo'})
    pacientes = pacientes_dicts
    facturacion = filtrar_registros_empresa(
        st.session_state.get('facturacion_db', []), mi_empresa, rol
    )
    evoluciones = filtrar_registros_empresa(
        st.session_state.get('evoluciones_db', []), mi_empresa, rol
    )
    inventario = st.session_state.get('inventario_db', [])

    hoy = ahora().date()
    inicio_ano = datetime(hoy.year, 1, 1)

    # Metricas principales
    col_m1, col_m2, col_m3, col_m4 = st.columns(4)
    col_m1.metric('Pacientes activos', sum(1 for p in pacientes if p.get('estado', 'Activo') == 'Activo'))
    col_m2.metric('Altas del ano', sum(1 for p in pacientes if parse_fecha_hora(p.get('fecha_alta', '')).date() >= inicio_ano if parse_fecha_hora(p.get('fecha_alta', '')) != datetime.min))
    col_m3.metric('Facturacion total', f"${sum(float(f.get('monto', 0) or 0) for f in facturacion):,.2f}")
    col_m4.metric('Stock critico', sum(1 for item in inventario if int(item.get('stock', 0) or 0) <= int(item.get('stock_minimo', 0) or 0)) if inventario else 0)

    st.divider()

    # Grafico: Pacientes por mes
    st.markdown('#### Pacientes por mes')
    conteo_pac = _contar_por_mes(pacientes, 'fecha_alta')
    if conteo_pac:
        df_pac = pd.DataFrame([
            {'Mes': k, 'Pacientes': v} for k, v in sorted(conteo_pac.items())
        ])
        chart_pac = alt.Chart(df_pac).mark_bar(cornerRadiusEnd=4).encode(
            x=alt.X('Mes:N', title='Mes'),
            y=alt.Y('Pacientes:Q', title='Cantidad'),
            tooltip=[alt.Tooltip('Mes:N'), alt.Tooltip('Pacientes:Q')],
        ).configure_axis(labelFontSize=12, titleFontSize=13).configure_view(strokeWidth=0)
        st.altair_chart(chart_pac, width='stretch')
    else:
        bloque_estado_vacio('Sin datos', 'No hay pacientes registrados con fecha de alta.')

    st.divider()

    # Grafico: Facturacion por mes
    st.markdown('#### Facturacion por mes')
    fact_meses = {}
    for f in facturacion:
        try:
            dt = parse_fecha_hora(f.get('fecha', ''))
            if dt and dt != datetime.min:
                mes = dt.strftime('%Y-%m')
                fact_meses[mes] = fact_meses.get(mes, 0) + float(f.get('monto', 0) or 0)
        except Exception:
            continue
    if fact_meses:
        df_fact = pd.DataFrame([
            {'Mes': k, 'Monto': v} for k, v in sorted(fact_meses.items())
        ])
        chart_fact = alt.Chart(df_fact).mark_line(point=True, strokeWidth=2).encode(
            x=alt.X('Mes:N', title='Mes'),
            y=alt.Y('Monto:Q', title='Monto ($)'),
            tooltip=[alt.Tooltip('Mes:N'), alt.Tooltip('Monto:Q', format='$,.2f')],
        ).configure_axis(labelFontSize=12, titleFontSize=13).configure_view(strokeWidth=0)
        st.altair_chart(chart_fact, width='stretch')
    else:
        bloque_estado_vacio('Sin datos', 'No hay facturacion registrada.')

    st.divider()

    # Grafico: Evoluciones por mes
    st.markdown('#### Evoluciones registradas por mes')
    conteo_evol = _contar_por_mes(evoluciones)
    if conteo_evol:
        df_evol = pd.DataFrame([
            {'Mes': k, 'Evoluciones': v} for k, v in sorted(conteo_evol.items())
        ])
        chart_evol = alt.Chart(df_evol).mark_area(opacity=0.5, line=True).encode(
            x=alt.X('Mes:N', title='Mes'),
            y=alt.Y('Evoluciones:Q', title='Cantidad'),
            tooltip=[alt.Tooltip('Mes:N'), alt.Tooltip('Evoluciones:Q')],
        ).configure_axis(labelFontSize=12, titleFontSize=13).configure_view(strokeWidth=0)
        st.altair_chart(chart_evol, width='stretch')
    else:
        bloque_estado_vacio('Sin datos', 'No hay evoluciones registradas.')

    st.divider()

    # Stock critico
    st.markdown('#### Stock critico en inventario')
    if inventario:
        items_criticos = [
            item for item in inventario
            if int(item.get('stock', 0) or 0) <= int(item.get('stock_minimo', 0) or 0)
        ]
        if items_criticos:
            df_stock = pd.DataFrame([
                {'Item': item.get('item', ''), 'Stock': int(item.get('stock', 0) or 0),
                 'Minimo': int(item.get('stock_minimo', 0) or 0)}
                for item in items_criticos
            ])
            chart_stock = alt.Chart(df_stock).mark_bar(cornerRadiusEnd=4).encode(
                x=alt.X('Item:N', title='Item', sort='-y'),
                y=alt.Y('Stock:Q', title='Stock actual'),
                color=alt.condition(
                    alt.datum.Stock <= alt.datum.Minimo,
                    alt.value('#ef4444'),
                    alt.value('#10b981'),
                ),
                tooltip=[alt.Tooltip('Item:N'), alt.Tooltip('Stock:Q'), alt.Tooltip('Minimo:Q')],
            ).configure_axis(labelFontSize=12, titleFontSize=13).configure_view(strokeWidth=0)
            st.altair_chart(chart_stock, width='stretch')
        else:
            st.success('No hay items con stock critico.')
    else:
        bloque_estado_vacio('Sin datos', 'No hay inventario cargado en el sistema.')

    log_event('estadisticas_vista', f'{mi_empresa}')
