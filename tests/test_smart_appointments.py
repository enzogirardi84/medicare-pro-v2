"""Tests para core.smart_appointments."""
from __future__ import annotations

import pytest


class TestSmartAppointments:
    """Tests para funciones públicas de core.smart_appointments."""

    def test_smart_appointments_importable(self):
        import core.smart_appointments
        assert core.smart_appointments is not None

    def test_functions_exist(self):
        import core.smart_appointments
        assert callable(core.smart_appointments.get_appointment_manager)
        assert callable(core.smart_appointments.schedule_appointment)
        assert callable(core.smart_appointments.get_patient_risk_score)
        assert callable(core.smart_appointments.suggest_optimal_slots)
        assert callable(core.smart_appointments.duration_minutes)
        assert callable(core.smart_appointments.actual_duration_minutes)
        assert callable(core.smart_appointments.find_available_slots)
        assert callable(core.smart_appointments.schedule_appointment)
        assert callable(core.smart_appointments.check_in_patient)
        assert callable(core.smart_appointments.complete_appointment)
