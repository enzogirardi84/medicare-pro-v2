"""Tests para views.alertas_paciente_app."""
from __future__ import annotations

import pytest


class TestAlertasPacienteApp:
    """Tests para funciones públicas de views.alertas_paciente_app."""

    def test_alertas_paciente_app_importable(self):
        import views.alertas_paciente_app
        assert views.alertas_paciente_app is not None

    def test_functions_exist(self):
        import views.alertas_paciente_app
        assert callable(views.alertas_paciente_app.render_alertas_paciente_app)
        assert callable(views.alertas_paciente_app.nivel_ord)
        assert callable(views.alertas_paciente_app.by_fecha)
