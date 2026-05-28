"""Tests para views.balance."""
from __future__ import annotations

import pytest


class TestBalance:
    """Tests para funciones públicas de views.balance."""

    def test_balance_importable(self):
        import views.balance
        assert views.balance is not None

    def test_functions_exist(self):
        import views.balance
        assert callable(views.balance.render_balance)
