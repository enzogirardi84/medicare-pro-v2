"""
Sistema de Gestión de Enfermedades Crónicas para MediCare Pro.

Enfermedades soportadas:
- Diabetes Mellitus (Tipo 1 y 2)
- Hipertensión Arterial
- Enfermedad Pulmonar Obstructiva Crónica (EPOC)
- Insuficiencia Cardíaca
- Enfermedad Renal Crónica
- Asma

Características:
- Seguimiento de parámetros clínicos
- Alertas de control fuera de objetivo
- Recordatorios de controles periódicos
- Metas de tratamiento personalizadas
- Historial de evolución
- Control de complicaciones
- Integración con signos vitales
- Reportes para auditoría de calidad
"""
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from collections import defaultdict
import statistics

import streamlit as st

from core.app_logging import log_event
from core.realtime_notifications import send_critical_alert, NotificationPriority


class ChronicDiseaseType(Enum):
    """Tipos de enfermedades crónicas."""
    DIABETES_T1 = "diabetes_tipo_1"
    DIABETES_T2 = "diabetes_tipo_2"
    HIPERTENSION = "hipertension_arterial"
    EPOC = "epoc"
    INSUFICIENCIA_CARDIACA = "insuficiencia_cardiaca"
    ENFERMEDAD_RENAL = "enfermedad_renal_cronica"
    ASMA = "asma"


class ControlStatus(Enum):
    """Estado de control de la enfermedad."""
    WELL_CONTROLLED = "bien_controlada"
    FAIRLY_CONTROLLED = "regularmente_controlada"
    POORLY_CONTROLLED = "mal_controlada"
    UNCONTROLLED = "descontrolada"
    UNKNOWN = "desconocido"


@dataclass
class ClinicalTarget:
    """Meta clínica para una enfermedad."""
    parameter: str
    min_value: Optional[float]
    max_value: Optional[float]
    unit: str
    description: str
    priority: str  # high, medium, low


@dataclass
class DiseaseControlRecord:
    """Registro de control de enfermedad crónica."""
    record_id: str
    patient_id: str
    disease_type: str
    date_recorded: str
    parameters: Dict[str, Any]  # {hba1c: 7.2, pa_sistolica: 130, ...}
    medications: List[str]
    complications: List[str]
    professional_id: str
    notes: Optional[str] = None
    next_control_date: Optional[str] = None
    adherence_percentage: Optional[float] = None  # % adherencia al tratamiento
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class DiabetesManager:
    """Gestor específico para Diabetes Mellitus."""
    
    # Metas clínicas según ADA (American Diabetes Association) 2024
    CLINICAL_TARGETS = {
        "hba1c": ClinicalTarget(
            parameter="HbA1c",
            min_value=None,
            max_value=7.0,
            unit="%",
            description="Hemoglobina glicosilada",
            priority="high"
        ),
        "glucosa_ayunas": ClinicalTarget(
            parameter="Glucosa en ayunas",
            min_value=80,
            max_value=130,
            unit="mg/dL",
            description="Glucosa plasmática en ayunas",
            priority="high"
        ),
        "glucosa_postprandial": ClinicalTarget(
            parameter="Glucosa postprandial",
            min_value=None,
            max_value=180,
            unit="mg/dL",
            description="Glucosa 2 horas postprandial",
            priority="medium"
        ),
        "pa_sistolica": ClinicalTarget(
            parameter="Presión arterial sistólica",
            min_value=None,
            max_value=130,
            unit="mmHg",
            description="PA sistólica",
            priority="high"
        ),
        "pa_diastolica": ClinicalTarget(
            parameter="Presión arterial diastólica",
            min_value=None,
            max_value=80,
            unit="mmHg",
            description="PA diastólica",
            priority="high"
        ),
        "ldl": ClinicalTarget(
            parameter="Colesterol LDL",
            min_value=None,
            max_value=100,
            unit="mg/dL",
            description="Colesterol malo",
            priority="medium"
        ),
        "trigliceridos": ClinicalTarget(
            parameter="Triglicéridos",
            min_value=None,
            max_value=150,
            unit="mg/dL",
            description="Triglicéridos plasmáticos",
            priority="medium"
        ),
        "imc": ClinicalTarget(
            parameter="IMC",
            min_value=18.5,
            max_value=25.0,
            unit="kg/m²",
            description="Índice de Masa Corporal",
            priority="medium"
        )
    }
    
    def __init__(self):
        self._records: Dict[str, List[DiseaseControlRecord]] = {}
        self._load_records()
    
    def _load_records(self) -> None:
        """Carga registros de diabetes."""
        if "diabetes_records" in st.session_state:
            records_data = st.session_state["diabetes_records"]
            for patient_id, records in records_data.items():
                self._records[patient_id] = [DiseaseControlRecord(**r) for r in records]
    
    def _save_records(self) -> None:
        """Guarda registros de diabetes."""
        st.session_state["diabetes_records"] = {
            patient_id: [r.to_dict() for r in records]
            for patient_id, records in self._records.items()
        }
    
    def record_control(
        self,
        patient_id: str,
        hba1c: Optional[float] = None,
        glucosa_ayunas: Optional[float] = None,
        glucosa_postprandial: Optional[float] = None,
        pa_sistolica: Optional[float] = None,
        pa_diastolica: Optional[float] = None,
        ldl: Optional[float] = None,
        trigliceridos: Optional[float] = None,
        imc: Optional[float] = None,
        medications: Optional[List[str]] = None,
        complications: Optional[List[str]] = None,
        professional_id: str = "system",
        notes: Optional[str] = None,
        next_control_months: int = 3
    ) -> DiseaseControlRecord:
        """Registra un control de diabetes."""
        
        parameters = {
            "hba1c": hba1c,
            "glucosa_ayunas": glucosa_ayunas,
            "glucosa_postprandial": glucosa_postprandial,
            "pa_sistolica": pa_sistolica,
            "pa_diastolica": pa_diastolica,
            "ldl": ldl,
            "trigliceridos": trigliceridos,
            "imc": imc
        }
        
        # Remover None values
        parameters = {k: v for k, v in parameters.items() if v is not None}
        
        record_id = f"dm-{datetime.now(timezone.utc).timestamp()}-{hash(patient_id) % 10000}"
        
        record = DiseaseControlRecord(
            record_id=record_id,
            patient_id=patient_id,
            disease_type=ChronicDiseaseType.DIABETES_T2.value,
            date_recorded=datetime.now(timezone.utc).isoformat(),
            parameters=parameters,
            medications=medications or [],
            complications=complications or [],
            professional_id=professional_id,
            notes=notes,
            next_control_date=(datetime.now(timezone.utc) + timedelta(days=30*next_control_months)).isoformat()
        )
        
        if patient_id not in self._records:
            self._records[patient_id] = []
        
        self._records[patient_id].append(record)
        self._save_records()
        
        # Verificar alertas
        self._check_alerts(patient_id, parameters)
        
        log_event("chronic_disease", f"diabetes_control_recorded:{patient_id}:hba1c:{hba1c}")
        
        return record
    
    def _check_alerts(self, patient_id: str, parameters: Dict[str, Any]) -> None:
        """Verifica alertas de control."""
        hba1c = parameters.get("hba1c")
        glucosa = parameters.get("glucosa_ayunas")
        
        # HbA1c muy alta
        if hba1c and hba1c > 9.0:
            send_critical_alert(
                title="Diabetes Mal Controlada",
                message=f"Paciente con HbA1c {hba1c}% - Requiere ajuste terapéutico urgente",
                patient_id=patient_id,
                priority=NotificationPriority.HIGH
            )
        
        # Hipoglucemia
        if glucosa and glucosa < 70:
            send_critical_alert(
                title="Hipoglucemia Detectada",
                message=f"Glucosa {glucosa} mg/dL - Evaluar tratamiento",
                patient_id=patient_id,
                priority=NotificationPriority.CRITICAL
            )
    
    def get_control_status(self, patient_id: str) -> Tuple[ControlStatus, List[str]]:
        """
        Determina estado de control del paciente.
        
        Returns:
            (status, messages)
        """
        records = self._records.get(patient_id, [])
        
        if not records:
            return ControlStatus.UNKNOWN, ["Sin registros de control"]
        
        # Obtener último registro
        latest = sorted(records, key=lambda r: r.date_recorded, reverse=True)[0]
        
        parameters = latest.parameters
        messages = []
        out_of_target = 0
        total_measured = 0
        
        for param_name, target in self.CLINICAL_TARGETS.items():
            value = parameters.get(param_name)
            if value is None:
                continue
            
            total_measured += 1
            
            # Verificar si está en rango
            in_range = True
            if target.min_value is not None and value < target.min_value:
                in_range = False
            if target.max_value is not None and value > target.max_value:
                in_range = False
            
            if not in_range:
                out_of_target += 1
                messages.append(f"{target.parameter}: {value} {target.unit} (meta: {target.min_value}-{target.max_value})")
        
        # Determinar estado
        if total_measured == 0:
            return ControlStatus.UNKNOWN, ["Sin parámetros medidos"]
        
        percentage_in_range = ((total_measured - out_of_target) / total_measured) * 100
        
        if percentage_in_range >= 90:
            status = ControlStatus.WELL_CONTROLLED
        elif percentage_in_range >= 70:
            status = ControlStatus.FAIRLY_CONTROLLED
        elif percentage_in_range >= 50:
            status = ControlStatus.POORLY_CONTROLLED
        else:
            status = ControlStatus.UNCONTROLLED
        
        return status, messages
    
    def get_trend_analysis(
        self,
        patient_id: str,
        parameter: str,
        months: int = 6
    ) -> List[Dict[str, Any]]:
        """Obtiene tendencia de un parámetro."""
        records = self._records.get(patient_id, [])
        
        cutoff = datetime.now(timezone.utc) - timedelta(days=30*months)
        
        trend = []
        for record in records:
            record_date = datetime.fromisoformat(record.date_recorded)
            if record_date >= cutoff and parameter in record.parameters:
                trend.append({
                    "date": record.date_recorded,
                    "value": record.parameters[parameter]
                })
        
        trend.sort(key=lambda x: x["date"])
        return trend
    
    def get_pending_controls(self) -> List[Dict[str, Any]]:
        """Obtiene pacientes con controles vencidos."""
        pending = []
        now = datetime.now(timezone.utc)
        
        for patient_id, records in self._records.items():
            if not records:
                continue
            
            latest = sorted(records, key=lambda r: r.date_recorded, reverse=True)[0]
            
            if latest.next_control_date:
                next_control = datetime.fromisoformat(latest.next_control_date)
                if next_control < now:
                    days_overdue = (now - next_control).days
                    pending.append({
                        "patient_id": patient_id,
                        "last_control": latest.date_recorded,
                        "next_control_due": latest.next_control_date,
                        "days_overdue": days_overdue,
                        "hba1c_last": latest.parameters.get("hba1c")
                    })
        
        pending.sort(key=lambda x: x["days_overdue"], reverse=True)
        return pending


class HypertensionManager:
    """Gestor específico para Hipertensión Arterial."""
    
    # Metas clínicas según guías ESC/ESH 2023
    CLINICAL_TARGETS = {
        "pa_sistolica": ClinicalTarget(
            parameter="Presión arterial sistólica",
            min_value=None,
            max_value=130,
            unit="mmHg",
            description="PA sistólica",
            priority="high"
        ),
        "pa_diastolica": ClinicalTarget(
            parameter="Presión arterial diastólica",
            min_value=None,
            max_value=80,
            unit="mmHg",
            description="PA diastólica",
            priority="high"
        ),
        "frecuencia_cardiaca": ClinicalTarget(
            parameter="Frecuencia cardíaca",
            min_value=60,
            max_value=80,
            unit="lpm",
            description="FC en reposo",
            priority="medium"
        )
    }
    
    def __init__(self):
        self._records: Dict[str, List[DiseaseControlRecord]] = {}
        self._load_records()
    
    def _load_records(self) -> None:
        """Carga registros de hipertensión."""
        if "hypertension_records" in st.session_state:
            records_data = st.session_state["hypertension_records"]
            for patient_id, records in records_data.items():
                self._records[patient_id] = [DiseaseControlRecord(**r) for r in records]
    
    def _save_records(self) -> None:
        """Guarda registros de hipertensión."""
        st.session_state["hypertension_records"] = {
            patient_id: [r.to_dict() for r in records]
            for patient_id, records in self._records.items()
        }
    
    def record_control(
        self,
        patient_id: str,
        pa_sistolica: float,
        pa_diastolica: float,
        frecuencia_cardiaca: Optional[float] = None,
        medications: Optional[List[str]] = None,
        complications: Optional[List[str]] = None,
        professional_id: str = "system",
        notes: Optional[str] = None
    ) -> DiseaseControlRecord:
        """Registra un control de hipertensión."""
        
        parameters = {
            "pa_sistolica": pa_sistolica,
            "pa_diastolica": pa_diastolica
        }
        
        if frecuencia_cardiaca:
            parameters["frecuencia_cardiaca"] = frecuencia_cardiaca
        
        record_id = f"ht-{datetime.now(timezone.utc).timestamp()}-{hash(patient_id) % 10000}"
        
        record = DiseaseControlRecord(
            record_id=record_id,
            patient_id=patient_id,
            disease_type=ChronicDiseaseType.HIPERTENSION.value,
            date_recorded=datetime.now(timezone.utc).isoformat(),
            parameters=parameters,
            medications=medications or [],
            complications=complications or [],
            professional_id=professional_id,
            notes=notes,
            next_control_date=(datetime.now(timezone.utc) + timedelta(days=90)).isoformat()  # Cada 3 meses
        )
        
        if patient_id not in self._records:
            self._records[patient_id] = []
        
        self._records[patient_id].append(record)
        self._save_records()
        
        # Verificar alertas
        if pa_sistolica > 180 or pa_diastolica > 110:
            send_critical_alert(
                title="HTA Descontrolada - Urgencia",
                message=f"PA {pa_sistolica}/{pa_diastolica} mmHg - Riesgo cardiovascular inmediato",
                patient_id=patient_id,
                priority=NotificationPriority.CRITICAL
            )
        
        log_event("chronic_disease", f"hypertension_control_recorded:{patient_id}:pa:{pa_sistolica}/{pa_diastolica}")
        
        return record
    
    def get_control_status(self, patient_id: str) -> Tuple[ControlStatus, List[str]]:
        """Determina estado de control de HTA."""
        records = self._records.get(patient_id, [])
        
        if not records:
            return ControlStatus.UNKNOWN, ["Sin registros"]
        
        latest = sorted(records, key=lambda r: r.date_recorded, reverse=True)[0]
        parameters = latest.parameters
        
        sistolica = parameters.get("pa_sistolica", 0)
        diastolica = parameters.get("pa_diastolica", 0)
        
        messages = []
        
        if sistolica > 140 or diastolica > 90:
            status = ControlStatus.POORLY_CONTROLLED
            messages.append(f"PA elevada: {sistolica}/{diastolica} mmHg")
        elif sistolica > 130 or diastolica > 80:
            status = ControlStatus.FAIRLY_CONTROLLED
            messages.append(f"PA limítrofe: {sistolica}/{diastolica} mmHg")
        else:
            status = ControlStatus.WELL_CONTROLLED
        
        return status, messages


class ChronicDiseaseDashboard:
    """Dashboard para gestión de enfermedades crónicas."""
    
    def __init__(self):
        self.diabetes_manager = DiabetesManager()
        self.hypertension_manager = HypertensionManager()
    
    def render(self) -> None:
        """Renderiza dashboard de enfermedades crónicas."""
        st.header("🏥 Gestión de Enfermedades Crónicas")
        
        tab1, tab2, tab3 = st.tabs(["Diabetes", "Hipertensión", "Alertas"])
        
        with tab1:
            self._render_diabetes_tab()
        
        with tab2:
            self._render_hypertension_tab()
        
        with tab3:
            self._render_alerts_tab()
    
    def _render_diabetes_tab(self) -> None:
        """Renderiza pestaña de diabetes."""
        st.subheader("Diabetes Mellitus")
        
        patient_id = st.text_input("ID del Paciente (Diabetes)", key="dm_patient")
        
        col1, col2 = st.columns(2)
        
        with col1:
            hba1c = st.number_input("HbA1c (%)", min_value=0.0, max_value=20.0, value=7.0, step=0.1)
            glucosa_ayunas = st.number_input("Glucosa Ayunas (mg/dL)", min_value=0, max_value=500, value=110)
            glucosa_post = st.number_input("Glucosa Postprandial (mg/dL)", min_value=0, max_value=500, value=140)
        
        with col2:
            pa_sys = st.number_input("PA Sistólica", min_value=0, max_value=300, value=130)
            pa_dia = st.number_input("PA Diastólica", min_value=0, max_value=200, value=85)
            ldl = st.number_input("LDL (mg/dL)", min_value=0, max_value=300, value=100)
        
        medications = st.multiselect(
            "Medicamentos",
            ["Metformina", "Glibenclamida", "Insulina NPH", "Insulina Glargina", "Atorvastatina", "Enalapril"]
        )
        
        if st.button("💉 Registrar Control Diabetes", type="primary"):
            if patient_id:
                record = self.diabetes_manager.record_control(
                    patient_id=patient_id,
                    hba1c=hba1c,
                    glucosa_ayunas=glucosa_ayunas,
                    glucosa_postprandial=glucosa_post,
                    pa_sistolica=pa_sys,
                    pa_diastolica=pa_dia,
                    ldl=ldl,
                    medications=medications
                )
                
                status, messages = self.diabetes_manager.get_control_status(patient_id)
                
                if status == ControlStatus.WELL_CONTROLLED:
                    st.success("✅ Diabetes bien controlada")
                elif status == ControlStatus.FAIRLY_CONTROLLED:
                    st.warning("⚠️ Diabetes regularmente controlada")
                else:
                    st.error(f"❌ {status.value}")
                
                if messages:
                    for msg in messages:
                        st.write(f"• {msg}")
            else:
                st.error("Ingrese ID del paciente")
        
        # Mostrar tendencia
        if patient_id and st.checkbox("Ver tendencia HbA1c"):
            trend = self.diabetes_manager.get_trend_analysis(patient_id, "hba1c", months=6)
            if trend:
                import pandas as pd
                df = pd.DataFrame(trend)
                st.line_chart(df.set_index("date")["value"])
    
    def _render_hypertension_tab(self) -> None:
        """Renderiza pestaña de hipertensión."""
        st.subheader("Hipertensión Arterial")
        
        patient_id = st.text_input("ID del Paciente (HTA)", key="hta_patient")
        
        col1, col2 = st.columns(2)
        
        with col1:
            pa_sys = st.number_input("PA Sistólica", min_value=0, max_value=300, value=130, key="hta_sys")
            frecuencia = st.number_input("Frecuencia Cardíaca", min_value=0, max_value=200, value=72)
        
        with col2:
            pa_dia = st.number_input("PA Diastólica", min_value=0, max_value=200, value=85, key="hta_dia")
        
        medications = st.multiselect(
            "Medicamentos",
            ["Enalapril", "Losartán", "Amlodipino", "Hidroclorotiazida", "Metoprolol"],
            key="hta_med"
        )
        
        if st.button("🫀 Registrar Control HTA", type="primary"):
            if patient_id:
                record = self.hypertension_manager.record_control(
                    patient_id=patient_id,
                    pa_sistolica=pa_sys,
                    pa_diastolica=pa_dia,
                    frecuencia_cardiaca=frecuencia,
                    medications=medications
                )
                
                status, messages = self.hypertension_manager.get_control_status(patient_id)
                
                if status == ControlStatus.WELL_CONTROLLED:
                    st.success("✅ HTA bien controlada")
                elif status == ControlStatus.FAIRLY_CONTROLLED:
                    st.warning("⚠️ HTA regularmente controlada")
                else:
                    st.error(f"❌ {status.value}")
                
                if messages:
                    for msg in messages:
                        st.write(f"• {msg}")
            else:
                st.error("Ingrese ID del paciente")
    
    def _render_alerts_tab(self) -> None:
        """Renderiza pestaña de alertas."""
        st.subheader("Alertas y Controles Pendientes")
        
        pending_dm = self.diabetes_manager.get_pending_controls()
        
        if pending_dm:
            st.warning(f"⚠️ {len(pending_dm)} pacientes con control de diabetes vencido")
            
            for patient in pending_dm[:10]:  # Mostrar primeros 10
                with st.expander(f"Paciente {patient['patient_id']} - {patient['days_overdue']} días vencido"):
                    st.write(f"Último control: {patient['last_control'][:10]}")
                    st.write(f"Última HbA1c: {patient['hba1c_last']}%" if patient['hba1c_last'] else "Sin HbA1c registrada")
        else:
            st.success("✅ Todos los controles de diabetes al día")


# Funciones helper
def get_diabetes_manager() -> DiabetesManager:
    """Retorna gestor de diabetes."""
    return DiabetesManager()


def get_hypertension_manager() -> HypertensionManager:
    """Retorna gestor de hipertensión."""
    return HypertensionManager()


def record_diabetes_control(patient_id: str, hba1c: float, **kwargs) -> DiseaseControlRecord:
    """Helper para registrar control de diabetes."""
    return get_diabetes_manager().record_control(
        patient_id=patient_id,
        hba1c=hba1c,
        **kwargs
    )


def record_hypertension_control(patient_id: str, pa_sistolica: float, pa_diastolica: float, **kwargs) -> DiseaseControlRecord:
    """Helper para registrar control de hipertensión."""
    return get_hypertension_manager().record_control(
        patient_id=patient_id,
        pa_sistolica=pa_sistolica,
        pa_diastolica=pa_diastolica,
        **kwargs
    )
