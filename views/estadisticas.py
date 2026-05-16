from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta

import altair as alt
import pandas as pd
import streamlit as st

from core.app_logging import log_event
from core.utils import (
    ahora, es_control_total, filtrar_registros_empresa,
    mapa_detalles_pacientes, parse_fecha_hora,
)
from core.view_helpers import bloque_estado_vacio, bloque_mc_grid_tarjetas
from core.charts import (
    render_metric_card, render_chart_card, chart_barras, chart_linea,
    COLOR_PRIMARY, COLOR_SUCCESS, COLOR_WARNING, COLOR_DANGER, COLOR_INFO,
)


def _contar_por_mes(registros, campo_fecha='fecha', filtro_ano=None):
    conteo = Counter()
    for r in registros:
        try:
            dt = parse_fecha_hora(r.get(campo_fecha, ''))
            if dt and dt != datetime.min:
                if filtro_ano and dt.year != filtro_ano:
                    continue
                mes = dt.strftime('%Y-%m')
                conteo[mes] += 1
        except Exception:
            continue
    return conteo


def _sumar_por_mes(registros, campo_fecha='fecha', campo_valor='monto', filtro_ano=None):
    totales = {}
    for r in registros:
        try:
            dt = parse_fecha_hora(r.get(campo_fecha, ''))
            if dt and dt != datetime.min:
                if filtro_ano and dt.year != filtro_ano:
                    continue
                mes = dt.strftime('%Y-%m')
                totales[mes] = totales.get(mes, 0) + float(r.get(campo_valor, 0) or 0)
        except Exception:
            continue
    return totales


def _chart_barras_mes(df, x_col, y_col, titulo_x='Mes', titulo_y='Cantidad', color=COLOR_PRIMARY):
    if df is None or df.empty:
        return None
    return alt.Chart(df).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X(f'{x_col}:N', title=titulo_x, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y(f'{y_col}:Q', title=titulo_y),
        color=alt.condition(
            alt.datum[y_col] == alt.datum[y_col].max(),
            alt.value(COLOR_DANGER),
            alt.value(color),
        ),
        tooltip=[alt.Tooltip(f'{x_col}:N'), alt.Tooltip(f'{y_col}:Q', format=',')],
    ).configure_axis(labelFontSize=11, titleFontSize=12).configure_view(strokeWidth=0)


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
    bloque_mc_grid_tarjetas([
        ('Pacientes', 'Altas mensuales y total de activos.'),
        ('Facturacion', 'Evolucion de montos facturados en el tiempo.'),
        ('Operaciones', 'Evoluciones registradas y stock critico.'),
    ])
    st.caption('Los graficos usan datos cargados en el sistema. Filtran automaticamente por la empresa seleccionada.')

    with st.spinner('Cargando datos estadisticos...'):
        pacientes = filtrar_registros_empresa(
            st.session_state.get('pacientes_db', []), mi_empresa, rol
        )
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
                    pacientes_dicts.append({'id': p, 'estado': 'Activo'})
        pacientes = pacientes_dicts

        facturacion = filtrar_registros_empresa(
            st.session_state.get('facturacion_db', []), mi_empresa, rol
        )
        evoluciones = filtrar_registros_empresa(
            st.session_state.get('evoluciones_db', []), mi_empresa, rol
        )
        inventario = st.session_state.get('inventario_db', [])
        checkins = filtrar_registros_empresa(
            st.session_state.get('checkin_db', []), mi_empresa, rol
        )

    hoy = ahora().date()
    anos_disponibles = sorted(set(
        dt.year for r in (
            list(pacientes) + list(facturacion) + list(evoluciones)
        )
        for campo in ('fecha', 'fecha_alta')
        if parse_fecha_hora(r.get(campo, '')).year > 2000
    ), reverse=True) or [hoy.year]

    c_ano, _ = st.columns([1, 3])
    filtro_ano = c_ano.selectbox(
        'Filtrar por ano', ['Todos'] + anos_disponibles,
        index=0, key='est_filtro_ano',
    )
    ano_sel = None if filtro_ano == 'Todos' else filtro_ano

    inicio_ano = datetime(ano_sel or hoy.year, 1, 1) if ano_sel else datetime(hoy.year, 1, 1)

    tabs = st.tabs(['Resumen', 'Pacientes', 'Facturacion', 'Evoluciones', 'Stock'])

    # ================================================================
    # TAB 0: RESUMEN
    # ================================================================
    with tabs[0]:
        activos = sum(1 for p in pacientes if p.get('estado', 'Activo') == 'Activo')
        altas = 0
        for p in pacientes:
            fa = p.get('fecha_alta', '')
            if isinstance(fa, str) and fa.strip():
                dt = parse_fecha_hora(fa)
                if dt and dt != datetime.min:
                    try:
                        if not ano_sel or dt.year == ano_sel:
                            altas += 1
                    except TypeError:
                        pass
        total_fact = sum(float(f.get('monto', 0) or 0) for f in facturacion)
        total_evol = len(evoluciones)
        stock_crit = 0
        for item in inventario:
            sm = item.get('stock_minimo')
            if sm is not None and str(sm).strip():
                try:
                    if int(item.get('stock', 0) or 0) <= int(sm):
                        stock_crit += 1
                except (ValueError, TypeError):
                    pass
        visitas = len(checkins)

        kpi_data = [
            (activos, 'Pacientes activos', None, '👤', COLOR_PRIMARY),
            (altas, 'Altas' + (f' {ano_sel}' if ano_sel else ' del ano'), None, '✅', COLOR_SUCCESS),
            (f'${total_fact:,.0f}', 'Facturacion total', None, '💰', COLOR_INFO),
            (total_evol, 'Evoluciones registradas', None, '📝', COLOR_WARNING),
            (visitas, 'Visitas (checkins)', None, '🏥', COLOR_PRIMARY),
            (stock_crit, 'Stock critico', None, '🔴', COLOR_DANGER),
        ]
        cols_kpi = st.columns(3)
        for i, (val, lab, delta, icono, color) in enumerate(kpi_data):
            with cols_kpi[i % 3]:
                render_metric_card(val, lab, delta=delta, icono=icono, color=color)

        st.divider()
        st.markdown('#### Distribucion de pacientes')
        total_pac = len(pacientes)
        if total_pac > 0:
            estados = Counter(p.get('estado', 'Activo') for p in pacientes)
            df_est = pd.DataFrame([
                {'Estado': k, 'Cantidad': v} for k, v in estados.most_common()
            ])
            pie = alt.Chart(df_est).mark_arc(innerRadius=50).encode(
                color=alt.Color('Estado:N', scale=alt.Scale(
                    domain=['Activo', 'De Alta', 'Inactivo'],
                    range=[COLOR_SUCCESS, COLOR_INFO, COLOR_WARNING],
                )),
                theta=alt.Theta('Cantidad:Q'),
                tooltip=['Estado:N', 'Cantidad:Q'],
            ).properties(height=250)
            col_pie, col_est = st.columns([1, 1])
            with col_pie:
                st.altair_chart(pie, use_container_width=True)
            with col_est:
                st.markdown(f'**Total pacientes: {total_pac}**')
                for est, cnt in estados.most_common():
                    pct = cnt / total_pac * 100
                    st.markdown(f'- {est}: **{cnt}** ({pct:.1f}%)')
        else:
            bloque_estado_vacio('Sin pacientes', 'No hay pacientes registrados para esta empresa.')

    # ================================================================
    # TAB 1: PACIENTES
    # ================================================================
    with tabs[1]:
        st.markdown('#### Altas de pacientes por mes')
        conteo_pac = _contar_por_mes(pacientes, 'fecha_alta', filtro_ano=ano_sel)
        if conteo_pac:
            df_pac = pd.DataFrame([
                {'Mes': k, 'Altas': v} for k, v in sorted(conteo_pac.items())
            ])
            render_chart_card(
                'Altas mensuales de pacientes',
                _chart_barras_mes(df_pac, 'Mes', 'Altas', titulo_y='Cantidad', color=COLOR_PRIMARY),
            )
        else:
            bloque_estado_vacio(
                'Sin datos',
                'No hay pacientes registrados con fecha de alta'
                + (f' en {ano_sel}.' if ano_sel else '.'),
            )

    # ================================================================
    # TAB 2: FACTURACION
    # ================================================================
    with tabs[2]:
        st.markdown('#### Facturacion por mes')
        fact_meses = _sumar_por_mes(facturacion, campo_fecha='fecha', campo_valor='monto', filtro_ano=ano_sel)
        if fact_meses:
            df_fact = pd.DataFrame([
                {'Mes': k, 'Monto': v} for k, v in sorted(fact_meses.items())
            ])
            render_chart_card(
                'Evolucion de facturacion mensual',
                chart_linea(df_fact, 'Mes', 'Monto', titulo_x='Mes', titulo_y='Monto ($)'),
            )
            st.success(f'Total facturado: **${sum(fact_meses.values()):,.2f}**')
        else:
            bloque_estado_vacio(
                'Sin datos',
                'No hay facturacion registrada'
                + (f' en {ano_sel}.' if ano_sel else '.'),
            )

        st.divider()
        st.markdown('#### Metodo de pago')
        metodos = Counter(f.get('metodo', 'S/D') for f in facturacion)
        if metodos:
            df_met = pd.DataFrame([
                {'Metodo': k, 'Monto': v} for k, v in metodos.most_common(8)
            ])
            render_chart_card(
                'Distribucion por metodo de pago',
                _chart_barras_mes(df_met, 'Metodo', 'Monto', titulo_x='Metodo', titulo_y='Operaciones', color=COLOR_INFO),
            )
        else:
            st.caption('Sin datos de metodo de pago.')

    # ================================================================
    # TAB 3: EVOLUCIONES
    # ================================================================
    with tabs[3]:
        st.markdown('#### Evoluciones registradas por mes')
        conteo_evol = _contar_por_mes(evoluciones, filtro_ano=ano_sel)
        if conteo_evol:
            df_evol = pd.DataFrame([
                {'Mes': k, 'Evoluciones': v} for k, v in sorted(conteo_evol.items())
            ])
            render_chart_card(
                'Evoluciones clinicas mensuales',
                _chart_barras_mes(df_evol, 'Mes', 'Evoluciones', titulo_y='Cantidad', color=COLOR_WARNING),
            )
        else:
            bloque_estado_vacio(
                'Sin datos',
                'No hay evoluciones registradas'
                + (f' en {ano_sel}.' if ano_sel else '.'),
            )

        st.divider()
        st.markdown('#### Evoluciones por profesional')
        prof_evol = Counter(e.get('firma', e.get('profesional', 'S/D')) for e in evoluciones)
        if prof_evol:
            df_prof = pd.DataFrame([
                {'Profesional': k, 'Evoluciones': v}
                for k, v in prof_evol.most_common(15)
            ])
            render_chart_card(
                'Top profesionales que mas registran evoluciones',
                _chart_barras_mes(df_prof, 'Profesional', 'Evoluciones', titulo_y='Cantidad', color=COLOR_SUCCESS),
            )
        else:
            st.caption('Sin datos de profesional en evoluciones.')

    # ================================================================
    # TAB 4: STOCK
    # ================================================================
    with tabs[4]:
        st.markdown('#### Estado de inventario')
        if inventario:
            total_items = len(inventario)
            total_units = sum(int(i.get('stock', 0) or 0) for i in inventario)
            items_con_minimo = 0
            items_criticos = []
            for item in inventario:
                sm = item.get('stock_minimo')
                if sm is not None and str(sm).strip():
                    items_con_minimo += 1
                    try:
                        if int(item.get('stock', 0) or 0) <= int(sm):
                            items_criticos.append(item)
                    except (ValueError, TypeError):
                        pass

            mc1, mc2, mc3, mc4 = st.columns(4)
            mc1.metric('Items en inventario', total_items)
            mc2.metric('Unidades totales', total_units)
            mc3.metric('Stock critico', len(items_criticos))
            mc4.metric('Items con minimo configurado', items_con_minimo)

            if items_criticos:
                st.divider()
                st.markdown('#### Items con stock critico')
                df_stock = pd.DataFrame([
                    {
                        'Item': item.get('item', ''),
                        'Stock': int(item.get('stock', 0) or 0),
                        'Minimo': int(item.get('stock_minimo', 0) or 0),
                    }
                    for item in items_criticos
                ])
                render_chart_card(
                    'Items por debajo del stock minimo',
                    alt.Chart(df_stock).mark_bar(cornerRadiusEnd=4).encode(
                        x=alt.X('Item:N', title='Item', sort='-y'),
                        y=alt.Y('Stock:Q', title='Stock actual'),
                        color=alt.condition(
                            alt.datum.Stock <= alt.datum.Minimo,
                            alt.value(COLOR_DANGER),
                            alt.value(COLOR_SUCCESS),
                        ),
                        tooltip=[
                            alt.Tooltip('Item:N'),
                            alt.Tooltip('Stock:Q'),
                            alt.Tooltip('Minimo:Q'),
                        ],
                    ).configure_axis(labelFontSize=11, titleFontSize=12).configure_view(strokeWidth=0),
                )
            else:
                if items_con_minimo > 0:
                    st.success('No hay items con stock critico.')
                else:
                    st.info(
                        'Ningun item tiene configurado un stock minimo. '
                        'Para activar las alertas de stock critico, edite cada item en Inventario '
                        'y establezca un valor en "Stock minimo".'
                    )
        else:
            bloque_estado_vacio(
                'Sin datos',
                'No hay inventario cargado en el sistema.',
                sugerencia='Cargue insumos en el modulo Inventario para ver estadisticas de stock.',
            )

    log_event('estadisticas_vista', f'{mi_empresa}')
