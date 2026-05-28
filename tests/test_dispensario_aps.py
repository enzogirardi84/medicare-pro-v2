"""Tests para views.dispensario_aps."""
from __future__ import annotations

import pytest


class TestDispensarioAps:
    """Tests para funciones públicas de views.dispensario_aps."""

    def test_dispensario_aps_importable(self):
        import views.dispensario_aps
        assert views.dispensario_aps is not None

    def test_functions_exist(self):
        import views.dispensario_aps
        assert callable(views.dispensario_aps.render_dispensario_aps)
