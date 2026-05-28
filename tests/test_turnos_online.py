"""Tests para views.turnos_online."""
from __future__ import annotations

import pytest


class TestTurnosOnline:
    """Tests para funciones públicas de views.turnos_online."""

    def test_turnos_online_importable(self):
        import views.turnos_online
        assert views.turnos_online is not None

    def test_functions_exist(self):
        import views.turnos_online
        assert callable(views.turnos_online.render_turnos_online)
