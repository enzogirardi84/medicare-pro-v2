"""Tests para core.health_check."""
from __future__ import annotations

import pytest


class TestHealthCheck:
    """Tests para funciones públicas de core.health_check."""

    def test_health_check_importable(self):
        import core.health_check
        assert core.health_check is not None

    def test_functions_exist(self):
        import core.health_check
        assert callable(core.health_check.check_supabase_connection)
        assert callable(core.health_check.check_internet_connection)
        assert callable(core.health_check.run_startup_checks)
