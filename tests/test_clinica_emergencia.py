"""Tests para views.clinica_emergencia."""
from __future__ import annotations

import pytest


class TestClinicaEmergencia:
    """Tests para funciones públicas de views.clinica_emergencia."""

    def test_clinica_emergencia_importable(self):
        import views.clinica_emergencia
        assert views.clinica_emergencia is not None

    def test_functions_exist(self):
        import views.clinica_emergencia
        assert callable(views.clinica_emergencia.render)
