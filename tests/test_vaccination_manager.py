"""Tests para core.vaccination_manager."""
from __future__ import annotations

import pytest


class TestVaccinationManager:
    """Tests para funciones públicas de core.vaccination_manager."""

    def test_vaccination_manager_importable(self):
        import core.vaccination_manager
        assert core.vaccination_manager is not None

    def test_functions_exist(self):
        import core.vaccination_manager
        assert callable(core.vaccination_manager.get_vaccination_manager)
        assert callable(core.vaccination_manager.record_patient_vaccination)
        assert callable(core.vaccination_manager.check_patient_vaccination_status)
        assert callable(core.vaccination_manager.to_dict)
        assert callable(core.vaccination_manager.get_vaccines_for_age)
        assert callable(core.vaccination_manager.get_pending_doses)
        assert callable(core.vaccination_manager.record_vaccination)
        assert callable(core.vaccination_manager.get_patient_vaccination_history)
        assert callable(core.vaccination_manager.get_patient_pending_vaccines)
        assert callable(core.vaccination_manager.generate_vaccination_certificate)
