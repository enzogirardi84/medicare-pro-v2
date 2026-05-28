"""Tests para views.asistencia."""
from __future__ import annotations

import pytest


class TestAsistencia:
    """Tests para funciones públicas de views.asistencia."""

    def test_asistencia_importable(self):
        import views.asistencia
        assert views.asistencia is not None

    def test_functions_exist(self):
        import views.asistencia
        assert callable(views.asistencia.render_asistencia)
