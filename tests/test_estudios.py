"""Tests para views.estudios."""
from __future__ import annotations

import pytest


class TestEstudios:
    """Tests para funciones públicas de views.estudios."""

    def test_estudios_importable(self):
        import views.estudios
        assert views.estudios is not None

    def test_functions_exist(self):
        import views.estudios
        assert callable(views.estudios.registrar_estado_estudios_sql)
        assert callable(views.estudios.estado_estudios_sql)
        assert callable(views.estudios.render_estudios)
