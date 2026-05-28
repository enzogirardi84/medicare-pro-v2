"""Tests para views._enfermeria_plan."""
from __future__ import annotations

import pytest


class TestEnfermeriaPlan:
    """Tests para funciones públicas de views._enfermeria_plan."""

    def test__enfermeria_plan_importable(self):
        import views._enfermeria_plan
        assert views._enfermeria_plan is not None

    def test_functions_exist(self):
        import views._enfermeria_plan
        assert callable(views._enfermeria_plan.cargar_registros_enfermeria)
