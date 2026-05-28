"""Tests para core.safe_view."""
from __future__ import annotations

import pytest


class TestSafeView:
    """Tests para funciones públicas de core.safe_view."""

    def test_safe_view_importable(self):
        import core.safe_view
        assert core.safe_view is not None

    def test_functions_exist(self):
        import core.safe_view
        assert callable(core.safe_view.safe_clinical_view)
        assert callable(core.safe_view.decorator)
        assert callable(core.safe_view.wrapper)
