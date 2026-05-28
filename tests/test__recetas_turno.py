"""Tests para views._recetas_turno."""
from __future__ import annotations

import pytest


class TestRecetasTurno:
    """Tests para funciones públicas de views._recetas_turno."""

    def test__recetas_turno_importable(self):
        import views._recetas_turno
        assert views._recetas_turno is not None

    def test_functions_exist(self):
        import views._recetas_turno
        assert callable(views._recetas_turno.render_administracion_turno)
        assert callable(views._recetas_turno.render_historial_prescripciones)
