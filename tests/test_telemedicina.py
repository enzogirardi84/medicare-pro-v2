"""Tests para views.telemedicina."""
from __future__ import annotations

import pytest


class TestTelemedicina:
    """Tests para funciones públicas de views.telemedicina."""

    def test_telemedicina_importable(self):
        import views.telemedicina
        assert views.telemedicina is not None

    def test_functions_exist(self):
        import views.telemedicina
        assert callable(views.telemedicina.render_telemedicina)
