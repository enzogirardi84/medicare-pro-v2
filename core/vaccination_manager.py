"""
Sistema de Gestión de Vacunación para MediCare Pro.

Calendarios soportados:
- Nacional (Argentina - Ministerio de Salud)
- OMS (Organización Mundial de la Salud)
- CDC (Centers for Disease Control - USA)
- Personalizado por clínica

Características:
- Calendario de vacunación por edad
- Alertas de vacunas próximas/vencidas
- Registro de vacunas aplicadas
- Control de dosis (primeras, segundas, refuerzos)
- Lotes y vencimientos
- Contraindicaciones y precauciones
- Certificado de vacunación digital
- Integración con historial clínico

Alertas automáticas:
- Vacunas pendientes por edad
- Segundas dosis próximas
- Refuerzos vencidos
- Campañas de vacunación
"""
import json
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone, timedelta
from enum import Enum, auto
from collections import defaultdict

import streamlit as st

from core.app_logging import log_event
from core.realtime_notifications import send_appointment_reminder, NotificationPriority


class VaccineType(Enum):
    """Tipos de vacunas."""
    BCG = "BCG"  # Tuberculosis
    HEPATITIS_B = "Hepatitis B"
    PENTAVALENTE = "Pentavalente"  # DTP + Hib + Hep B
    POLIO = "Polio"  # IPV/OPV
    NEUMOCOCO = "Neumococo"
    ROTAVIRUS = "Rotavirus"
    MENINGOCOCO = "Meningococo"
    TRIPLE_VIRAL = "Triple Viral"  # Sarampión, Rubeola, Paperas
    VARICELA = "Varicela"
    HEPATITIS_A = "Hepatitis A"
    DTP = "DTP"  # Difteria, Tétanos, Tos Ferina
    HPV = "HPV"  # Virus Papiloma Humano
    FIEBRE_AMARILLA = "Fiebre Amarilla"
    COVID19 = "COVID-19"
    INFLUENZA = "Influenza"
    NEUMONIA = "Neumonía"
    HERPES_ZOSTER = "Herpes Zoster"
    TETANOS = "Tétanos"
    HEPATITIS_B_ADULTO = "Hepatitis B (Adulto)"
    FIEBRE_TIFOIDEA = "Fiebre Tifoidea"
    RABIA = "Rabia"
    OTRA = "Otra"


class DoseType(Enum):
    """Tipos de dosis."""
    PRIMERA = "1ª dosis"
    SEGUNDA = "2ª dosis"
    TERCERA = "3ª dosis"
    REFUERZO = "Refuerzo"
    ANUAL = "Anual"
    UNICA = "Única"


class ScheduleType(Enum):
    """Tipos de calendario."""
    NACIONAL_ARGENTINA = "nacional_argentina"
    OMS = "oms"
    CDC = "cdc"
    PERSONALIZADO = "personalizado"


@dataclass
class VaccineDose:
    """Dosis específica de una vacuna."""
    dose_type: str  # DoseType.value
    age_months: int  # Edad en meses recomendada
    age_range: Tuple[int, int]  # (min, max) meses
    is_mandatory: bool
    contraindications: List[str] = field(default_factory=list)
    notes: Optional[str] = None


@dataclass
class VaccineSchedule:
    """Vacuna con su calendario de dosis."""
    vaccine_type: str
    name: str
    description: str
    doses: List[VaccineDose]
    requires_booster: bool
    booster_interval_months: Optional[int] = None
    special_populations: List[str] = field(default_factory=list)
    diseases_protected: List[str] = field(default_factory=list)


@dataclass
class VaccinationRecord:
    """Registro de vacuna aplicada."""
    record_id: str
    patient_id: str
    vaccine_type: str
    dose_type: str
    date_applied: str
    lot_number: str
    expiration_date: str
    manufacturer: str
    health_professional: str
    establishment: str
    side_effects: List[str] = field(default_factory=list)
    next_dose_due: Optional[str] = None
    certificate_generated: bool = False
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class VaccinationCalendar:
    """Calendario de vacunación configurado."""
    
    # Calendario Nacional de Vacunación - Argentina (2024)
    NATIONAL_SCHEDULE = {
        VaccineType.BCG: VaccineSchedule(
            vaccine_type=VaccineType.BCG.value,
            name="BCG",
            description="Vacuna contra tuberculosis",
            doses=[
                VaccineDose(
                    dose_type=DoseType.UNICA.value,
                    age_months=0,
                    age_range=(0, 12),
                    is_mandatory=True,
                    contraindications=["Inmunodeficiencia primaria"]
                )
            ],
            requires_booster=False,
            diseases_protected=["Tuberculosis meníngea y miliar"]
        ),
        
        VaccineType.HEPATITIS_B: VaccineSchedule(
            vaccine_type=VaccineType.HEPATITIS_B.value,
            name="Hepatitis B",
            description="Vacuna contra hepatitis B",
            doses=[
                VaccineDose(
                    dose_type=DoseType.PRIMERA.value,
                    age_months=0,
                    age_range=(0, 2),
                    is_mandatory=True
                ),
                VaccineDose(
                    dose_type=DoseType.SEGUNDA.value,
                    age_months=2,
                    age_range=(2, 4),
                    is_mandatory=True
                ),
                VaccineDose(
                    dose_type=DoseType.TERCERA.value,
                    age_months=6,
                    age_range=(6, 8),
                    is_mandatory=True
                )
            ],
            requires_booster=False,
            diseases_protected=["Hepatitis B"]
        ),
        
        VaccineType.PENTAVALENTE: VaccineSchedule(
            vaccine_type=VaccineType.PENTAVALENTE.value,
            name="Pentavalente",
            description="DTP + Hib + Hepatitis B",
            doses=[
                VaccineDose(
                    dose_type=DoseType.PRIMERA.value,
                    age_months=2,
                    age_range=(2, 3),
                    is_mandatory=True
                ),
                VaccineDose(
                    dose_type=DoseType.SEGUNDA.value,
                    age_months=4,
                    age_range=(4, 5),
                    is_mandatory=True
                ),
                VaccineDose(
                    dose_type=DoseType.TERCERA.value,
                    age_months=6,
                    age_range=(6, 7),
                    is_mandatory=True
                )
            ],
            requires_booster=True,
            booster_interval_months=15,  # Refuerzo a los 15-18 meses
            diseases_protected=["Difteria", "Tétanos", "Tos Ferina", "Hib", "Hepatitis B"]
        ),
        
        VaccineType.POLIO: VaccineSchedule(
            vaccine_type=VaccineType.POLIO.value,
            name="Polio (IPV)",
            description="Vacuna inactivada contra poliomielitis",
            doses=[
                VaccineDose(
                    dose_type=DoseType.PRIMERA.value,
                    age_months=2,
                    age_range=(2, 3),
                    is_mandatory=True
                ),
                VaccineDose(
                    dose_type=DoseType.SEGUNDA.value,
                    age_months=4,
                    age_range=(4, 5),
                    is_mandatory=True
                ),
                VaccineDose(
                    dose_type=DoseType.TERCERA.value,
                    age_months=6,
                    age_range=(6, 7),
                    is_mandatory=True
                )
            ],
            requires_booster=True,
            booster_interval_months=15,
            diseases_protected=["Poliomielitis"]
        ),
        
        VaccineType.NEUMOCOCO: VaccineSchedule(
            vaccine_type=VaccineType.NEUMOCOCO.value,
            name="Neumococo conjugada",
            description="Vacuna contra Streptococcus pneumoniae",
            doses=[
                VaccineDose(
                    dose_type=DoseType.PRIMERA.value,
                    age_months=2,
                    age_range=(2, 3),
                    is_mandatory=False  # Opcional pero recomendada
                ),
                VaccineDose(
                    dose_type=DoseType.SEGUNDA.value,
                    age_months=4,
                    age_range=(4, 5),
                    is_mandatory=False
                ),
                VaccineDose(
                    dose_type=DoseType.TERCERA.value,
                    age_months=12,
                    age_range=(12, 15),
                    is_mandatory=False
                )
            ],
            requires_booster=False,
            special_populations=["Prematuros", "Asplénicos"],
            diseases_protected=["Neumonía", "Meningitis", "Sepsis por neumococo"]
        ),
        
        VaccineType.TRIPLE_VIRAL: VaccineSchedule(
            vaccine_type=VaccineType.TRIPLE_VIRAL.value,
            name="Triple Viral (SPR)",
            description="Sarampión, Paperas, Rubeola",
            doses=[
                VaccineDose(
                    dose_type=DoseType.PRIMERA.value,
                    age_months=12,
                    age_range=(12, 15),
                    is_mandatory=True,
                    contraindications=["Embarazo", "Inmunosupresión severa"]
                ),
                VaccineDose(
                    dose_type=DoseType.SEGUNDA.value,
                    age_months=60,  # 5 años
                    age_range=(60, 72),
                    is_mandatory=True
                )
            ],
            requires_booster=False,
            diseases_protected=["Sarampión", "Paperas", "Rubeola"]
        ),
        
        VaccineType.VARICELA: VaccineSchedule(
            vaccine_type=VaccineType.VARICELA.value,
            name="Varicela",
            description="Vacuna contra varicela",
            doses=[
                VaccineDose(
                    dose_type=DoseType.PRIMERA.value,
                    age_months=15,
                    age_range=(15, 18),
                    is_mandatory=True,
                    contraindications=["Embarazo", "Inmunosupresión severa"]
                ),
                VaccineDose(
                    dose_type=DoseType.SEGUNDA.value,
                    age_months=60,
                    age_range=(60, 72),
                    is_mandatory=True
                )
            ],
            requires_booster=False,
            diseases_protected=["Varicela"]
        ),
        
        VaccineType.COVID19: VaccineSchedule(
            vaccine_type=VaccineType.COVID19.value,
            name="COVID-19",
            description="Vacuna contra SARS-CoV-2",
            doses=[
                VaccineDose(
                    dose_type=DoseType.PRIMERA.value,
                    age_months=72,  # 6 años+
                    age_range=(72, 1200),
                    is_mandatory=False
                ),
                VaccineDose(
                    dose_type=DoseType.SEGUNDA.value,
                    age_months=72,
                    age_range=(72, 1200),
                    is_mandatory=False
                ),
                VaccineDose(
                    dose_type=DoseType.REFUERZO.value,
                    age_months=78,
                    age_range=(78, 1200),
                    is_mandatory=False
                )
            ],
            requires_booster=True,
            booster_interval_months=6,
            special_populations=["Personal de salud", "Adultos mayores", "Comorbilidades"],
            diseases_protected=["COVID-19"]
        ),
        
        VaccineType.INFLUENZA: VaccineSchedule(
            vaccine_type=VaccineType.INFLUENZA.value,
            name="Influenza",
            description="Vacuna antigripal anual",
            doses=[
                VaccineDose(
                    dose_type=DoseType.ANUAL.value,
                    age_months=6,
                    age_range=(6, 1200),
                    is_mandatory=False,
                    notes="Vacunación anual antes del invierno"
                )
            ],
            requires_booster=True,
            booster_interval_months=12,
            special_populations=["Adultos mayores", "Embarazadas", "Personal de salud"],
            diseases_protected=["Influenza"]
        )
    }
    
    def __init__(self, schedule_type: ScheduleType = ScheduleType.NACIONAL_ARGENTINA):
        self.schedule_type = schedule_type
        self._schedules: Dict[VaccineType, VaccineSchedule] = {}
        self._load_schedule()
    
    def _load_schedule(self) -> None:
        """Carga el calendario según el tipo."""
        if self.schedule_type == ScheduleType.NACIONAL_ARGENTINA:
            self._schedules = self.NATIONAL_SCHEDULE.copy()
        elif self.schedule_type == ScheduleType.OMS:
            # En producción: cargar calendario OMS
            self._schedules = self.NATIONAL_SCHEDULE.copy()  # Fallback
        elif self.schedule_type == ScheduleType.CDC:
            # En producción: cargar calendario CDC
            self._schedules = self.NATIONAL_SCHEDULE.copy()  # Fallback
    
    def get_vaccines_for_age(self, age_months: int) -> List[VaccineSchedule]:
        """Obtiene vacunas recomendadas para una edad."""
        result = []
        
        for vaccine_schedule in self._schedules.values():
            for dose in vaccine_schedule.doses:
                min_age, max_age = dose.age_range
                if min_age <= age_months <= max_age:
                    result.append(vaccine_schedule)
                    break  # Evitar duplicados si múltiples dosis aplican
        
        return result
    
    def get_pending_doses(
        self,
        age_months: int,
        applied_vaccines: List[VaccinationRecord]
    ) -> List[Tuple[VaccineSchedule, VaccineDose]]:
        """Obtiene dosis pendientes para un paciente."""
        pending = []
        applied_keys = {(v.vaccine_type, v.dose_type) for v in applied_vaccines}
        
        for vaccine_schedule in self._schedules.values():
            for dose in vaccine_schedule.doses:
                # Verificar si la dosis ya fue aplicada
                key = (vaccine_schedule.vaccine_type, dose.dose_type)
                if key in applied_keys:
                    continue
                
                # Verificar si está en edad de aplicar
                min_age, max_age = dose.age_range
                if age_months >= min_age:  # Ya cumplió edad mínima
                    pending.append((vaccine_schedule, dose))
        
        return pending


class VaccinationManager:
    """
    Gestor de vacunación de pacientes.
    
    Uso:
        manager = VaccinationManager()
        
        # Registrar vacuna aplicada
        record = manager.record_vaccination(
            patient_id="pat-123",
            vaccine_type=VaccineType.PENTAVALENTE,
            dose_type=DoseType.PRIMERA,
            lot_number="LOT202401",
            health_professional="Dr. García"
        )
        
        # Verificar vacunas pendientes
        pending = manager.get_patient_pending_vaccines("pat-123", age_months=6)
    """
    
    def __init__(self, calendar: Optional[VaccinationCalendar] = None):
        self.calendar = calendar or VaccinationCalendar()
        self._records: Dict[str, List[VaccinationRecord]] = {}  # patient_id -> records
        self._load_records()
    
    def _load_records(self) -> None:
        """Carga registros de vacunación."""
        if "vaccination_records" in st.session_state:
            records_data = st.session_state["vaccination_records"]
            for patient_id, records in records_data.items():
                self._records[patient_id] = [VaccinationRecord(**r) for r in records]
    
    def _save_records(self) -> None:
        """Guarda registros de vacunación."""
        st.session_state["vaccination_records"] = {
            patient_id: [r.to_dict() for r in records]
            for patient_id, records in self._records.items()
        }
    
    def record_vaccination(
        self,
        patient_id: str,
        vaccine_type: VaccineType,
        dose_type: DoseType,
        lot_number: str,
        expiration_date: str,
        manufacturer: str,
        health_professional: str,
        establishment: str = "Clínica Principal",
        side_effects: Optional[List[str]] = None
    ) -> VaccinationRecord:
        """
        Registra una vacuna aplicada.
        
        Returns:
            VaccinationRecord creado
        """
        # Generar ID único
        record_id = f"vacc-{datetime.now(timezone.utc).timestamp()}-{hash(patient_id) % 10000}"
        
        # Calcular próxima dosis si aplica
        next_dose = None
        schedule = self.calendar._schedules.get(vaccine_type)
        if schedule:
            for i, dose in enumerate(schedule.doses):
                if dose.dose_type == dose_type.value and i + 1 < len(schedule.doses):
                    next_dose_info = schedule.doses[i + 1]
                    # Calcular fecha estimada basada en edad
                    next_dose = (datetime.now(timezone.utc) + 
                                timedelta(days=30*(next_dose_info.age_months - dose.age_months))).isoformat()
                    break
        
        record = VaccinationRecord(
            record_id=record_id,
            patient_id=patient_id,
            vaccine_type=vaccine_type.value,
            dose_type=dose_type.value,
            date_applied=datetime.now(timezone.utc).isoformat(),
            lot_number=lot_number,
            expiration_date=expiration_date,
            manufacturer=manufacturer,
            health_professional=health_professional,
            establishment=establishment,
            side_effects=side_effects or [],
            next_dose_due=next_dose,
            certificate_generated=False
        )
        
        # Guardar
        if patient_id not in self._records:
            self._records[patient_id] = []
        
        self._records[patient_id].append(record)
        self._save_records()
        
        log_event("vaccination", f"recorded:{vaccine_type.value}:{dose_type.value}:{patient_id}")
        
        return record
    
    def get_patient_vaccination_history(
        self,
        patient_id: str
    ) -> List[VaccinationRecord]:
        """Obtiene historial de vacunación de un paciente."""
        return sorted(
            self._records.get(patient_id, []),
            key=lambda r: r.date_applied,
            reverse=True
        )
    
    def get_patient_pending_vaccines(
        self,
        patient_id: str,
        age_months: int,
        birth_date: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Obtiene vacunas pendientes para un paciente.
        
        Returns:
            Lista de vacunas pendientes con urgencia
        """
        applied = self._records.get(patient_id, [])
        pending_doses = self.calendar.get_pending_doses(age_months, applied)
        
        result = []
        for vaccine_schedule, dose in pending_doses:
            # Calcular urgencia
            min_age, max_age = dose.age_range
            urgency = "normal"
            
            if age_months > max_age:
                urgency = "overdue"  # Vencida
            elif age_months >= min_age:
                urgency = "due"  # Ya se puede aplicar
            
            days_overdue = max(0, (age_months - max_age) * 30) if age_months > max_age else 0
            
            result.append({
                "vaccine_type": vaccine_schedule.vaccine_type,
                "vaccine_name": vaccine_schedule.name,
                "dose_type": dose.dose_type,
                "age_recommended_months": dose.age_months,
                "age_current_months": age_months,
                "is_mandatory": dose.is_mandatory,
                "urgency": urgency,
                "days_overdue": days_overdue,
                "contraindications": dose.contraindications,
                "notes": dose.notes,
                "diseases_protected": vaccine_schedule.diseases_protected
            })
        
        # Ordenar por urgencia y obligatoriedad
        urgency_order = {"overdue": 0, "due": 1, "normal": 2}
        result.sort(key=lambda x: (
            urgency_order.get(x["urgency"], 3),
            not x["is_mandatory"],
            x["age_recommended_months"]
        ))
        
        return result
    
    def generate_vaccination_certificate(
        self,
        patient_id: str,
        patient_name: str
    ) -> Dict[str, Any]:
        """Genera certificado de vacunación digital."""
        records = self.get_patient_vaccination_history(patient_id)
        
        certificate = {
            "certificate_id": f"cert-vacc-{patient_id}-{datetime.now(timezone.utc).strftime('%Y%m%d')}",
            "patient_id": patient_id,
            "patient_name": patient_name,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "valid_from": datetime.now(timezone.utc).isoformat(),
            "valid_until": (datetime.now(timezone.utc) + timedelta(days=365)).isoformat(),
            "vaccines": []
        }
        
        for record in records:
            vaccine_info = {
                "vaccine": record.vaccine_type,
                "dose": record.dose_type,
                "date": record.date_applied,
                "lot": record.lot_number,
                "professional": record.health_professional,
                "establishment": record.establishment
            }
            certificate["vaccines"].append(vaccine_info)
            
            # Marcar como certificado generado
            record.certificate_generated = True
        
        self._save_records()
        
        log_event("vaccination", f"certificate_generated:{patient_id}")
        
        return certificate
    
    def check_vaccination_alerts(
        self,
        patient_id: str,
        age_months: int
    ) -> List[Dict[str, Any]]:
        """Verifica y genera alertas de vacunación."""
        pending = self.get_patient_pending_vaccines(patient_id, age_months)
        alerts = []
        
        for vaccine in pending:
            if vaccine["urgency"] in ["overdue", "due"] and vaccine["is_mandatory"]:
                alerts.append({
                    "type": "vaccination_due",
                    "priority": "high" if vaccine["urgency"] == "overdue" else "medium",
                    "vaccine": vaccine["vaccine_name"],
                    "dose": vaccine["dose_type"],
                    "message": f"Vacuna {vaccine['vaccine_name']} ({vaccine['dose_type']}) {'vencida' if vaccine['urgency'] == 'overdue' else 'pendiente'}",
                    "days_overdue": vaccine["days_overdue"],
                    "action_required": True
                })
        
        return alerts
    
    def render_vaccination_dashboard(self) -> None:
        """Renderiza dashboard de vacunación en Streamlit."""
        st.header("💉 Sistema de Vacunación")
        
        tab1, tab2, tab3 = st.tabs(["Registro", "Calendario", "Certificado"])
        
        with tab1:
            st.subheader("Registrar Vacuna")
            
            patient_id = st.text_input("ID del Paciente")
            
            col1, col2 = st.columns(2)
            with col1:
                vaccine_options = {v.value: v.value for v in VaccineType}
                selected_vaccine = st.selectbox("Vacuna", options=list(vaccine_options.keys()))
                dose_options = {d.value: d.value for d in DoseType}
                selected_dose = st.selectbox("Dosis", options=list(dose_options.keys()))
            
            with col2:
                lot_number = st.text_input("Lote", "LOT-2024-001")
                expiration = st.date_input("Vencimiento", datetime.now(timezone.utc) + timedelta(days=365))
                manufacturer = st.text_input("Fabricante", "Laboratorio XYZ")
            
            professional = st.text_input("Profesional que aplica", "Dr. García")
            
            if st.button("💉 Registrar Vacuna", type="primary"):
                if patient_id:
                    record = self.record_vaccination(
                        patient_id=patient_id,
                        vaccine_type=VaccineType(selected_vaccine),
                        dose_type=DoseType(selected_dose),
                        lot_number=lot_number,
                        expiration_date=expiration.isoformat(),
                        manufacturer=manufacturer,
                        health_professional=professional
                    )
                    st.success(f"Vacuna registrada: {record.record_id}")
                    
                    # Mostrar alertas si hay próximas dosis
                    if record.next_dose_due:
                        st.info(f"📅 Próxima dosis estimada: {record.next_dose_due[:10]}")
                else:
                    st.error("Ingrese ID del paciente")
        
        with tab2:
            st.subheader("Calendario de Vacunación")
            
            patient_id_cal = st.text_input("ID del Paciente (para verificar)")
            age_months = st.number_input("Edad (meses)", min_value=0, max_value=1200, value=6)
            
            if st.button("🔍 Verificar Vacunas Pendientes"):
                if patient_id_cal:
                    pending = self.get_patient_pending_vaccines(patient_id_cal, age_months)
                    
                    if not pending:
                        st.success("✅ Todas las vacunas al día")
                    else:
                        for vaccine in pending:
                            urgency_icon = "🔴" if vaccine["urgency"] == "overdue" else "🟡" if vaccine["urgency"] == "due" else "⚪"
                            mandatory_icon = "📌" if vaccine["is_mandatory"] else ""
                            
                            with st.expander(f"{urgency_icon} {mandatory_icon} {vaccine['vaccine_name']} - {vaccine['dose_type']}"):
                                st.write(f"**Edad recomendada:** {vaccine['age_recommended_months']} meses")
                                st.write(f"**Edad actual:** {vaccine['age_current_months']} meses")
                                
                                if vaccine["days_overdue"] > 0:
                                    st.error(f"⚠️ Vencida hace {vaccine['days_overdue']} días")
                                
                                st.write(f"**Protege contra:** {', '.join(vaccine['diseases_protected'])}")
                                
                                if vaccine["contraindications"]:
                                    st.warning(f"**Contraindicaciones:** {', '.join(vaccine['contraindications'])}")
                else:
                    st.error("Ingrese ID del paciente")
        
        with tab3:
            st.subheader("Certificado de Vacunación")
            
            patient_id_cert = st.text_input("ID del Paciente (certificado)")
            patient_name = st.text_input("Nombre del Paciente")
            
            if st.button("📜 Generar Certificado"):
                if patient_id_cert and patient_name:
                    cert = self.generate_vaccination_certificate(patient_id_cert, patient_name)
                    
                    st.success(f"Certificado generado: {cert['certificate_id']}")
                    
                    with st.expander("Ver certificado"):
                        st.json(cert)
                    
                    # Botón de descarga
                    json_str = json.dumps(cert, indent=2, ensure_ascii=False)
                    st.download_button(
                        "⬇️ Descargar Certificado",
                        json_str,
                        f"certificado_vacunacion_{patient_id_cert}.json",
                        "application/json"
                    )
                else:
                    st.error("Complete ID y nombre del paciente")


# Instancia global
_vaccination_manager = None

def get_vaccination_manager() -> VaccinationManager:
    """Retorna instancia singleton."""
    global _vaccination_manager
    if _vaccination_manager is None:
        _vaccination_manager = VaccinationManager()
    return _vaccination_manager


def record_patient_vaccination(
    patient_id: str,
    vaccine_type: VaccineType,
    dose_type: DoseType,
    lot_number: str,
    expiration_date: str,
    manufacturer: str,
    health_professional: str
) -> VaccinationRecord:
    """Helper para registrar vacuna."""
    return get_vaccination_manager().record_vaccination(
        patient_id=patient_id,
        vaccine_type=vaccine_type,
        dose_type=dose_type,
        lot_number=lot_number,
        expiration_date=expiration_date,
        manufacturer=manufacturer,
        health_professional=health_professional
    )


def check_patient_vaccination_status(
    patient_id: str,
    age_months: int
) -> List[Dict[str, Any]]:
    """Helper para verificar estado de vacunación."""
    return get_vaccination_manager().get_patient_pending_vaccines(patient_id, age_months)
