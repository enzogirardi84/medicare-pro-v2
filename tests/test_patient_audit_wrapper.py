"""Tests para core.patient_audit_wrapper."""
from __future__ import annotations

import pytest


class TestPatientAuditWrapper:
    """Tests para funciones públicas de core.patient_audit_wrapper."""

    def test_patient_audit_wrapper_importable(self):
        import core.patient_audit_wrapper
        assert core.patient_audit_wrapper is not None

    def test_functions_exist(self):
        import core.patient_audit_wrapper
        assert callable(core.patient_audit_wrapper.requires_auth)
        assert callable(core.patient_audit_wrapper.audit_action)
        assert callable(core.patient_audit_wrapper.buscar_pacientes)
        assert callable(core.patient_audit_wrapper.obtener_paciente)
        assert callable(core.patient_audit_wrapper.crear_paciente)
        assert callable(core.patient_audit_wrapper.actualizar_paciente)
        assert callable(core.patient_audit_wrapper.eliminar_paciente)
        assert callable(core.patient_audit_wrapper.decorator)
        assert callable(core.patient_audit_wrapper.decorator)
        assert callable(core.patient_audit_wrapper.list_patients)
