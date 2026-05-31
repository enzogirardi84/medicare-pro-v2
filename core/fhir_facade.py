"""Fachada FHIR R4 para interoperabilidad B2B con prepagas.
Traduce recursos FHIR entrantes a eventos del clinical_event_store
y viceversa. Endpoints estandar: Patient, Observation, Bundle.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

from core.app_logging import log_event
from core.fhir_adapter import FHIRAdapter


# ═══════════════════════════════════════════════════════════════════
# 1. CONSTANTES FHIR
# ═══════════════════════════════════════════════════════════════════

FHIR_MIME_TYPE = "application/fhir+json"
FHIR_PROFILES = {
    "Patient": "http://hl7.org/fhir/StructureDefinition/Patient",
    "Observation": "http://hl7.org/fhir/StructureDefinition/Observation",
    "MedicationAdministration": "http://hl7.org/fhir/StructureDefinition/MedicationAdministration",
    "Bundle": "http://hl7.org/fhir/StructureDefinition/Bundle",
}


# ═══════════════════════════════════════════════════════════════════
# 2. TRADUCTOR FHIR <-> EVENTO INTERNO
# ═══════════════════════════════════════════════════════════════════

class FHIRFacade:
    """Fachada de interoperabilidad FHIR R4.

    Traduce:
    - GET /fhir/Patient/{id} → evento interno → FHIR Patient
    - POST /fhir/Observation → FHIR Observation → evento clinical_event_store
    - GET /fhir/{type}?search params → busqueda en event store → Bundle
    """

    # Mapeo de recursos FHIR a aggregate_type interno
    FHIR_TO_AGGREGATE = {
        "Patient": "paciente",
        "Observation": "evolucion",
        "MedicationAdministration": "medicacion",
        "MedicationRequest": "receta",
    }

    AGGREGATE_TO_FHIR = {v: k for k, v in FHIR_TO_AGGREGATE.items()}

    def __init__(self):
        self._conn = None
        self._adapter = FHIRAdapter()

    async def _get_conn(self):
        if self._conn is None:
            import asyncpg
            self._conn = await asyncpg.connect("postgresql://localhost:5432/medicare")
        return self._conn

    # ── Lectura: FHIR Resource → Event Store → FHIR ─────────

    async def read_resource(self, resource_type: str, resource_id: str,
                            tenant_id: str) -> Optional[dict]:
        """Lee un recurso FHIR desde el event store.

        Args:
            resource_type: Tipo FHIR (Patient, Observation, etc.)
            resource_id: ID del recurso.
            tenant_id: Tenant del recurso.

        Returns:
            Recurso FHIR R4, o None si no existe.
        """
        aggregate_type = self.FHIR_TO_AGGREGATE.get(resource_type)
        if not aggregate_type:
            raise ValueError(f"Tipo de recurso no soportado: {resource_type}")

        conn = await self._get_conn()
        row = await conn.fetchrow("""
            SELECT payload, event_version, checksum, created_at
            FROM clinical_event_store
            WHERE aggregate_type = $1 AND aggregate_id = $2 AND tenant_id = $3
            ORDER BY event_version DESC
            LIMIT 1
        """, aggregate_type, resource_id, tenant_id)

        if not row:
            return None

        payload = row["payload"]
        if isinstance(payload, str):
            payload = json.loads(payload)

        # Traducir a FHIR segun el tipo
        if resource_type == "Patient":
            return self._adapter.paciente_a_fhir(payload)
        elif resource_type == "Observation":
            return self._adapter.evolucion_a_fhir(payload)
        elif resource_type == "MedicationAdministration":
            return self._adapter.medicacion_a_fhir(payload)

        return payload

    async def search_resources(self, resource_type: str, tenant_id: str,
                                filters: Optional[dict] = None,
                                limit: int = 50, offset: int = 0) -> dict:
        """Busca recursos FHIR con filtros.

        Returns:
            Bundle FHIR con los resultados.
        """
        aggregate_type = self.FHIR_TO_AGGREGATE.get(resource_type)
        if not aggregate_type:
            raise ValueError(f"Tipo de recurso no soportado: {resource_type}")

        conn = await self._get_conn()
        where_clauses = ["aggregate_type = $1", "tenant_id = $2"]
        params = [aggregate_type, tenant_id]
        param_idx = 3

        # Filtros
        filters = filters or {}
        date_field = filters.get("date_field", "created_at")
        if "since" in filters:
            where_clauses.append(f"{date_field} >= ${param_idx}")
            params.append(filters["since"])
            param_idx += 1
        if "until" in filters:
            where_clauses.append(f"{date_field} <= ${param_idx}")
            params.append(filters["until"])
            param_idx += 1
        if "patient" in filters:
            where_clauses.append(f"payload->>'paciente_id' = ${param_idx}")
            params.append(filters["patient"])
            param_idx += 1

        where = " AND ".join(where_clauses)
        rows = await conn.fetch(f"""
            SELECT DISTINCT ON (aggregate_id) aggregate_id, payload, event_version, created_at
            FROM clinical_event_store
            WHERE {where}
            ORDER BY aggregate_id, event_version DESC
            LIMIT ${param_idx} OFFSET ${param_idx + 1}
        """, *params, limit, offset)

        total_row = await conn.fetchrow(f"""
            SELECT COUNT(DISTINCT aggregate_id) as total
            FROM clinical_event_store
            WHERE {where}
        """, *params[:param_idx - 1])

        total = total_row["total"] if total_row else 0

        # Traducir cada resultado a FHIR
        entries = []
        for r in rows:
            payload = r["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)

            fhir_resource = None
            if resource_type == "Patient":
                fhir_resource = self._adapter.paciente_a_fhir(payload)
            elif resource_type == "Observation":
                fhir_resource = self._adapter.evolucion_a_fhir(payload)
            elif resource_type == "MedicationAdministration":
                fhir_resource = self._adapter.medicacion_a_fhir(payload)

            if fhir_resource:
                entries.append({
                    "fullUrl": f"https://api.medicare-pro.app/fhir/{resource_type}/{r['aggregate_id']}",
                    "resource": fhir_resource,
                })

        return {
            "resourceType": "Bundle",
            "type": "searchset",
            "total": total,
            "entry": entries,
            "meta": {
                "lastUpdated": datetime.now(timezone.utc).isoformat(),
                "profile": [FHIR_PROFILES["Bundle"]],
            },
        }

    # ── Escritura: FHIR Resource → Event Store ──────────────

    async def create_resource(self, resource_type: str, fhir_resource: dict,
                               tenant_id: str, actor_id: str) -> dict:
        """Crea un recurso FHIR entrante como evento en el event store.

        Args:
            resource_type: Tipo FHIR.
            fhir_resource: Recurso FHIR R4.
            tenant_id: Tenant destino.
            actor_id: Profesional que crea el recurso.

        Returns:
            Recurso FHIR creado con id asignado.
        """
        aggregate_type = self.FHIR_TO_AGGREGATE.get(resource_type)
        if not aggregate_type:
            raise ValueError(f"Tipo de recurso no soportado: {resource_type}")

        resource_id = fhir_resource.get("id", str(uuid.uuid4()))
        internal_payload = self._fhir_to_internal(resource_type, fhir_resource)

        conn = await self._get_conn()
        event_type = f"{resource_type}Creado"

        await conn.execute("""
            INSERT INTO clinical_event_store
                (aggregate_type, aggregate_id, event_type, event_version,
                 tenant_id, actor_id, payload, checksum)
            VALUES ($1, $2, $3, 1, $4, $5, $6::jsonb, $7)
        """, aggregate_type, resource_id, event_type, tenant_id, actor_id,
             json.dumps(internal_payload, default=str),
             self._checksum(internal_payload))

        log_event("fhir_facade", f"created:{resource_type}:{resource_id}")
        return await self.read_resource(resource_type, resource_id, tenant_id)

    @staticmethod
    def _fhir_to_internal(resource_type: str, fhir: dict) -> dict:
        """Traduce un recurso FHIR a payload interno.

        Extrae campos relevantes del recurso FHIR R4
        y los mapea a la estructura interna de MediCare.
        """
        if resource_type == "Patient":
            name = fhir.get("name", [{}])[0].get("text", "")
            identifier = fhir.get("identifier", [])
            dni = ""
            for id_entry in identifier:
                if "dni" in id_entry.get("system", "").lower():
                    dni = id_entry.get("value", "")
            return {
                "id": fhir.get("id", ""),
                "nombre": name,
                "dni": dni,
                "genero": fhir.get("gender", "unknown"),
                "fecha_nacimiento": fhir.get("birthDate", ""),
                "direccion": fhir.get("address", [{}])[0].get("text", "")
                if fhir.get("address") else "",
            }

        elif resource_type == "Observation":
            code = fhir.get("code", {}).get("coding", [{}])[0]
            return {
                "id": fhir.get("id", ""),
                "diagnostico": code.get("display", code.get("code", "")),
                "codigo_snomed": code.get("code", ""),
                "nota": fhir.get("valueString", fhir.get("note", [{}])[0].get("text", "")),
                "paciente_id": fhir.get("subject", {}).get("reference", "").replace("Patient/", ""),
                "fecha_atencion": fhir.get("effectiveDateTime", ""),
            }

        elif resource_type == "MedicationAdministration":
            med = fhir.get("medicationCodeableConcept", {}).get("coding", [{}])[0]
            dosage = fhir.get("dosage", {})
            return {
                "id": fhir.get("id", ""),
                "medicamento": med.get("display", ""),
                "codigo_snomed": med.get("code", ""),
                "dosis": dosage.get("text", ""),
                "via": dosage.get("route", {}).get("coding", [{}])[0].get("display", ""),
                "paciente_id": fhir.get("subject", {}).get("reference", "").replace("Patient/", ""),
                "estado": fhir.get("status", "completed"),
            }

        return dict(fhir)

    @staticmethod
    def _checksum(payload: dict) -> str:
        import hashlib
        raw = json.dumps(payload, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode()).hexdigest()[:32]

    async def close(self):
        if self._conn:
            await self._conn.close()
            self._conn = None


# ═══════════════════════════════════════════════════════════════════
# 3. FASTAPI ROUTER (ejemplo de registro)
# ═══════════════════════════════════════════════════════════════════

FHIR_ROUTER_CODE = """
# Registrar en la app FastAPI:
# from core.fhir_facade import FHIRFacade, FHIR_ROUTER_CODE
# fhir = FHIRFacade()
# router = APIRouter(prefix="/fhir", tags=["fhir"])
# router.add_api_route("/Patient/{id}", ...)
# app.include_router(router)

from fastapi import APIRouter, Header, HTTPException
from core.fhir_facade import FHIRFacade, FHIR_MIME_TYPE

router = APIRouter(prefix="/fhir", tags=["fhir"])
fhir = FHIRFacade()

@router.get("/Patient/{patient_id}", response_model=dict)
async def get_patient(patient_id: str, x_tenant_id: str = Header(...)):
    result = await fhir.read_resource("Patient", patient_id, x_tenant_id)
    if not result:
        raise HTTPException(404, "Patient not found")
    return result

@router.get("/Observation", response_model=dict)
async def search_observations(
    patient: str = "", since: str = "", x_tenant_id: str = Header(...),
):
    filters = {}
    if patient: filters["patient"] = patient
    if since: filters["since"] = since
    return await fhir.search_resources("Observation", x_tenant_id, filters)

@router.post("/Observation", response_model=dict, status_code=201)
async def create_observation(
    resource: dict, x_tenant_id: str = Header(...), x_actor_id: str = Header(...),
):
    return await fhir.create_resource("Observation", resource, x_tenant_id, x_actor_id)
"""


__all__ = [
    "FHIRFacade",
    "FHIR_ROUTER_CODE",
    "FHIR_MIME_TYPE",
]
