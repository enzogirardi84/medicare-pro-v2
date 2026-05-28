"""Tests para views._visitas_secciones."""
from __future__ import annotations

import pytest


class TestVisitasSecciones:
    """Tests para funciones públicas de views._visitas_secciones."""

    def test__visitas_secciones_importable(self):
        import views._visitas_secciones
        assert views._visitas_secciones is not None

    def test_functions_exist(self):
        import views._visitas_secciones
        assert callable(views._visitas_secciones.registrar_estado_checkins_sql)
        assert callable(views._visitas_secciones.estado_checkins_sql)
