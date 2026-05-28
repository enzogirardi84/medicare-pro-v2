"""Tests para views.self_healing_admin."""
from __future__ import annotations

import pytest


class TestSelfHealingAdmin:
    """Tests para funciones públicas de views.self_healing_admin."""

    def test_self_healing_admin_importable(self):
        import views.self_healing_admin
        assert views.self_healing_admin is not None

    def test_functions_exist(self):
        import views.self_healing_admin
        assert callable(views.self_healing_admin.render_self_healing_admin)
        assert callable(views.self_healing_admin.render_escaneo)
        assert callable(views.self_healing_admin.render_hallazgos)
        assert callable(views.self_healing_admin.render_historial)
        assert callable(views.self_healing_admin.render_errores)
