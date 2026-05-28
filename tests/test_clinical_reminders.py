"""Tests para core.clinical_reminders."""
from __future__ import annotations

import pytest


class TestClinicalReminders:
    """Tests para funciones públicas de core.clinical_reminders."""

    def test_clinical_reminders_importable(self):
        import core.clinical_reminders
        assert core.clinical_reminders is not None

    def test_functions_exist(self):
        import core.clinical_reminders
        assert callable(core.clinical_reminders.get_reminder_manager)
        assert callable(core.clinical_reminders.create_follow_up_reminder)
        assert callable(core.clinical_reminders.create_medication_reminder)
        assert callable(core.clinical_reminders.to_dict)
        assert callable(core.clinical_reminders.from_dict)
        assert callable(core.clinical_reminders.create_reminder)
        assert callable(core.clinical_reminders.complete_reminder)
        assert callable(core.clinical_reminders.delete_reminder)
        assert callable(core.clinical_reminders.get_reminders)
        assert callable(core.clinical_reminders.get_pending_notifications)
