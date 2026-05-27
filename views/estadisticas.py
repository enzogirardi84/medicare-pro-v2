from __future__ import annotations

from collections import Counter
from datetime import datetime

import altair as alt
import pandas as pd
import streamlit as st

from core.app_logging import log_event
from core.utils import (
    ahora,
    es_control_total,
    filtrar_registros_empresa,
    mapa_detalles_pacientes,
    parse_fecha_hora,
)
from core.view_helpers import bloque_mc_grid_tarjetas
from core.charts import (
    render_metric_card,
    render_chart_card,
    chart_linea,
    COLOR_PRIMARY,
    COLOR_SUCCESS,
    COLOR_WARNING,
    COLOR_DANGER,
    COLOR_INFO,
)

import io
import csv


def _estado_vacio_stats(titulo: str, mensaje: str, sugerencia: str | None = None) -> None:
    """Estado vacío nativo, sin HTML crudo."""
    st.info(f"{titulo}: {mensaje}")
    if sugerencia:
        st.caption(sugerencia)


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


def _parse_stock(v):
    try:
        s = str(v or '0').replace(',', '').strip()
        return int(float(s)) if s else 0
    except (ValueError, TypeError):
        return 0


def _parse_monto(v):
    try:
        if v is None:
            return 0.0
        s = str(v).replace(',', '').replace('$', '').strip()
        return float(s) if s else 0.0
    except (ValueError, TypeError):
        return 0.0


def _descargar_csv(data, filename):
    buf = io.StringIO()
    writer = csv.writer(buf)
    if data:
        writer.writerow(data[0].keys())
        for row in data:
            writer.writerow(row.values())
    st.download_button('Descargar CSV', data=buf.getvalue(), file_name=filename, mime='text/csv')


def _chart_barras_mes(df, x_col, y_col, titulo_x='Mes', titulo_y='Cantidad', color=COLOR_PRIMARY):
    if df is None or df.empty:
        return None
    y_max = df[y_col].max()
    if pd.isna(y_max):
        y_max = 0
    df = df.copy()
    df["_is_max"] = df[y_col] == y_max
    return alt.Chart(df).mark_bar(cornerRadiusEnd=4).encode(
        x=alt.X(f'{x_col}:N', title=titulo_x, axis=alt.Axis(labelAngle=-45)),
        y=alt.Y(f'{y_col}:Q', title=titulo_y),
        color=alt.condition(
            "_is_max",
            alt.value(COLOR_DANGER),
            alt.value(color),
        ),
        tooltip=[alt.Tooltip(f'{x_col}:N'), alt.Tooltip(f'{y_col}:Q', format=',')],
    ).configure_axis(labelFontSize=11, titleFontSize=12).configure_view(strokeWidth=0)


def render_estadisticas(mi_empresa, rol):
    st.markdown(
        """
        <div class="mc-hero">
            <h2 class="mc-hero-title">Estadísticas y gráficos</h2>
            <p class="mc-hero-text">Panel visual con métricas clave de la clínica: pacientes, facturación, evoluciones y stock.</p>
            <div class="mc-chip-row">
                <span class="mc-chip">Pacientes por mes</span>
                <span class="mc-chip">Facturación</span>
                <span class="mc-chip">Stock</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
    bloque_mc_grid_tarjetas([
        ('Pacientes', 'Altas mensuales y total de activos.'),
        ('Facturación', 'Evolución de montos facturados en el tiempo.'),
        ('Operaciones', 'Evoluciones registradas y stock crítico.'),
    ])
    st.caption('Los gráficos usan datos cargados en el sistema. Filtran automáticamente por la empresa seleccionada.')

    with st.spinner('Cargando datos estadísticos...'):
        pacientes = filtrar_registros_empresa(
            st.session_state.get('pacientes_db', []), mi_empresa, rol
        )
        detalles = mapa_detalles_pacientes(st.session_state)
        pacientes_dicts = []
        for p in pacientes:
            if isinstance(p, dict):
                pacientes_dicts.append(p)
            elif isinstance(p, str):
                if p in detalles:
                    d = dict(detalles[p])
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
        inventario = filtrar_registros_empresa(
            st.session_state.get('inventario_db', []), mi_empresa, rol
        )
        checkins = filtrar_registros_empresa(
            st.session_state.get('checkin_db', []), mi_empresa, rol
        )

    hoy = ahora().date()
    anos = set()
    for r in list(pacientes) + list(facturacion) + list(evoluciones):
        for campo in ('fecha', 'fecha_alta'):
            d = parse_fecha_hora(r.get(campo, ''))
            if d and d.year > 2000:
                anos.add(d.year)
    anos_disponibles = sorted(anos, reverse=True) or [hoy.year]

    c_ano, _ = st.columns([1, 3])
    filtro_ano = c_ano.selectbox(
        'Filtrar por año', ['Todos'] + anos_disponibles,
        index=0, key='est_filtro_ano',
    )
    ano_sel = None if filtro_ano == 'Todos' else filtro_ano

    tabs = st.tabs(['Resumen', 'Pacientes', 'Facturación', 'Evoluciones', 'Stock'])

    with tabs[0]:
        activos = sum(1 for p in pacientes if p.get('estado', 'Activo') == 'Activo')
        altas = 0
        for p in pacientes:
            fa = p.get('fecha_alta', '')
            if isinstance(fa, str) and fa.strip():
                dt = parse_fecha_hora(fa)
                if dt and dt != datetime.min:
                    if not ano_sel or dt.year == ano_sel:
                        altas += 1

        total_fact = sum(_parse_monto(f.get('monto')) for f in facturacion)
        total_evol = len(evoluciones)
        stock_crit = 0
        for item in inventario:
            sm = item.get('stock_minimo')
            if sm is not None and str(sm).strip():
                if _parse_stock(item.get('stock')) <= _parse_stock(sm):
                    stock_crit += 1
        visitas = len(checkins)

        kpi_data = [
            (activos, 'Pacientes activos', None, '👤', COLOR_PRIMARY),
            (altas, 'Altas' + (f' {ano_sel}' if ano_sel else ' del año'), None, '✅', COLOR_SUCCESS),
            (f'${total_fact:,.0f}', 'Facturación total', None, '💰', COLOR_INFO),
            (total_evol, 'Evoluciones registradas', None, '📝', COLOR_WARNING),
            (visitas, 'Visitas (check-ins)', None, '🏥', COLOR_PRIMARY),
            (stock_crit, 'Stock crítico', None, '🔴', COLOR_DANGER),
        ]
        cols_kpi = st.columns(3)
        for i, (val, lab, delta, icono, color) in enumerate(kpi_data):
            with cols_kpi[i % 3]:
                render_metric_card(val, lab, delta=delta, icono=icono, color=color)

        st.divider()
        st.markdown('#### Distribución de pacientes')
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
                st.altair_chart(pie, width='stretch')
            with col_est:
                st.markdown(f'**Total pacientes: {total_pac}**')
                for est, cnt in estados.most_common():
                    pct = cnt / total_pac * 100
                    st.markdown(f'- {est}: **{cnt}** ({pct:.1f}%)')
        else:
            _estado_vacio_stats('Sin pacientes', 'No hay pacientes registrados para esta empresa.')

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
            _descargar_csv([{'Mes': k, 'Altas': v} for k, v in sorted(conteo_pac.items())], 'altas_pacientes.csv')
        else:
            _estado_vacio_stats(
                'Sin datos',
                'No hay pacientes registrados con fecha de alta'
                + (f' en {ano_sel}.' if ano_sel else '.'),
            )

    with tabs[2]:
        st.markdown('#### Facturación por mes')
        fact_meses = _sumar_por_mes(facturacion, campo_fecha='fecha', campo_valor='monto', filtro_ano=ano_sel)
        if fact_meses:
            df_fact = pd.DataFrame([
                {'Mes': k, 'Monto': v} for k, v in sorted(fact_meses.items())
            ])
            render_chart_card(
                'Evolución de facturación mensual',
                chart_linea(df_fact, 'Mes', 'Monto', titulo_x='Mes', titulo_y='Monto ($)'),
            )
            _descargar_csv([{'Mes': k, 'Monto': v} for k, v in sorted(fact_meses.items())], 'facturacion_mensual.csv')
            st.success(f'Total facturado: **${sum(fact_meses.values()):,.2f}**')
        else:
            _estado_vacio_stats(
                'Sin datos',
                'No hay facturación registrada'
                + (f' en {ano_sel}.' if ano_sel else '.'),
            )

        st.divider()
        st.markdown('#### Método de pago')
        metodos = Counter(f.get('metodo', 'S/D') for f in facturacion)
        if metodos:
            df_met = pd.DataFrame([
                {'Método': k, 'Monto': v} for k, v in metodos.most_common(8)
            ])
            render_chart_card(
                'Distribución por método de pago',
                _chart_barras_mes(df_met, 'Método', 'Monto', titulo_x='Método', titulo_y='Operaciones', color=COLOR_INFO),
            )
        else:
            st.caption('Sin datos de método de pago.')

    with tabs[3]:
        st.markdown('#### Evoluciones registradas por mes')
        conteo_evol = _contar_por_mes(evoluciones, filtro_ano=ano_sel)
        if conteo_evol:
            df_evol = pd.DataFrame([
                {'Mes': k, 'Evoluciones': v} for k, v in sorted(conteo_evol.items())
            ])
            render_chart_card(
                'Evoluciones clínicas mensuales',
                _chart_barras_mes(df_evol, 'Mes', 'Evoluciones', titulo_y='Cantidad', color=COLOR_WARNING),
            )
            _descargar_csv([{'Mes': k, 'Evoluciones': v} for k, v in sorted(conteo_evol.items())], 'evoluciones_mensual.csv')
        else:
            _estado_vacio_stats(
                'Sin datos',
                'No hay evoluciones registradas'
                + (f' en {ano_sel}.' if ano_sel else '.'),
            )

        st.divider()
        st.markdown('#### Evoluciones por profesional')
        if len(evoluciones) < 20000:
            prof_evol = Counter(e.get('firma', e.get('profesional', 'S/D')) for e in evoluciones)
            if prof_evol:
                df_prof = pd.DataFrame([
                    {'Profesional': k, 'Evoluciones': v}
                    for k, v in prof_evol.most_common(15)
                ])
                render_chart_card(
                    'Profesionales que más registran evoluciones',
                    _chart_barras_mes(df_prof, 'Profesional', 'Evoluciones', titulo_y='Cantidad', color=COLOR_SUCCESS),
                )
            else:
                st.caption('Sin datos de profesional en evoluciones.')
        else:
            st.caption(f'Demasiados registros ({len(evoluciones)}) para agrupar por profesional.')

    with tabs[4]:
        st.markdown('#### Estado de inventario')
        if inventario:
            total_items = len(inventario)
            total_units = 0
            items_con_minimo = 0
            items_criticos = []
            for item in inventario:
                stock = _parse_stock(item.get('stock'))
                total_units += stock
                sm = item.get('stock_minimo')
                if sm is not None and str(sm).strip():
                    items_con_minimo += 1
                    if stock <= _parse_stock(sm):
                        items_criticos.append(item)

            mc1, mc2 = st.columns(2)
            mc1.metric('Ítems en inventario', total_items)
            mc1.metric('Unidades totales', total_units)
            mc2.metric('Stock crítico', len(items_criticos))
            mc2.metric('Ítems con mínimo configurado', items_con_minimo)

            if items_criticos and len(items_criticos) <= 500:
                st.divider()
                st.markdown('#### Ítems con stock crítico')
                df_stock = pd.DataFrame([
                    {
                        'Ítem': item.get('item', ''),
                        'Stock': _parse_stock(item.get('stock')),
                        'Mínimo': _parse_stock(item.get('stock_minimo')),
                    }
                    for item in items_criticos[:500]
                ])
                df_stock["_bajo_minimo"] = df_stock["Stock"] <= df_stock["Mínimo"]
                render_chart_card(
                    'Ítems por debajo del stock mínimo',
                    alt.Chart(df_stock).mark_bar(cornerRadiusEnd=4).encode(
                        x=alt.X('Ítem:N', title='Ítem', sort='-y'),
                        y=alt.Y('Stock:Q', title='Stock actual'),
                        color=alt.condition(
                            "_bajo_minimo",
                            alt.value(COLOR_DANGER),
                            alt.value(COLOR_SUCCESS),
                        ),
                        tooltip=[
                            alt.Tooltip('Ítem:N'),
                            alt.Tooltip('Stock:Q'),
                            alt.Tooltip('Mínimo:Q'),
                        ],
                    ).configure_axis(labelFontSize=11, titleFontSize=12).configure_view(strokeWidth=0),
                )
            elif items_criticos:
                st.warning(f'{len(items_criticos)} ítems con stock crítico. Agrupe por categoría para verlos.')
            else:
                if items_con_minimo > 0:
                    st.success('No hay ítems con stock crítico.')
                else:
                    st.info(
                        'Ningún ítem tiene configurado un stock mínimo. '
                        'Para activar las alertas de stock crítico, edite cada ítem en Inventario '
                        'y establezca un valor en "Stock mínimo".'
                    )
        else:
            _estado_vacio_stats(
                'Sin datos',
                'No hay inventario cargado en el sistema.',
                sugerencia='Cargue insumos en el módulo Inventario para ver estadísticas de stock.',
            )

    log_event('estadisticas_vista', f'{mi_empresa}')
