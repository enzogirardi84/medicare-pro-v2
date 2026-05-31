"""Traductor de datos clinicos a formato FHIR (HL7 Fast Healthcare
Interoperability Resources). Transforma registros de evoluciones,
pacientes y administracion de medicamentos a recursos FHIR R4 JSON.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, Field

from core.app_logging import log_event


# ═══════════════════════════════════════════════════════════════════
# 1. RECURSOS FHIR R4
# ═══════════════════════════════════════════════════════════════════

class FHIRPatient(BaseModel):
    """Recurso FHIR Patient (R4)."""
    resourceType: str = "Patient"
    id: str = ""
    identifier: list[dict] = []
    name: list[dict] = []
    gender: str = ""
    birthDate: str = ""
    address: list[dict] = []


class FHIRObservation(BaseModel):
    """Recurso FHIR Observation (evolucion clinica)."""
    resourceType: str = "Observation"
    id: str = ""
    status: str = "final"
    code: dict = {}
    subject: dict = {}
    effectiveDateTime: str = ""
    valueString: str = ""
    note: list[dict] = []


class FHIRMedicationAdministration(BaseModel):
    """Recurso FHIR MedicationAdministration (R4)."""
    resourceType: str = "MedicationAdministration"
    id: str = ""
    status: str = "completed"
    medicationCodeableConcept: dict = {}
    subject: dict = {}
    effectiveDateTime: str = ""
    dosage: dict = {}


# ═══════════════════════════════════════════════════════════════════
# 2. ADAPTADORES DE TRANSFORMACION
# ═══════════════════════════════════════════════════════════════════

class FHIRAdapter:
    """Convierte registros de MediCare a recursos FHIR R4.

    Uso:
        adapter = FHIRAdapter()
        fhir_json = adapter.paciente_a_fhir(paciente_dict)
        fhir_json = adapter.evolucion_a_fhir(evolucion_dict)
    """

    # Mapeo de diagnosticos a codigos SNOMED CT
    SNOMED_MAP = {
        "neumonia": {"code": "233604007", "display": "Neumonia"},
        "fractura": {"code": "125605004", "display": "Fractura"},
        "diabetes": {"code": "73211009", "display": "Diabetes mellitus"},
        "hipertension": {"code": "38341003", "display": "Hipertension arterial"},
        "gripe": {"code": "6142004", "display": "Influenza"},
    }

    @staticmethod
    def _generate_id() -> str:
        return str(uuid.uuid4())

    @staticmethod
    def _snomed(code: str) -> dict:
        """Busca codigo SNOMED CT para un diagnostico."""
        mapping = FHIRAdapter.SNOMED_MAP.get(code.lower().strip(), {})
        if mapping:
            return {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": mapping["code"],
                    "display": mapping["display"],
                }]
            }
        return {"text": code}

    # ── Paciente → FHIR Patient ─────────────────────────────

    @staticmethod
    def paciente_a_fhir(paciente: dict[str, Any]) -> dict:
        """Convierte un paciente a recurso FHIR Patient."""
        resource = {
            "resourceType": "Patient",
            "id": str(paciente.get("id", FHIRAdapter._generate_id())),
            "identifier": [{
                "system": "https://medicare-pro.app/identifiers/dni",
                "value": str(paciente.get("dni", "")),
            }],
            "name": [{
                "use": "official",
                "text": str(paciente.get("nombre", "")),
            }],
            "gender": paciente.get("genero", "unknown"),
            "birthDate": str(paciente.get("fecha_nacimiento", "") or "")[:10],
            "address": [{
                "text": str(paciente.get("direccion", "")),
            }],
            "generalPractitioner": [{
                "identifier": {"value": str(paciente.get("medico_cabecera", ""))},
            }],
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/Patient"],
                "lastUpdated": datetime.now(timezone.utc).isoformat(),
            },
        }
        return resource

    # ── Evolucion → FHIR Observation ────────────────────────

    @staticmethod
    def evolucion_a_fhir(evo: dict[str, Any]) -> dict:
        """Convierte una evolucion a recurso FHIR Observation."""
        diagnostico = str(evo.get("diagnostico", "") or "")

        resource = {
            "resourceType": "Observation",
            "id": str(evo.get("id", FHIRAdapter._generate_id())),
            "status": "final",
            "code": FHIRAdapter._snomed(diagnostico),
            "subject": {
                "reference": f"Patient/{evo.get('paciente_id', '')}",
            },
            "effectiveDateTime": str(evo.get("fecha_atencion", evo.get("created_at", "")))[:19],
            "valueString": str(evo.get("nota", "")),
            "note": [{
                "text": f"Diagnostico: {diagnostico}. Medicacion: {evo.get('medicacion', '')}",
            }],
            "performer": [{
                "reference": f"Practitioner/{evo.get('profesional_id', '')}",
            }],
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/Observation"],
            },
        }
        return resource

    # ── Medicacion → FHIR MedicationAdministration ──────────

    @staticmethod
    def medicacion_a_fhir(med: dict[str, Any]) -> dict:
        """Convierte una administracion de medicamento a FHIR."""
        resource = {
            "resourceType": "MedicationAdministration",
            "id": str(med.get("id", FHIRAdapter._generate_id())),
            "status": str(med.get("estado", "completed")),
            "medicationCodeableConcept": {
                "coding": [{
                    "system": "http://snomed.info/sct",
                    "code": med.get("codigo_snomed", "UNKNOWN"),
                    "display": str(med.get("medicamento", "")),
                }],
                "text": str(med.get("medicamento", "")),
            },
            "subject": {
                "reference": f"Patient/{med.get('paciente_id', '')}",
            },
            "effectiveDateTime": str(med.get("fecha_real", med.get("created_at", "")))[:19],
            "dosage": {
                "text": f"{med.get('dosis', '')} via {med.get('via', '')}",
                "route": {
                    "coding": [{
                        "system": "http://snomed.info/sct",
                        "code": med.get("via_codigo", "UNKNOWN"),
                        "display": str(med.get("via", "")),
                    }],
                },
            },
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/MedicationAdministration"],
            },
        }
        return resource

    # ── Batch de exportacion ────────────────────────────────

    @staticmethod
    def batch_export(recursos: list[dict]) -> dict:
        """Empaqueta multiples recursos en un Bundle FHIR.

        Uso:
            bundle = FHIRAdapter.batch_export([
                paciente_fhir,
                evolucion_fhir,
                medicacion_fhir,
            ])
        """
        return {
            "resourceType": "Bundle",
            "type": "collection",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "entry": [
                {
                    "fullUrl": f"https://medicare-pro.app/fhir/{r['resourceType']}/{r['id']}",
                    "resource": r,
                }
                for r in recursos
            ],
            "meta": {
                "profile": ["http://hl7.org/fhir/StructureDefinition/Bundle"],
            },
        }
