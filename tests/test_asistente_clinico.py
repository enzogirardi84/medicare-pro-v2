"""Tests para views.asistente_clinico."""
from __future__ import annotations

import pytest


class TestAsistenteClinico:
    """Tests para funciones públicas de views.asistente_clinico."""

    def test_asistente_clinico_importable(self):
        import views.asistente_clinico
        assert views.asistente_clinico is not None

    def test_functions_exist(self):
        import views.asistente_clinico
        assert callable(views.asistente_clinico.render_asistente_clinico)
        assert callable(views.asistente_clinico.renderizar_tarjeta_indicacion)
