"""Tests para views.pediatria."""
from __future__ import annotations

import pytest


class TestPediatria:
    """Tests para funciones públicas de views.pediatria."""

    def test_pediatria_importable(self):
        import views.pediatria
        assert views.pediatria is not None

    def test_functions_exist(self):
        import views.pediatria
        assert callable(views.pediatria.render_pediatria)
