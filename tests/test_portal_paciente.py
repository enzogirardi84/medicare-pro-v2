"""Tests para views.portal_paciente."""
from __future__ import annotations

import pytest


class TestPortalPaciente:
    """Tests para funciones públicas de views.portal_paciente."""

    def test_portal_paciente_importable(self):
        import views.portal_paciente
        assert views.portal_paciente is not None

    def test_functions_exist(self):
        import views.portal_paciente
        assert callable(views.portal_paciente.render_portal_paciente)
