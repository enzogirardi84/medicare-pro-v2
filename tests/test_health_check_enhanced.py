"""Tests para core.health_check_enhanced."""
from __future__ import annotations

import pytest


class TestHealthCheckEnhanced:
    """Tests para funciones públicas de core.health_check_enhanced."""

    def test_health_check_enhanced_importable(self):
        import core.health_check_enhanced
        assert core.health_check_enhanced is not None

    def test_functions_exist(self):
        import core.health_check_enhanced
        assert callable(core.health_check_enhanced.get_health_checker)
        assert callable(core.health_check_enhanced.check_system_health)
        assert callable(core.health_check_enhanced.render_health_dashboard)
        assert callable(core.health_check_enhanced.to_dict)
        assert callable(core.health_check_enhanced.run_all_checks)
        assert callable(core.health_check_enhanced.get_last_report)
        assert callable(core.health_check_enhanced.is_system_healthy)
