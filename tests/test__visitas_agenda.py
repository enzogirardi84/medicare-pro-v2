"""Tests para views._visitas_agenda."""
from __future__ import annotations

import pytest


class TestVisitasAgenda:
    """Tests para funciones públicas de views._visitas_agenda."""

    def test__visitas_agenda_importable(self):
        import views._visitas_agenda
        assert views._visitas_agenda is not None

    def test_functions_exist(self):
        import views._visitas_agenda
        assert callable(views._visitas_agenda.registrar_estado_visitas_sql)
        assert callable(views._visitas_agenda.estado_visitas_sql)
        assert callable(views._visitas_agenda.get_turnos_by_empresa)
