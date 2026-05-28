"""Tests para views.appointment_scheduler."""
from __future__ import annotations

import pytest


class TestAppointmentScheduler:
    """Tests para funciones públicas de views.appointment_scheduler."""

    def test_appointment_scheduler_importable(self):
        import views.appointment_scheduler
        assert views.appointment_scheduler is not None

    def test_functions_exist(self):
        import views.appointment_scheduler
        assert callable(views.appointment_scheduler.render_appointment_scheduler)
        assert callable(views.appointment_scheduler.render_new_appointment_form)
        assert callable(views.appointment_scheduler.render_daily_agenda)
        assert callable(views.appointment_scheduler.render_appointment_stats)
        assert callable(views.appointment_scheduler.get_scheduler)
        assert callable(views.appointment_scheduler.to_dict)
        assert callable(views.appointment_scheduler.create_appointment)
        assert callable(views.appointment_scheduler.is_slot_available)
        assert callable(views.appointment_scheduler.get_available_slots)
        assert callable(views.appointment_scheduler.get_appointments)
