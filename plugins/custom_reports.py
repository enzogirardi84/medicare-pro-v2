"""
Plugin de Reportes Personalizados para Medicare Pro.

Ejemplo de plugin real que agrega:
- Reporte de productividad médica
- Estadísticas de pacientes por mes
- Gráficos de evoluciones
"""

from core.plugin_system import MedicarePlugin, PluginInfo, PluginHook, register_hook
from core.app_logging import log_event

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta


class CustomReportsPlugin(MedicarePlugin):
    """
    Plugin de reportes personalizados.
    
    Agrega nuevas páginas de reportes al dashboard administrativo.
    """
    
    def get_info(self) -> PluginInfo:
        return PluginInfo(
            name="custom_reports",
            version="1.0.0",
            description="Reportes personalizados y analíticas avanzadas",
            author="Medicare Team",
            requires=[],
            hooks=[
                PluginHook.APP_INIT,
                PluginHook.POST_RENDER
            ],
            config_schema={
                "default_date_range": {
                    "type": "number",
                    "label": "Rango de fechas por defecto (días)",
                    "default": 30
                },
                "show_charts": {
                    "type": "boolean",
                    "label": "Mostrar gráficos",
                    "default": True
                },
                "export_format": {
                    "type": "string",
                    "label": "Formato de exportación por defecto",
                    "default": "excel"
                }
            },
            enabled=True,
            priority=50
        )
    
    def initialize(self, config: dict) -> bool:
        """Inicializa el plugin."""
        self.date_range = config.get("default_date_range", 30)
        self.show_charts = config.get("show_charts", True)
        self.export_format = config.get("export_format", "excel")
        
        log_event("plugin", "Custom Reports plugin initialized")
        return True
    
    def on_app_init(self, context: dict) -> dict:
        """Se ejecuta al iniciar la app."""
        log_event("plugin", "Custom Reports: App init hook triggered")
        
        # Registrar vistas adicionales
        context["additional_views"] = context.get("additional_views", [])
        context["additional_views"].append({
            "name": "Reportes Personalizados",
            "icon": "📊",
            "function": self.render_reports_page
        })
        
        return context
    
    def render_reports_page(self):
        """Renderiza página de reportes personalizados."""
        st.title("📊 Reportes Personalizados")
        st.caption("Plugin: Reportes Avanzados v1.0")
        
        # Tabs de reportes
        tabs = st.tabs([
            "📈 Productividad",
            "👥 Pacientes",
            "📋 Evoluciones",
            "💊 Prescripciones"
        ])
        
        with tabs[0]:
            self._render_productivity_report()
        
        with tabs[1]:
            self._render_patients_report()
        
        with tabs[2]:
            self._render_evolutions_report()
        
        with tabs[3]:
            self._render_prescriptions_report()
    
    def _render_productivity_report(self):
        """Reporte de productividad médica."""
        st.header("Productividad del Equipo Médico")
        
        # Obtener datos
        evoluciones_db = st.session_state.get("evoluciones_db", [])
        
        if not evoluciones_db:
            st.info("No hay datos de evoluciones para analizar.")
            return
        
        # Contar por médico
        from collections import defaultdict
        
        medico_stats = defaultdict(lambda: {"count": 0, "last_date": None})
        
        for evo in evoluciones_db:
            medico_id = evo.get("medico_id", "unknown")
            medico_nombre = evo.get("medico_nombre", medico_id)
            
            medico_stats[medico_nombre]["count"] += 1
            
            fecha = evo.get("fecha", "")
            if fecha and (not medico_stats[medico_nombre]["last_date"] or fecha > medico_stats[medico_nombre]["last_date"]):
                medico_stats[medico_nombre]["last_date"] = fecha
        
        # Mostrar tabla
        data = []
        for nombre, stats in sorted(medico_stats.items(), key=lambda x: x[1]["count"], reverse=True):
            data.append({
                "Médico": nombre,
                "Evoluciones": stats["count"],
                "Última Actividad": stats["last_date"] or "N/A"
            })
        
        df = pd.DataFrame(data)
        st.dataframe(df, width='stretch')
        
        # Gráfico
        if self.show_charts and len(data) > 0:
            st.subheader("Gráfico de Productividad")
            chart_data = df.set_index("Médico")
            st.bar_chart(chart_data["Evoluciones"])
        
        # Exportar
        if st.button("📥 Exportar a Excel"):
            output = self._export_to_excel(df, "productividad")
            st.download_button(
                "Descargar",
                output,
                file_name=f"productividad_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )
    
    def _render_patients_report(self):
        """Reporte de pacientes."""
        st.header("Estadísticas de Pacientes")
        
        pacientes_db = st.session_state.get("pacientes_db", {})
        
        if not pacientes_db:
            st.info("No hay pacientes registrados.")
            return
        
        # KPIs
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("Total Pacientes", len(pacientes_db))
        
        with col2:
            obras_sociales = set(p.get("obra_social", "Sin OS") for p in pacientes_db.values())
            st.metric("Obras Sociales", len(obras_sociales))
        
        with col3:
            con_alergias = sum(1 for p in pacientes_db.values() if p.get("alergias"))
            st.metric("Con Alergias", con_alergias)
        
        with col4:
            con_email = sum(1 for p in pacientes_db.values() if p.get("email"))
            st.metric("Con Email", con_email)
        
        # Distribución por obra social
        st.subheader("Distribución por Obra Social")
        
        os_counts = {}
        for p in pacientes_db.values():
            os = p.get("obra_social", "Sin OS") or "Sin OS"
            os_counts[os] = os_counts.get(os, 0) + 1
        
        os_data = [{"Obra Social": k, "Pacientes": v} for k, v in sorted(os_counts.items(), key=lambda x: x[1], reverse=True)]
        df_os = pd.DataFrame(os_data)
        
        st.dataframe(df_os, width='stretch')
        
        if self.show_charts:
            st.bar_chart(df_os.set_index("Obra Social"))
    
    def _render_evolutions_report(self):
        """Reporte de evoluciones."""
        st.header("Análisis de Evoluciones")
        
        evoluciones_db = st.session_state.get("evoluciones_db", [])
        
        if not evoluciones_db:
            st.info("No hay evoluciones registradas.")
            return
        
        # Tendencia temporal
        from collections import Counter
        
        fechas = []
        for evo in evoluciones_db:
            fecha = evo.get("fecha", "")
            if fecha and len(fecha) >= 7:
                # Agrupar por mes (YYYY-MM)
                mes = fecha[:7]
                fechas.append(mes)
        
        conteo = Counter(fechas)
        
        data = [{"Mes": k, "Evoluciones": v} for k, v in sorted(conteo.items())]
        df = pd.DataFrame(data)
        
        st.subheader("Evoluciones por Mes")
        st.dataframe(df, width='stretch')
        
        if self.show_charts and len(data) > 1:
            st.line_chart(df.set_index("Mes"))
    
    def _render_prescriptions_report(self):
        """Reporte de prescripciones."""
        st.header("Análisis de Prescripciones")
        
        recetas_db = st.session_state.get("recetas_db", [])
        
        if not recetas_db:
            st.info("No hay recetas registradas.")
            return
        
        # Medicamentos más prescritos
        from collections import Counter
        
        medicamentos = []
        for receta in recetas_db:
            meds = receta.get("medicamentos", [])
            for med in meds:
                nombre = med.get("nombre", "Desconocido")
                medicamentos.append(nombre)
        
        conteo = Counter(medicamentos)
        
        st.subheader("Top Medicamentos Prescritos")
        
        data = [{"Medicamento": k, "Prescripciones": v} for k, v in conteo.most_common(20)]
        df = pd.DataFrame(data)
        
        st.dataframe(df, width='stretch')
        
        if self.show_charts and len(data) > 0:
            st.bar_chart(df.head(10).set_index("Medicamento"))
    
    def _export_to_excel(self, df: pd.DataFrame, sheet_name: str) -> bytes:
        """Exporta DataFrame a Excel."""
        output = pd.ExcelWriter(f"{sheet_name}.xlsx", engine='openpyxl')
        df.to_excel(output, sheet_name=sheet_name, index=False)
        
        # Obtener bytes
        import io
        buffer = io.BytesIO()
        output.book.save(buffer)
        return buffer.getvalue()


# Instancia del plugin
plugin_instance = CustomReportsPlugin()
