"""
Sistema de Reportes Financieros y Analíticos para Medicare Pro.

Características:
- Dashboard financiero (ingresos, gastos, utilidad)
- Análisis por obra social/aseguradora
- Reportes de productividad médica
- Estadísticas de pacientes (nuevos, recurrentes)
- Previsiones y tendencias
- Exportación a Excel/PDF
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict

from core.app_logging import log_event
from core.audit_trail import audit_log, AuditEventType


def render_financial_reports(mi_empresa=None, rol=None):
    """Renderiza panel de reportes financieros."""
    user = st.session_state.get("u_actual", {})
    if user.get("rol") not in ["admin", "superadmin", "recepcionista"]:
        st.error("Acceso denegado. Solo administradores y recepción.")
        return
    
    st.title("📊 Reportes Financieros y Analíticos")
    st.caption(f"Usuario: {user.get('nombre', 'N/A')} | {datetime.now().strftime('%d/%m/%Y %H:%M')}")
    
    # Tabs
    tabs = st.tabs([
        "💰 Financiero",
        "📈 Productividad",
        "👥 Pacientes",
        "🏥 Obras Sociales",
        "📅 Tendencias"
    ])
    
    with tabs[0]:
        render_financial_dashboard()
    
    with tabs[1]:
        render_productivity_dashboard()
    
    with tabs[2]:
        render_patients_analytics()
    
    with tabs[3]:
        render_insurance_analytics()
    
    with tabs[4]:
        render_trends_forecast()


def render_financial_dashboard():
    """Dashboard financiero."""
    st.header("💰 Dashboard Financiero")
    
    # Período de análisis
    col1, col2, col3 = st.columns(3)
    
    with col1:
        periodo = st.selectbox(
            "Período",
            options=["Hoy", "Esta semana", "Este mes", "Últimos 3 meses", "Este año", "Personalizado"],
            index=2
        )
    
    with col2:
        if periodo == "Personalizado":
            fecha_desde = st.date_input("Desde", value=date.today() - timedelta(days=30))
        else:
            fecha_desde = calculate_period_start(periodo)
    
    with col3:
        if periodo == "Personalizado":
            fecha_hasta = st.date_input("Hasta", value=date.today())
        else:
            fecha_hasta = date.today()
    
    # Obtener datos financieros
    facturacion = st.session_state.get("facturacion_db", [])
    
    # Filtrar por fecha
    facturas_filtradas = filter_by_date_range(facturacion, fecha_desde, fecha_hasta)
    
    # KPIs
    col1, col2, col3, col4 = st.columns(4)
    
    total_facturado = sum(f.get("monto", 0) or 0 for f in facturas_filtradas)
    total_cobrado = sum(f.get("monto_cobrado", 0) or 0 for f in facturas_filtradas)
    total_deuda = total_facturado - total_cobrado
    cantidad_facturas = len(facturas_filtradas)
    
    with col1:
        st.metric(
            "Total Facturado",
            f"${total_facturado:,.2f}",
            help="Suma de todos los montos facturados en el período"
        )
    
    with col2:
        st.metric(
            "Total Cobrado",
            f"${total_cobrado:,.2f}",
            delta=f"{((total_cobrado/total_facturado)*100 if total_facturado > 0 else 0):.1f}%" if total_facturado > 0 else None
        )
    
    with col3:
        st.metric(
            "Por Cobrar",
            f"${total_deuda:,.2f}",
            delta=f"{((total_deuda/total_facturado)*100 if total_facturado > 0 else 0):.1f}%" if total_facturado > 0 else None,
            delta_color="inverse"
        )
    
    with col4:
        st.metric(
            "Facturas Emitidas",
            cantidad_facturas,
            help="Cantidad total de facturas en el período"
        )
    
    st.divider()
    
    # Evolución diaria
    st.subheader("Evolución Diaria")
    
    if facturas_filtradas:
        df = pd.DataFrame(facturas_filtradas)
        
        if "fecha" in df.columns:
            # Agrupar por día
            df["fecha"] = pd.to_datetime(df["fecha"], errors="coerce")
            df = df.dropna(subset=["fecha"])
            
            daily = df.groupby(df["fecha"].dt.date).agg({
                "monto": "sum",
                "monto_cobrado": "sum"
            }).reset_index()
            
            daily.columns = ["Fecha", "Facturado", "Cobrado"]
            
            st.line_chart(daily.set_index("Fecha"))
    else:
        st.info("No hay datos de facturación para el período seleccionado.")
    
    st.divider()
    
    # Desglose por tipo
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Por Tipo de Atención")
        
        tipo_counts = defaultdict(float)
        for f in facturas_filtradas:
            tipo = f.get("tipo", "Consulta")
            tipo_counts[tipo] += f.get("monto", 0) or 0
        
        if tipo_counts:
            data = [{"Tipo": k, "Monto": v} for k, v in sorted(tipo_counts.items(), key=lambda x: x[1], reverse=True)]
            df_tipo = pd.DataFrame(data)
            st.bar_chart(df_tipo.set_index("Tipo"))
    
    with col2:
        st.subheader("Estado de Pagos")
        
        # Simular estados de pago
        pagadas = sum(1 for f in facturas_filtradas if (f.get("monto_cobrado", 0) or 0) >= (f.get("monto", 0) or 0))
        parciales = sum(1 for f in facturas_filtradas if 0 < (f.get("monto_cobrado", 0) or 0) < (f.get("monto", 0) or 0))
        pendientes = sum(1 for f in facturas_filtradas if (f.get("monto_cobrado", 0) or 0) == 0)
        
        data = {
            "Estado": ["Pagadas", "Parciales", "Pendientes"],
            "Cantidad": [pagadas, parciales, pendientes]
        }
        df_estado = pd.DataFrame(data)
        
        try:
            import plotly.express as px
            fig = px.pie(df_estado, values="Cantidad", names="Estado", hole=0.4,
                         template="plotly_dark", color_discrete_sequence=["#10b981", "#f59e0b", "#ef4444"])
            fig.update_layout(margin=dict(l=10, r=10, t=10, b=10),
                              paper_bgcolor="rgba(0,0,0,0)",
                              font=dict(color="#e2e8f0"),
                              showlegend=True)
            fig.update_traces(textposition="inside", textinfo="percent+label")
            st.plotly_chart(fig, use_container_width=True)
        except Exception:
            st.bar_chart(df_estado.set_index("Estado"))
    
    # Exportar
    st.divider()
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📥 Exportar a Excel", width='stretch'):
            if facturas_filtradas:
                df_export = pd.DataFrame(facturas_filtradas)
                output = export_to_excel(df_export, "reporte_financiero")
                st.download_button(
                    "Descargar Excel",
                    output,
                    file_name=f"reporte_financiero_{datetime.now().strftime('%Y%m%d')}.xlsx"
                )
    
    with col2:
        if st.button("📄 Exportar a PDF", width='stretch'):
            st.info("Generación de PDF en desarrollo...")


def render_productivity_dashboard():
    """Dashboard de productividad médica."""
    st.header("📈 Productividad del Equipo Médico")
    
    # Obtener datos
    evoluciones = st.session_state.get("evoluciones_db", [])
    facturacion = st.session_state.get("facturacion_db", [])
    
    # Período
    dias = st.slider("Período (días)", 7, 365, 30)
    fecha_desde = date.today() - timedelta(days=dias)
    
    # Filtrar por fecha
    evo_filtradas = [e for e in evoluciones if parse_date(e.get("fecha")) >= fecha_desde]
    
    # Estadísticas por médico
    medico_stats = defaultdict(lambda: {
        "evoluciones": 0,
        "pacientes_unicos": set(),
        "ingresos": 0.0
    })
    
    for evo in evo_filtradas:
        medico = evo.get("medico_nombre", evo.get("medico_id", "Desconocido"))
        medico_stats[medico]["evoluciones"] += 1
        medico_stats[medico]["pacientes_unicos"].add(evo.get("paciente_id", "unknown"))
    
    # Agregar datos de facturación
    fact_filtradas = [f for f in facturacion if parse_date(f.get("fecha")) >= fecha_desde]
    for fact in fact_filtradas:
        medico = fact.get("medico", "Desconocido")
        medico_stats[medico]["ingresos"] += fact.get("monto", 0) or 0
    
    # Crear DataFrame
    data = []
    for medico, stats in sorted(medico_stats.items(), key=lambda x: x[1]["evoluciones"], reverse=True):
        data.append({
            "Médico": medico,
            "Evoluciones": stats["evoluciones"],
            "Pacientes Únicos": len(stats["pacientes_unicos"]),
            "Ingresos Generados": stats["ingresos"],
            "Promedio por Paciente": stats["ingresos"] / len(stats["pacientes_unicos"]) if stats["pacientes_unicos"] else 0
        })
    
    if data:
        df = pd.DataFrame(data)
        st.dataframe(df, width='stretch', hide_index=True)
        
        # Gráficos
        st.subheader("Comparación Visual")
        
        tab1, tab2, tab3 = st.tabs(["Evoluciones", "Pacientes", "Ingresos"])
        
        with tab1:
            st.bar_chart(df.set_index("Médico")["Evoluciones"])
        
        with tab2:
            st.bar_chart(df.set_index("Médico")["Pacientes Únicos"])
        
        with tab3:
            st.bar_chart(df.set_index("Médico")["Ingresos Generados"])
    else:
        st.info("No hay datos suficientes para el período seleccionado.")


def render_patients_analytics():
    """Analítica de pacientes."""
    st.header("👥 Análisis de Pacientes")
    
    pacientes = st.session_state.get("pacientes_db", {})
    evoluciones = st.session_state.get("evoluciones_db", [])
    
    # KPIs
    total_pacientes = len(pacientes)
    
    # Nuevos vs recurrentes (último mes)
    hoy = date.today()
    mes_pasado = hoy - timedelta(days=30)
    
    pacientes_nuevos = 0
    pacientes_recurrentes = 0
    
    # Contar evoluciones por paciente en el último mes
    paciente_evoluciones = defaultdict(int)
    for evo in evoluciones:
        fecha = parse_date(evo.get("fecha"))
        if fecha >= mes_pasado:
            paciente_evoluciones[evo.get("paciente_id", "")] += 1
    
    # Si tienen 1 evolución y fueron creados recientemente = nuevo
    for p_id, count in paciente_evoluciones.items():
        if count == 1:
            paciente = pacientes.get(p_id)
            if paciente:
                fecha_alta = parse_date(paciente.get("fecha_alta", ""))
                if fecha_alta >= mes_pasado:
                    pacientes_nuevos += 1
                else:
                    pacientes_recurrentes += 1
        else:
            pacientes_recurrentes += 1
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Pacientes", total_pacientes)
    
    with col2:
        st.metric("Nuevos (30d)", pacientes_nuevos)
    
    with col3:
        st.metric("Recurrentes (30d)", pacientes_recurrentes)
    
    with col4:
        tasa_retencion = (pacientes_recurrentes / (pacientes_nuevos + pacientes_recurrentes) * 100) if (pacientes_nuevos + pacientes_recurrentes) > 0 else 0
        st.metric("Tasa Retención", f"{tasa_retencion:.1f}%")
    
    st.divider()
    
    # Distribución por obra social
    st.subheader("Distribución por Obra Social")
    
    os_count = defaultdict(int)
    for p in pacientes.values():
        os = p.get("obra_social", "Sin OS") or "Sin OS"
        os_count[os] += 1
    
    if os_count:
        data = [{"Obra Social": k, "Pacientes": v} for k, v in sorted(os_count.items(), key=lambda x: x[1], reverse=True)]
        df = pd.DataFrame(data)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.dataframe(df, width='stretch', hide_index=True)
        
        with col2:
            st.bar_chart(df.head(10).set_index("Obra Social"))


def render_insurance_analytics():
    """Analítica por obra social/seguro."""
    st.header("🏥 Análisis por Obras Sociales y Seguros")
    
    facturacion = st.session_state.get("facturacion_db", [])
    
    if not facturacion:
        st.info("No hay datos de facturación disponibles.")
        return
    
    # Análisis por obra social
    os_stats = defaultdict(lambda: {"facturas": 0, "monto": 0.0, "cobrado": 0.0})
    
    for fact in facturacion:
        os = fact.get("obra_social", "Particular")
        os_stats[os]["facturas"] += 1
        os_stats[os]["monto"] += fact.get("monto", 0) or 0
        os_stats[os]["cobrado"] += fact.get("monto_cobrado", 0) or 0
    
    data = []
    for os, stats in sorted(os_stats.items(), key=lambda x: x[1]["monto"], reverse=True):
        data.append({
            "Obra Social": os,
            "Facturas": stats["facturas"],
            "Monto Total": stats["monto"],
            "Cobrado": stats["cobrado"],
            "Por Cobrar": stats["monto"] - stats["cobrado"],
            "% Cobranza": (stats["cobrado"] / stats["monto"] * 100) if stats["monto"] > 0 else 0
        })
    
    df = pd.DataFrame(data)
    st.dataframe(df, width='stretch', hide_index=True)
    
    st.divider()
    
    # Visualización
    st.subheader("Top 5 Obras Sociales por Facturación")
    st.bar_chart(df.head(5).set_index("Obra Social")["Monto Total"])


def render_trends_forecast():
    """Tendencias y previsiones."""
    st.header("📅 Tendencias y Previsiones")
    
    evoluciones = st.session_state.get("evoluciones_db", [])
    
    if not evoluciones:
        st.info("No hay datos históricos suficientes.")
        return
    
    # Evolución mensual últimos 12 meses
    meses = defaultdict(int)
    
    for evo in evoluciones:
        fecha = parse_date(evo.get("fecha"))
        if fecha:
            mes_key = fecha.strftime("%Y-%m")
            meses[mes_key] += 1
    
    # Ordenar y tomar últimos 12
    sorted_meses = sorted(meses.items())[-12:]
    
    if sorted_meses:
        data = [{"Mes": k, "Evoluciones": v} for k, v in sorted_meses]
        df = pd.DataFrame(data)
        
        st.subheader("Evoluciones por Mes (Últimos 12 meses)")
        st.line_chart(df.set_index("Mes"))
        
        # Tendencia simple
        if len(data) >= 3:
            ultimos_3 = [d["Evoluciones"] for d in data[-3:]]
            promedio_3 = sum(ultimos_3) / 3
            
            mes_anterior = data[-2]["Evoluciones"] if len(data) >= 2 else 0
            mes_actual = data[-1]["Evoluciones"]
            
            variacion = ((mes_actual - mes_anterior) / mes_anterior * 100) if mes_anterior > 0 else 0
            
            col1, col2 = st.columns(2)
            
            with col1:
                st.metric(
                    "Tendencia Mensual",
                    f"{variacion:+.1f}%",
                    delta_color="normal" if variacion >= 0 else "inverse"
                )
            
            with col2:
                # Proyección simple para próximo mes
                st.metric(
                    "Proyección Próximo Mes",
                    f"{int(promedio_3)} evoluciones",
                    help="Promedio de los últimos 3 meses"
                )
    
    st.divider()
    
    # Comparación año anterior
    st.subheader("Comparación Interanual")
    st.info("Comparación con el mismo período del año anterior estará disponible con más datos históricos.")


def calculate_period_start(periodo: str) -> date:
    """Calcula fecha de inicio según período."""
    hoy = date.today()
    
    if periodo == "Hoy":
        return hoy
    elif periodo == "Esta semana":
        return hoy - timedelta(days=hoy.weekday())
    elif periodo == "Este mes":
        return hoy.replace(day=1)
    elif periodo == "Últimos 3 meses":
        return hoy - timedelta(days=90)
    elif periodo == "Este año":
        return hoy.replace(month=1, day=1)
    else:
        return hoy - timedelta(days=30)


def parse_date(fecha_str: str) -> date:
    """Parsea fecha de string."""
    if not fecha_str:
        return date.min
    
    try:
        # Intentar formato DD/MM/YYYY
        return datetime.strptime(fecha_str[:10], "%d/%m/%Y").date()
    except Exception:
        try:
            # Intentar formato ISO
            return datetime.fromisoformat(fecha_str).date()
        except Exception:
            return date.min


def filter_by_date_range(data: list, desde: date, hasta: date) -> list:
    """Filtra lista de dicts por rango de fechas."""
    result = []
    for item in data:
        fecha = parse_date(item.get("fecha", ""))
        if desde <= fecha <= hasta:
            result.append(item)
    return result


def export_to_excel(df: pd.DataFrame, sheet_name: str) -> bytes:
    """Exporta DataFrame a Excel."""
    output = pd.ExcelWriter(f"{sheet_name}.xlsx", engine='openpyxl')
    df.to_excel(output, sheet_name=sheet_name, index=False)
    
    import io
    buffer = io.BytesIO()
    output.book.save(buffer)
    return buffer.getvalue()
