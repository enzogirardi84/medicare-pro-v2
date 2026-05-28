"""Tests para core.chronic_disease_manager."""
from __future__ import annotations

import pytest


class TestChronicDiseaseManager:
    """Tests para funciones públicas de core.chronic_disease_manager."""

    def test_chronic_disease_manager_importable(self):
        import core.chronic_disease_manager
        assert core.chronic_disease_manager is not None

    def test_functions_exist(self):
        import core.chronic_disease_manager
        assert callable(core.chronic_disease_manager.get_diabetes_manager)
        assert callable(core.chronic_disease_manager.get_hypertension_manager)
        assert callable(core.chronic_disease_manager.record_diabetes_control)
        assert callable(core.chronic_disease_manager.record_hypertension_control)
        assert callable(core.chronic_disease_manager.to_dict)
        assert callable(core.chronic_disease_manager.record_control)
        assert callable(core.chronic_disease_manager.get_control_status)
        assert callable(core.chronic_disease_manager.get_trend_analysis)
        assert callable(core.chronic_disease_manager.get_pending_controls)
        assert callable(core.chronic_disease_manager.record_control)
