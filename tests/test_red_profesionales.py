"""Tests para views.red_profesionales."""
from __future__ import annotations

import pytest


class TestRedProfesionales:
    """Tests para funciones públicas de views.red_profesionales."""

    def test_red_profesionales_importable(self):
        import views.red_profesionales
        assert views.red_profesionales is not None

    def test_functions_exist(self):
        import views.red_profesionales
        assert callable(views.red_profesionales.render_red_profesionales)
