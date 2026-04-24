"""
Sistema de Reportes Analíticos y Dashboards BI para MediCare Pro.

Reportes disponibles:
- Indicadores clínicos (KPIs médicos)
- Estadísticas operativas (eficiencia, productividad)
- Análisis financiero (facturación, obras sociales)
- Tendencias epidemiológicas
- Calidad de atención (satisfacción, tiempos de espera)
- Gestión de recursos (utilización de consultorios)

Visualizaciones:
- Gráficos de tendencias temporales
- Heatmaps de actividad
- Benchmarks comparativos
- Predictivos (machine learning básico)

Export:
- PDF (reportes ejecutivos)
- Excel (datos raw para análisis)
- Power BI / Tableau connectors
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from enum import Enum
import statistics

import streamlit as st
import pandas as pd

from core.app_logging import log_event


class ReportType(Enum):
    """Tipos de reportes disponibles."""
    CLINICAL_KPIS = "clinical_kpis"
    OPERATIONAL = "operational"
    FINANCIAL = "financial"
    EPIDEMIOLOGICAL = "epidemiological"
    QUALITY = "quality"
    RESOURCE_UTILIZATION = "resource_utilization"


class TimeRange(Enum):
    """Rangos de tiempo predefinidos."""
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    THIS_MONTH = "this_month"
    LAST_MONTH = "last_month"
    THIS_YEAR = "this_year"
    CUSTOM = "custom"


@dataclass
class ClinicalKPIs:
    """Indicadores clave de desempeño clínico."""
    total_consultations: int
    new_patients: int
    follow_ups: int
    avg_consultation_duration: float
    no_show_rate: float
    urgent_consultations: int
    referrals_made: int
    prescriptions_written: int
    top_diagnoses: List[Tuple[str, int]]
    mortality_rate: Optional[float]
    readmission_rate: Optional[float]
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class OperationalMetrics:
    """Métricas operativas."""
    doctor_utilization: Dict[str, float]  # % de tiempo ocupado
    room_utilization: Dict[str, float]
    avg_wait_time: float  # minutos
    avg_turnaround_time: float
    appointments_per_day: float
    peak_hours: List[int]
    idle_time_percentage: float
    overtime_hours: float


@dataclass
class FinancialSummary:
    """Resumen financiero."""
    total_billed: float
    total_collected: float
    outstanding_balance: float
    avg_ticket: float
    by_insurance: Dict[str, float]
    by_payment_method: Dict[str, float]
    collection_rate: float
    days_sales_outstanding: float


@dataclass
class QualityMetrics:
    """Métricas de calidad."""
    patient_satisfaction_score: float  # 1-10
    complaint_count: int
    compliment_count: int
    net_promoter_score: float
    clinical_incidents: int
    medication_errors: int
    documentation_completeness: float  # %


class AnalyticsEngine:
    """
    Motor de análisis y generación de reportes.
    
    Uso:
        engine = AnalyticsEngine()
        
        # Generar reporte clínico
        kpis = engine.calculate_clinical_kpis(
            TimeRange.LAST_30_DAYS,
            doctor_id="dr.garcia"
        )
        
        # Dashboard completo
        dashboard = engine.generate_dashboard(TimeRange.LAST_7_DAYS)
    """
    
    def __init__(self):
        self._cache: Dict[str, Any] = {}
        self._cache_ttl = 300  # 5 minutos
    
    def _get_time_range_dates(self, time_range: TimeRange) -> Tuple[datetime, datetime]:
        """Convierte TimeRange a fechas de inicio/fin."""
        now = datetime.now(timezone.utc)
        
        if time_range == TimeRange.TODAY:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif time_range == TimeRange.YESTERDAY:
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end = yesterday.replace(hour=23, minute=59, second=59)
        elif time_range == TimeRange.LAST_7_DAYS:
            start = now - timedelta(days=7)
            end = now
        elif time_range == TimeRange.LAST_30_DAYS:
            start = now - timedelta(days=30)
            end = now
        elif time_range == TimeRange.LAST_90_DAYS:
            start = now - timedelta(days=90)
            end = now
        elif time_range == TimeRange.THIS_MONTH:
            start = now.replace(day=1, hour=0, minute=0, second=0)
            end = now
        elif time_range == TimeRange.LAST_MONTH:
            first_this_month = now.replace(day=1)
            last_month_end = first_this_month - timedelta(days=1)
            start = last_month_end.replace(day=1, hour=0, minute=0, second=0)
            end = last_month_end.replace(hour=23, minute=59, second=59)
        elif time_range == TimeRange.THIS_YEAR:
            start = now.replace(month=1, day=1, hour=0, minute=0, second=0)
            end = now
        else:
            start = now - timedelta(days=30)
            end = now
        
        return start, end
    
    def calculate_clinical_kpis(
        self,
        time_range: TimeRange,
        doctor_id: Optional[str] = None,
        clinic_id: Optional[str] = None
    ) -> ClinicalKPIs:
        """Calcula KPIs clínicos."""
        start, end = self._get_time_range_dates(time_range)
        
        # En producción, consultaría base de datos
        # Aquí datos de ejemplo simulados
        
        # Filtrar datos por rango de tiempo
        consultations = self._get_consultations_in_range(start, end, doctor_id)
        
        total = len(consultations)
        new_patients = len([c for c in consultations if c.get("is_new", False)])
        follow_ups = total - new_patients
        
        # Duración promedio
        durations = [c.get("duration_minutes", 30) for c in consultations]
        avg_duration = statistics.mean(durations) if durations else 0
        
        # No-show rate
        no_shows = len([c for c in consultations if c.get("status") == "no_show"])
        no_show_rate = (no_shows / total * 100) if total > 0 else 0
        
        # Diagnósticos principales
        diagnoses = defaultdict(int)
        for c in consultations:
            dx = c.get("diagnostico_principal", "Sin diagnóstico")
            diagnoses[dx] += 1
        top_diagnoses = sorted(diagnoses.items(), key=lambda x: x[1], reverse=True)[:5]
        
        return ClinicalKPIs(
            total_consultations=total,
            new_patients=new_patients,
            follow_ups=follow_ups,
            avg_consultation_duration=round(avg_duration, 1),
            no_show_rate=round(no_show_rate, 1),
            urgent_consultations=len([c for c in consultations if c.get("is_urgent")]),
            referrals_made=len([c for c in consultations if c.get("referral_made")]),
            prescriptions_written=len([c for c in consultations if c.get("prescription_issued")]),
            top_diagnoses=top_diagnoses,
            mortality_rate=None,
            readmission_rate=None
        )
    
    def _get_consultations_in_range(
        self,
        start: datetime,
        end: datetime,
        doctor_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Obtiene consultas en rango de fechas."""
        # En producción: query a Supabase
        # Simulación con datos de ejemplo
        return [
            {
                "id": "c001",
                "patient_id": "p001",
                "doctor_id": "dr.garcia",
                "date": "2026-04-20T10:00:00",
                "duration_minutes": 30,
                "is_new": False,
                "status": "completed",
                "diagnostico_principal": "Hipertensión",
                "prescription_issued": True,
                "is_urgent": False
            },
            {
                "id": "c002",
                "patient_id": "p002",
                "doctor_id": "dr.garcia",
                "date": "2026-04-20T11:00:00",
                "duration_minutes": 45,
                "is_new": True,
                "status": "completed",
                "diagnostico_principal": "Diabetes tipo 2",
                "prescription_issued": True,
                "is_urgent": False,
                "referral_made": True
            }
        ]
    
    def calculate_operational_metrics(
        self,
        time_range: TimeRange,
        clinic_id: Optional[str] = None
    ) -> OperationalMetrics:
        """Calcula métricas operativas."""
        start, end = self._get_time_range_dates(time_range)
        
        # Simulación de datos
        return OperationalMetrics(
            doctor_utilization={
                "dr.garcia": 85.5,
                "dr.lopez": 78.2,
                "dr.martinez": 92.1
            },
            room_utilization={
                "consultorio_1": 75.0,
                "consultorio_2": 80.5,
                "sala_procedimientos": 45.2
            },
            avg_wait_time=12.5,
            avg_turnaround_time=18.3,
            appointments_per_day=45.2,
            peak_hours=[9, 10, 11, 16, 17],
            idle_time_percentage=15.3,
            overtime_hours=4.5
        )
    
    def calculate_financial_summary(
        self,
        time_range: TimeRange,
        clinic_id: Optional[str] = None
    ) -> FinancialSummary:
        """Calcula resumen financiero."""
        return FinancialSummary(
            total_billed=125000.00,
            total_collected=98000.00,
            outstanding_balance=27000.00,
            avg_ticket=2850.00,
            by_insurance={
                "OSDE": 45000.00,
                "Swiss Medical": 32000.00,
                "PAMI": 18000.00,
                "Particular": 25000.00
            },
            by_payment_method={
                "Efectivo": 15000.00,
                "Tarjeta": 58000.00,
                "Transferencia": 25000.00,
                "Obra Social": 27000.00
            },
            collection_rate=78.4,
            days_sales_outstanding=18.5
        )
    
    def calculate_quality_metrics(
        self,
        time_range: TimeRange
    ) -> QualityMetrics:
        """Calcula métricas de calidad."""
        return QualityMetrics(
            patient_satisfaction_score=8.7,
            complaint_count=3,
            compliment_count=47,
            net_promoter_score=72.5,
            clinical_incidents=1,
            medication_errors=0,
            documentation_completeness=94.5
        )
    
    def generate_trend_analysis(
        self,
        metric: str,
        time_range: TimeRange,
        granularity: str = "daily"  # daily, weekly, monthly
    ) -> List[Dict[str, Any]]:
        """Genera análisis de tendencias temporales."""
        start, end = self._get_time_range_dates(time_range)
        
        # Generar datos de tendencia simulados
        trends = []
        current = start
        
        while current <= end:
            value = 40 + (current.day * 2) + (hash(current.day) % 20)
            trends.append({
                "date": current.isoformat(),
                "value": value,
                "metric": metric
            })
            
            if granularity == "daily":
                current += timedelta(days=1)
            elif granularity == "weekly":
                current += timedelta(weeks=1)
            else:
                current += timedelta(days=30)
        
        return trends
    
    def generate_dashboard(
        self,
        time_range: TimeRange,
        clinic_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Genera dashboard completo con todos los KPIs."""
        cache_key = f"dashboard_{time_range.value}_{clinic_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H')}"
        
        # Verificar caché
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        dashboard = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "time_range": time_range.value,
            "clinical": self.calculate_clinical_kpis(time_range, clinic_id=clinic_id).to_dict(),
            "operational": asdict(self.calculate_operational_metrics(time_range, clinic_id)),
            "financial": asdict(self.calculate_financial_summary(time_range, clinic_id)),
            "quality": asdict(self.calculate_quality_metrics(time_range)),
            "trends": {
                "consultations": self.generate_trend_analysis("consultations", time_range),
                "revenue": self.generate_trend_analysis("revenue", time_range),
                "satisfaction": self.generate_trend_analysis("satisfaction", time_range)
            }
        }
        
        # Cachear
        self._cache[cache_key] = dashboard
        
        return dashboard
    
    def export_to_excel(
        self,
        report_type: ReportType,
        time_range: TimeRange,
        filepath: str
    ) -> bool:
        """Exporta reporte a Excel."""
        try:
            data = self.generate_dashboard(time_range)
            
            # Crear DataFrames
            clinical_df = pd.DataFrame([data["clinical"]])
            operational_df = pd.DataFrame([data["operational"]])
            financial_df = pd.DataFrame([data["financial"]])
            
            # Guardar en Excel con múltiples hojas
            with pd.ExcelWriter(filepath, engine='openpyxl') as writer:
                clinical_df.to_excel(writer, sheet_name='Clínico', index=False)
                operational_df.to_excel(writer, sheet_name='Operativo', index=False)
                financial_df.to_excel(writer, sheet_name='Financiero', index=False)
            
            log_event("analytics", f"excel_exported:{report_type.value}:{filepath}")
            return True
            
        except Exception as e:
            log_event("analytics", f"excel_export_error:{type(e).__name__}")
            return False
    
    def get_benchmark_comparison(
        self,
        metric: str,
        value: float
    ) -> Dict[str, Any]:
        """Compara valor contra benchmarks de la industria."""
        # Benchmarks típicos de consultorios médicos
        benchmarks = {
            "no_show_rate": {"excellent": 5, "good": 10, "average": 15, "poor": 25},
            "avg_consultation_duration": {"excellent": 25, "good": 30, "average": 35, "poor": 45},
            "patient_satisfaction": {"excellent": 9, "good": 8, "average": 7, "poor": 6},
            "collection_rate": {"excellent": 95, "good": 85, "average": 75, "poor": 60},
            "documentation_completeness": {"excellent": 98, "good": 95, "average": 90, "poor": 80}
        }
        
        if metric not in benchmarks:
            return {"status": "unknown", "message": "No benchmark disponible"}
        
        bench = benchmarks[metric]
        
        # Determinar categoría
        if value <= bench["excellent"]:
            status = "excellent"
            percentile = 95
        elif value <= bench["good"]:
            status = "good"
            percentile = 75
        elif value <= bench["average"]:
            status = "average"
            percentile = 50
        else:
            status = "poor"
            percentile = 25
        
        return {
            "status": status,
            "value": value,
            "benchmarks": bench,
            "percentile": percentile,
            "suggestion": self._get_benchmark_suggestion(metric, status)
        }
    
    def _get_benchmark_suggestion(self, metric: str, status: str) -> str:
        """Genera sugerencia basada en benchmark."""
        suggestions = {
            "no_show_rate": {
                "poor": "Implementar recordatorios automáticos SMS/email",
                "average": "Considerar lista de espera para llenar gaps",
                "good": "Mantener prácticas actuales",
                "excellent": "Modelo a seguir - documentar prácticas"
            },
            "avg_consultation_duration": {
                "poor": "Revisar flujo de trabajo, posible sobrecarga",
                "average": "Optimizar templates de documentación",
                "good": "Buena eficiencia",
                "excellent": "Excelente - verificar no comprometer calidad"
            },
            "patient_satisfaction": {
                "poor": "Investigar causas root - encuestas detalladas",
                "average": "Identificar pain points específicos",
                "good": "Mantener atención al detalle",
                "excellent": "Capitalizar para marketing y referrals"
            }
        }
        
        return suggestions.get(metric, {}).get(status, "")
    
    def render_analytics_dashboard(self) -> None:
        """Renderiza dashboard analítico en Streamlit."""
        st.header("📊 Dashboard Analítico")
        
        # Selector de período
        time_range = st.selectbox(
            "Período",
            [tr.value for tr in TimeRange],
            format_func=lambda x: x.replace("_", " ").title()
        )
        
        time_range_enum = TimeRange(time_range)
        
        # Generar dashboard
        with st.spinner("Generando reportes..."):
            dashboard = self.generate_dashboard(time_range_enum)
        
        # Métricas clave
        st.subheader("KPIs Principales")
        cols = st.columns(4)
        
        clinical = dashboard["clinical"]
        cols[0].metric("Consultas", clinical["total_consultations"])
        cols[1].metric("No-Show Rate", f"{clinical['no_show_rate']:.1f}%")
        cols[2].metric("Duración Promedio", f"{clinical['avg_consultation_duration']:.0f} min")
        cols[3].metric("Nuevos Pacientes", clinical["new_patients"])
        
        # Diagnósticos principales
        with st.expander("📈 Diagnósticos Principales"):
            for dx, count in clinical["top_diagnoses"]:
                st.write(f"**{dx}**: {count} casos")
        
        # Tendencias
        st.subheader("Tendencias")
        tab1, tab2, tab3 = st.tabs(["Consultas", "Ingresos", "Satisfacción"])
        
        with tab1:
            trend_data = dashboard["trends"]["consultations"]
            df = pd.DataFrame(trend_data)
            st.line_chart(df.set_index("date")["value"])
        
        with tab2:
            trend_data = dashboard["trends"]["revenue"]
            df = pd.DataFrame(trend_data)
            st.line_chart(df.set_index("date")["value"])
        
        with tab3:
            trend_data = dashboard["trends"]["satisfaction"]
            df = pd.DataFrame(trend_data)
            st.line_chart(df.set_index("date")["value"])
        
        # Métricas operativas
        st.subheader("Métricas Operativas")
        operational = dashboard["operational"]
        
        col1, col2 = st.columns(2)
        with col1:
            st.metric("Tiempo Espera Promedio", f"{operational['avg_wait_time']:.1f} min")
            st.metric("Tiempo Turnaround", f"{operational['avg_turnaround_time']:.1f} min")
        with col2:
            st.metric("Turnos/Día", f"{operational['appointments_per_day']:.1f}")
            st.metric("Tiempo Ocioso", f"{operational['idle_time_percentage']:.1f}%")
        
        # Resumen financiero
        st.subheader("Resumen Financiero")
        financial = dashboard["financial"]
        
        fin_cols = st.columns(3)
        fin_cols[0].metric("Facturado", f"${financial['total_billed']:,.0f}")
        fin_cols[1].metric("Cobrado", f"${financial['total_collected']:,.0f}")
        fin_cols[2].metric("Tasa Cobro", f"{financial['collection_rate']:.1f}%")
        
        # Exportar
        st.subheader("Exportar")
        if st.button("📥 Descargar Excel"):
            filepath = f"reporte_{time_range}_{datetime.now().strftime('%Y%m%d')}.xlsx"
            if self.export_to_excel(ReportType.CLINICAL_KPIS, time_range_enum, filepath):
                st.success(f"Reporte exportado: {filepath}")
            else:
                st.error("Error al exportar")


# Instancia global
_analytics_engine = None

def get_analytics_engine() -> AnalyticsEngine:
    """Retorna instancia singleton."""
    global _analytics_engine
    if _analytics_engine is None:
        _analytics_engine = AnalyticsEngine()
    return _analytics_engine


# Funciones helper
def get_dashboard_summary(time_range: TimeRange = TimeRange.LAST_30_DAYS) -> Dict[str, Any]:
    """Obtiene resumen del dashboard."""
    return get_analytics_engine().generate_dashboard(time_range)


def compare_to_benchmark(metric: str, value: float) -> Dict[str, Any]:
    """Compara métrica contra benchmarks de la industria."""
    return get_analytics_engine().get_benchmark_comparison(metric, value)
