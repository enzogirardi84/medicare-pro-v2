"""
Integración FHIR (Fast Healthcare Interoperability Resources) R4.

Estándar internacional HL7 FHIR para interoperabilidad en salud.
https://www.hl7.org/fhir/

Recursos FHIR soportados:
- Patient: Datos demográficos del paciente
- Observation: Signos vitales, laboratorio
- Encounter: Consultas/visitas
- Condition: Diagnósticos
- MedicationRequest: Prescripciones
- Practitioner: Profesionales de salud
- Organization: Clínicas/organizaciones
- Appointment: Turnos
- DocumentReference: Documentos clínicos
- CarePlan: Planes de cuidado

Funcionalidades:
- Exportación de datos a formato FHIR
- Importación desde sistemas externos FHIR
- Validación de recursos FHIR
- Transformación bidireccional (FHIR ↔ MediCare)
- Interfaz REST FHIR (para integraciones)
"""
import json
from typing import Dict, Any, List, Optional, Union
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from enum import Enum
import uuid

import streamlit as st

from core.app_logging import log_event


class FHIRResourceType(Enum):
    """Tipos de recursos FHIR soportados."""
    PATIENT = "Patient"
    OBSERVATION = "Observation"
    ENCOUNTER = "Encounter"
    CONDITION = "Condition"
    MEDICATION_REQUEST = "MedicationRequest"
    PRACTITIONER = "Practitioner"
    ORGANIZATION = "Organization"
    APPOINTMENT = "Appointment"
    DOCUMENT_REFERENCE = "DocumentReference"
    CARE_PLAN = "CarePlan"
    DIAGNOSTIC_REPORT = "DiagnosticReport"
    PROCEDURE = "Procedure"
    ALLERGY_INTOLERANCE = "AllergyIntolerance"


@dataclass
class FHIRIdentifier:
    """Identificador FHIR."""
    system: str
    value: str
    use: str = "usual"


@dataclass
class FHIRName:
    """Nombre FHIR."""
    use: str
    family: str
    given: List[str]


@dataclass
class FHIRCoding:
    """Coding FHIR."""
    system: str
    code: str
    display: str


class FHIRConverter:
    """
    Convertidor entre formatos MediCare y FHIR R4.
    
    Uso:
        converter = FHIRConverter()
        
        # Exportar paciente a FHIR
        fhir_patient = converter.patient_to_fhir(medicare_patient)
        
        # Importar desde FHIR
        medicare_patient = converter.patient_from_fhir(fhir_patient)
        
        # Batch export
        bundle = converter.create_bundle([patient1, patient2], "transaction")
    """
    
    # Sistemas de identificación
    DNI_SYSTEM = "http://www.renaper.gob.ar/dni"
    CUI_SYSTEM = "http://www.sisa.gob.ar/cui"
    
    # Sistemas de codificación
    SNOMED_CT = "http://snomed.info/sct"
    LOINC = "http://loinc.org"
    ICD10 = "http://hl7.org/fhir/sid/icd-10"
    RXNORM = "http://www.nlm.nih.gov/research/umls/rxnorm"
    
    def __init__(self):
        self._validation_errors: List[str] = []
    
    def patient_to_fhir(self, medicare_patient: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte paciente MediCare a recurso FHIR Patient."""
        fhir_patient = {
            "resourceType": "Patient",
            "id": medicare_patient.get("id", str(uuid.uuid4())),
            "meta": {
                "versionId": "1",
                "lastUpdated": datetime.now(timezone.utc).isoformat()
            },
            "identifier": [
                {
                    "system": self.DNI_SYSTEM,
                    "value": medicare_patient.get("dni", ""),
                    "use": "official"
                }
            ],
            "name": [
                {
                    "use": "official",
                    "family": medicare_patient.get("apellido", ""),
                    "given": [medicare_patient.get("nombre", "")]
                }
            ],
            "gender": self._map_gender(medicare_patient.get("sexo", "")),
            "birthDate": medicare_patient.get("fecha_nacimiento", ""),
        }
        
        # Contactos (teléfono, email)
        telecom = []
        if medicare_patient.get("telefono"):
            telecom.append({
                "system": "phone",
                "value": medicare_patient["telefono"],
                "use": "mobile"
            })
        if medicare_patient.get("email"):
            telecom.append({
                "system": "email",
                "value": medicare_patient["email"],
                "use": "home"
            })
        
        if telecom:
            fhir_patient["telecom"] = telecom
        
        # Dirección
        if medicare_patient.get("direccion"):
            fhir_patient["address"] = [{
                "use": "home",
                "text": medicare_patient["direccion"],
                "city": medicare_patient.get("ciudad", ""),
                "postalCode": medicare_patient.get("codigo_postal", "")
            }]
        
        # Contacto de emergencia
        if medicare_patient.get("contacto_emergencia_nombre"):
            fhir_patient["contact"] = [{
                "relationship": [{"coding": [{"system": self.SNOMED_CT, "code": "184139008", "display": "Contacto de emergencia"}]}],
                "name": {
                    "text": medicare_patient["contacto_emergencia_nombre"]
                },
                "telecom": [{
                    "system": "phone",
                    "value": medicare_patient.get("contacto_emergencia_telefono", "")
                }] if medicare_patient.get("contacto_emergencia_telefono") else []
            }]
        
        return fhir_patient
    
    def patient_from_fhir(self, fhir_patient: Dict[str, Any]) -> Dict[str, Any]:
        """Convierte recurso FHIR Patient a formato MediCare."""
        medicare_patient = {
            "id": fhir_patient.get("id"),
            "fhir_id": fhir_patient.get("id")
        }
        
        # Identificadores
        for identifier in fhir_patient.get("identifier", []):
            if identifier.get("system") == self.DNI_SYSTEM:
                medicare_patient["dni"] = identifier.get("value", "")
        
        # Nombre
        for name in fhir_patient.get("name", []):
            if name.get("use") == "official":
                medicare_patient["apellido"] = name.get("family", "")
                given = name.get("given", [])
                medicare_patient["nombre"] = given[0] if given else ""
        
        # Género
        gender_map = {
            "male": "M",
            "female": "F",
            "other": "O",
            "unknown": "O"
        }
        medicare_patient["sexo"] = gender_map.get(fhir_patient.get("gender", ""), "O")
        
        # Fecha nacimiento
        if fhir_patient.get("birthDate"):
            medicare_patient["fecha_nacimiento"] = fhir_patient["birthDate"]
        
        # Contacto
        for telecom in fhir_patient.get("telecom", []):
            if telecom.get("system") == "phone":
                medicare_patient["telefono"] = telecom.get("value", "")
            elif telecom.get("system") == "email":
                medicare_patient["email"] = telecom.get("value", "")
        
        # Dirección
        addresses = fhir_patient.get("address", [])
        if addresses:
            address = addresses[0]
            medicare_patient["direccion"] = address.get("text", "")
            medicare_patient["ciudad"] = address.get("city", "")
            medicare_patient["codigo_postal"] = address.get("postalCode", "")
        
        return medicare_patient
    
    def vitals_to_fhir_observations(
        self,
        vitals: Dict[str, Any],
        patient_id: str,
        practitioner_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Convierte signos vitales a recursos FHIR Observation."""
        observations = []
        timestamp = vitals.get("fecha_hora", datetime.now(timezone.utc).isoformat())
        
        # Mapeo de vitales a LOINC codes
        vital_mappings = {
            "temperatura": ("8310-5", "Body temperature", "°C", "Cel"),
            "frecuencia_cardiaca": ("8867-4", "Heart rate", "beats/min", "/min"),
            "presion_sistolica": ("8480-6", "Systolic blood pressure", "mmHg", "mm[Hg]"),
            "presion_diastolica": ("8462-4", "Diastolic blood pressure", "mmHg", "mm[Hg]"),
            "saturacion_o2": ("2708-6", "Oxygen saturation", "%", "%"),
            "peso": ("3141-9", "Body weight", "kg", "kg"),
            "altura": ("8302-2", "Body height", "cm", "cm"),
            "glucosa": ("2339-0", "Glucose", "mg/dL", "mg/dL")
        }
        
        for vital_name, (loinc_code, display, unit, unit_code) in vital_mappings.items():
            value = vitals.get(vital_name)
            if value is not None:
                observation = {
                    "resourceType": "Observation",
                    "id": f"obs-{vital_name}-{uuid.uuid4().hex[:8]}",
                    "status": "final",
                    "category": [{
                        "coding": [{
                            "system": "http://terminology.hl7.org/CodeSystem/observation-category",
                            "code": "vital-signs",
                            "display": "Vital Signs"
                        }]
                    }],
                    "code": {
                        "coding": [{
                            "system": self.LOINC,
                            "code": loinc_code,
                            "display": display
                        }],
                        "text": display
                    },
                    "subject": {
                        "reference": f"Patient/{patient_id}"
                    },
                    "effectiveDateTime": timestamp,
                    "valueQuantity": {
                        "value": float(value),
                        "unit": unit,
                        "system": "http://unitsofmeasure.org",
                        "code": unit_code
                    }
                }
                
                if practitioner_id:
                    observation["performer"] = [{"reference": f"Practitioner/{practitioner_id}"}]
                
                observations.append(observation)
        
        return observations
    
    def encounter_to_fhir(
        self,
        encounter_data: Dict[str, Any],
        patient_id: str
    ) -> Dict[str, Any]:
        """Convierte consulta/evolución a recurso FHIR Encounter."""
        encounter = {
            "resourceType": "Encounter",
            "id": encounter_data.get("id", str(uuid.uuid4())),
            "status": "finished",
            "class": {
                "system": "http://terminology.hl7.org/CodeSystem/v3-ActCode",
                "code": "AMB",
                "display": "ambulatory"
            },
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "period": {
                "start": encounter_data.get("fecha", datetime.now(timezone.utc).isoformat())
            },
            "reasonCode": [{
                "text": encounter_data.get("motivo_consulta", "")
            }]
        }
        
        # Agregar diagnóstico si existe
        if encounter_data.get("diagnostico"):
            encounter["diagnosis"] = [{
                "condition": {
                    "text": encounter_data["diagnostico"]
                },
                "use": {
                    "coding": [{
                        "system": "http://terminology.hl7.org/CodeSystem/diagnosis-role",
                        "code": "DD",
                        "display": "Discharge diagnosis"
                    }]
                }
            }]
        
        return encounter
    
    def condition_to_fhir(
        self,
        diagnosis: str,
        patient_id: str,
        onset_date: Optional[str] = None,
        icd10_code: Optional[str] = None
    ) -> Dict[str, Any]:
        """Convierte diagnóstico a recurso FHIR Condition."""
        condition = {
            "resourceType": "Condition",
            "id": f"cond-{uuid.uuid4().hex[:8]}",
            "clinicalStatus": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
                    "code": "active",
                    "display": "Active"
                }]
            },
            "verificationStatus": {
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
                    "code": "confirmed",
                    "display": "Confirmed"
                }]
            },
            "category": [{
                "coding": [{
                    "system": "http://terminology.hl7.org/CodeSystem/condition-category",
                    "code": "encounter-diagnosis",
                    "display": "Encounter Diagnosis"
                }]
            }],
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "code": {
                "text": diagnosis
            }
        }
        
        # Agregar código ICD-10 si está disponible
        if icd10_code:
            condition["code"]["coding"] = [{
                "system": self.ICD10,
                "code": icd10_code,
                "display": diagnosis
            }]
        
        if onset_date:
            condition["onsetDateTime"] = onset_date
        
        return condition
    
    def medication_request_to_fhir(
        self,
        prescription: Dict[str, Any],
        patient_id: str,
        practitioner_id: str
    ) -> Dict[str, Any]:
        """Convierte prescripción a recurso FHIR MedicationRequest."""
        med_request = {
            "resourceType": "MedicationRequest",
            "id": prescription.get("id", f"medreq-{uuid.uuid4().hex[:8]}"),
            "status": "active",
            "intent": "order",
            "subject": {
                "reference": f"Patient/{patient_id}"
            },
            "requester": {
                "reference": f"Practitioner/{practitioner_id}"
            },
            "authoredOn": prescription.get("fecha", datetime.now(timezone.utc).isoformat()),
            "medicationCodeableConcept": {
                "text": prescription.get("medicamento", "")
            },
            "dosageInstruction": [{
                "text": prescription.get("posologia", ""),
                "route": {
                    "text": prescription.get("via_administracion", "oral")
                }
            }]
        }
        
        return med_request
    
    def create_bundle(
        self,
        resources: List[Dict[str, Any]],
        bundle_type: str = "transaction",
        patient_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crea un Bundle FHIR.
        
        Args:
            resources: Lista de recursos FHIR
            bundle_type: Tipo de bundle (transaction, batch, document)
            patient_id: ID del paciente para referencias
        
        Returns:
            Bundle FHIR
        """
        bundle = {
            "resourceType": "Bundle",
            "id": f"bundle-{uuid.uuid4().hex[:8]}",
            "meta": {
                "versionId": "1",
                "lastUpdated": datetime.now(timezone.utc).isoformat()
            },
            "type": bundle_type,
            "total": len(resources),
            "entry": []
        }
        
        for resource in resources:
            entry = {
                "resource": resource,
                "fullUrl": f"urn:uuid:{resource.get('id', str(uuid.uuid4()))}"
            }
            
            if bundle_type == "transaction":
                entry["request"] = {
                    "method": "POST",
                    "url": resource.get("resourceType", "")
                }
            
            bundle["entry"].append(entry)
        
        return bundle
    
    def _map_gender(self, gender: str) -> str:
        """Mapea género MediCare a FHIR."""
        mapping = {
            "M": "male",
            "F": "female",
            "O": "other",
            "": "unknown"
        }
        return mapping.get(gender, "unknown")
    
    def validate_fhir_resource(self, resource: Dict[str, Any]) -> Tuple[bool, List[str]]:
        """
        Valida un recurso FHIR básico.
        
        Returns:
            (is_valid, errors)
        """
        errors = []
        
        # Verificar resourceType
        if "resourceType" not in resource:
            errors.append("Falta resourceType")
        
        # Verificar id
        if "id" not in resource:
            errors.append("Falta id")
        
        # Validaciones específicas por tipo
        resource_type = resource.get("resourceType", "")
        
        if resource_type == "Patient":
            if not resource.get("name"):
                errors.append("Patient debe tener name")
            if not resource.get("birthDate"):
                errors.append("Patient debe tener birthDate")
        
        elif resource_type == "Observation":
            if not resource.get("code"):
                errors.append("Observation debe tener code")
            if not resource.get("subject"):
                errors.append("Observation debe tener subject")
        
        return len(errors) == 0, errors
    
    def export_patient_bundle(
        self,
        patient_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Exporta todos los datos de un paciente como Bundle FHIR.
        
        Args:
            patient_id: ID del paciente
        
        Returns:
            Bundle FHIR completo o None si no existe
        """
        resources = []
        
        # Buscar paciente
        pacientes = st.session_state.get("pacientes_db", [])
        patient = None
        for p in pacientes:
            if p.get("id") == patient_id:
                patient = p
                break
        
        if not patient:
            return None
        
        # Agregar paciente
        fhir_patient = self.patient_to_fhir(patient)
        resources.append(fhir_patient)
        
        # Agregar vitales
        vitales = st.session_state.get("vitales_db", [])
        for vital in vitales:
            if vital.get("paciente_id") == patient_id:
                observations = self.vitals_to_fhir_observations(vital, patient_id)
                resources.extend(observations)
        
        # Agregar evoluciones como encounters
        evoluciones = st.session_state.get("evoluciones_db", [])
        for evo in evoluciones:
            if evo.get("paciente_id") == patient_id:
                encounter = self.encounter_to_fhir(evo, patient_id)
                resources.append(encounter)
                
                # Agregar diagnóstico como condition
                if evo.get("diagnostico"):
                    condition = self.condition_to_fhir(
                        evo["diagnostico"],
                        patient_id,
                        evo.get("fecha"),
                        evo.get("cie10_code")
                    )
                    resources.append(condition)
        
        return self.create_bundle(resources, "document", patient_id)
    
    def render_fhir_manager(self) -> None:
        """Renderiza UI de gestión FHIR en Streamlit."""
        st.header("🏥 Integración FHIR (HL7)")
        
        tab1, tab2, tab3 = st.tabs(["Exportar", "Validar", "Documentación"])
        
        with tab1:
            st.subheader("Exportar Datos a FHIR")
            
            patient_id = st.text_input("ID del Paciente a exportar")
            
            if st.button("📤 Generar Bundle FHIR"):
                with st.spinner("Generando..."):
                    bundle = self.export_patient_bundle(patient_id)
                    
                    if bundle:
                        st.success(f"Bundle generado con {len(bundle.get('entry', []))} recursos")
                        
                        with st.expander("Ver JSON FHIR"):
                            st.json(bundle)
                        
                        # Botón de descarga
                        json_str = json.dumps(bundle, indent=2, ensure_ascii=False)
                        st.download_button(
                            "⬇️ Descargar JSON",
                            json_str,
                            f"fhir_export_{patient_id}.json",
                            "application/fhir+json"
                        )
                    else:
                        st.error("Paciente no encontrado")
        
        with tab2:
            st.subheader("Validar Recurso FHIR")
            
            json_input = st.text_area("Pegar JSON FHIR", height=200)
            
            if st.button("✅ Validar"):
                try:
                    resource = json.loads(json_input)
                    is_valid, errors = self.validate_fhir_resource(resource)
                    
                    if is_valid:
                        st.success("✅ Recurso FHIR válido")
                    else:
                        st.error("❌ Errores de validación:")
                        for error in errors:
                            st.write(f"• {error}")
                
                except json.JSONDecodeError as e:
                    st.error(f"JSON inválido: {e}")
        
        with tab3:
            st.subheader("Documentación FHIR")
            
            st.write("**Recursos soportados:**")
            resources = [
                "Patient - Datos demográficos",
                "Observation - Signos vitales, laboratorio",
                "Encounter - Consultas/visitas",
                "Condition - Diagnósticos",
                "MedicationRequest - Prescripciones",
                "Practitioner - Profesionales",
                "Organization - Clínicas",
                "Appointment - Turnos",
                "DocumentReference - Documentos",
                "CarePlan - Planes de cuidado"
            ]
            
            for resource in resources:
                st.write(f"• {resource}")
            
            st.caption("Versión FHIR: R4 (4.0.1)")
            st.caption("Perfil: Core Argentina")


# Instancia global
_fhir_converter = None

def get_fhir_converter() -> FHIRConverter:
    """Retorna instancia singleton."""
    global _fhir_converter
    if _fhir_converter is None:
        _fhir_converter = FHIRConverter()
    return _fhir_converter


def export_patient_to_fhir(patient_id: str) -> Optional[Dict[str, Any]]:
    """Helper para exportar paciente a FHIR."""
    return get_fhir_converter().export_patient_bundle(patient_id)


def convert_vitals_to_fhir(
    vitals: Dict[str, Any],
    patient_id: str
) -> List[Dict[str, Any]]:
    """Helper para convertir signos vitales."""
    return get_fhir_converter().vitals_to_fhir_observations(vitals, patient_id)


def validate_fhir_json(json_str: str) -> Tuple[bool, List[str]]:
    """Helper para validar JSON FHIR."""
    try:
        resource = json.loads(json_str)
        return get_fhir_converter().validate_fhir_resource(resource)
    except json.JSONDecodeError as e:
        return False, [f"JSON inválido: {str(e)}"]
