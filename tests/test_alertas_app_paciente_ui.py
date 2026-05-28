"""Tests para core.alertas_app_paciente_ui."""
from __future__ import annotations

import pytest


class TestAlertasAppPacienteUi:
    """Tests para funciones públicas de core.alertas_app_paciente_ui."""

    def test_alertas_app_paciente_ui_importable(self):
        import core.alertas_app_paciente_ui
        assert core.alertas_app_paciente_ui is not None

    def test_functions_exist(self):
        import core.alertas_app_paciente_ui
        assert callable(core.alertas_app_paciente_ui.obtener_alertas_rojas_pendientes)
        assert callable(core.alertas_app_paciente_ui.render_sidebar_bloque_app_paciente)
        assert callable(core.alertas_app_paciente_ui.render_banner_alertas_criticas_si_aplica)
        assert callable(core.alertas_app_paciente_ui.fetch)
