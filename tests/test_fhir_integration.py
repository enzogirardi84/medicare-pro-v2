"""Tests para core.fhir_integration."""
from __future__ import annotations

import pytest


class TestFhirIntegration:
    """Tests para funciones públicas de core.fhir_integration."""

    def test_fhir_integration_importable(self):
        import core.fhir_integration
        assert core.fhir_integration is not None

    def test_functions_exist(self):
        import core.fhir_integration
        assert callable(core.fhir_integration.get_fhir_converter)
        assert callable(core.fhir_integration.export_patient_to_fhir)
        assert callable(core.fhir_integration.convert_vitals_to_fhir)
        assert callable(core.fhir_integration.validate_fhir_json)
        assert callable(core.fhir_integration.patient_to_fhir)
        assert callable(core.fhir_integration.patient_from_fhir)
        assert callable(core.fhir_integration.vitals_to_fhir_observations)
        assert callable(core.fhir_integration.encounter_to_fhir)
        assert callable(core.fhir_integration.condition_to_fhir)
        assert callable(core.fhir_integration.medication_request_to_fhir)
