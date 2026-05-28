"""Tests para views.escalas_clinicas."""
from __future__ import annotations

import pytest


class TestEscalasClinicas:
    """Tests para funciones públicas de views.escalas_clinicas."""

    def test_escalas_clinicas_importable(self):
        import views.escalas_clinicas
        assert views.escalas_clinicas is not None

    def test_functions_exist(self):
        import views.escalas_clinicas
        assert callable(views.escalas_clinicas.render_escalas_clinicas)
