"""Tests para core.fhir_facade — FHIR R4 Facade."""
from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestFHIRFacade:
    def test_fhir_to_internal_patient(self):
        from core.fhir_facade import FHIRFacade
        fhir = {
            "id": "p1",
            "name": [{"text": "Juan Perez"}],
            "identifier": [{"system": "https://medicare-pro.app/identifiers/dni", "value": "12345678"}],
            "gender": "male",
            "birthDate": "1980-05-15",
            "address": [{"text": "Av. Siempre Viva 742"}],
        }
        internal = FHIRFacade._fhir_to_internal("Patient", fhir)
        assert internal["nombre"] == "Juan Perez"
        assert internal["dni"] == "12345678"

    def test_fhir_to_internal_observation(self):
        from core.fhir_facade import FHIRFacade
        fhir = {
            "id": "obs1",
            "code": {"coding": [{"code": "233604007", "display": "Neumonia"}]},
            "valueString": "Paciente con fiebre",
            "subject": {"reference": "Patient/p1"},
            "effectiveDateTime": "2026-06-01T10:00:00Z",
        }
        internal = FHIRFacade._fhir_to_internal("Observation", fhir)
        assert internal["diagnostico"] == "Neumonia"
        assert internal["paciente_id"] == "p1"

    def test_fhir_to_internal_medication(self):
        from core.fhir_facade import FHIRFacade
        fhir = {
            "id": "med1",
            "status": "completed",
            "medicationCodeableConcept": {"coding": [{"code": "12345", "display": "Paracetamol"}]},
            "subject": {"reference": "Patient/p1"},
            "dosage": {"text": "500mg cada 8h", "route": {"coding": [{"display": "oral"}]}},
        }
        internal = FHIRFacade._fhir_to_internal("MedicationAdministration", fhir)
        assert internal["medicamento"] == "Paracetamol"
        assert internal["dosis"] == "500mg cada 8h"

    def test_checksum(self):
        from core.fhir_facade import FHIRFacade
        cs1 = FHIRFacade._checksum({"a": 1, "b": 2})
        cs2 = FHIRFacade._checksum({"b": 2, "a": 1})
        assert cs1 == cs2
        assert len(cs1) == 32

    def test_read_resource_no_data(self):
        from core.fhir_facade import FHIRFacade
        facade = FHIRFacade()
        mock_conn = MagicMock()
        mock_conn.fetchrow = AsyncMock(return_value=None)
        facade._conn = mock_conn
        result = asyncio.run(facade.read_resource("Patient", "nonexistent", "t1"))
        assert result is None

    def test_search_resources_empty(self):
        from core.fhir_facade import FHIRFacade
        facade = FHIRFacade()
        mock_conn = MagicMock()
        mock_conn.fetch = AsyncMock(return_value=[])
        mock_conn.fetchrow = AsyncMock(return_value={"total": 0})
        facade._conn = mock_conn
        result = asyncio.run(facade.search_resources("Patient", "t1"))
        assert result["total"] == 0

    def test_read_resource_unsupported_type(self):
        from core.fhir_facade import FHIRFacade
        facade = FHIRFacade()
        with pytest.raises(ValueError, match="no soportado"):
            asyncio.run(facade.read_resource("UnknownType", "id", "t1"))


class TestFHIRRouterCode:
    def test_router_code_importable(self):
        from core.fhir_facade import FHIR_ROUTER_CODE
        assert "APIRouter" in FHIR_ROUTER_CODE
        assert "Patient" in FHIR_ROUTER_CODE
        assert "Observation" in FHIR_ROUTER_CODE
