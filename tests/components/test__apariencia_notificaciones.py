"""Tests para views.settings.components._apariencia_notificaciones."""
from __future__ import annotations

import pytest


class TestAparienciaNotificaciones:
    """Tests para funciones públicas de views.settings.components._apariencia_notificaciones."""

    def test__apariencia_notificaciones_importable(self):
        import views.settings.components._apariencia_notificaciones
        assert views.settings.components._apariencia_notificaciones is not None

    def test_functions_exist(self):
        import views.settings.components._apariencia_notificaciones
        assert callable(views.settings.components._apariencia_notificaciones.render_appearance_settings)
        assert callable(views.settings.components._apariencia_notificaciones.render_notification_settings)
