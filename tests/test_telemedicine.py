"""Tests para core.telemedicine."""
from __future__ import annotations

import pytest


class TestTelemedicine:
    """Tests para funciones públicas de core.telemedicine."""

    def test_telemedicine_importable(self):
        import core.telemedicine
        assert core.telemedicine is not None

    def test_functions_exist(self):
        import core.telemedicine
        assert callable(core.telemedicine.get_telemedicine_manager)
        assert callable(core.telemedicine.schedule_virtual_consultation)
        assert callable(core.telemedicine.patient_join_waiting_room)
        assert callable(core.telemedicine.doctor_join_consultation)
        assert callable(core.telemedicine.end_consultation)
        assert callable(core.telemedicine.add_chat_message)
        assert callable(core.telemedicine.get_consultation)
        assert callable(core.telemedicine.get_patient_consultations)
        assert callable(core.telemedicine.get_doctor_consultations)
        assert callable(core.telemedicine.get_waiting_room)
