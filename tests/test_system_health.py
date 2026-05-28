"""Tests para core.system_health."""
from __future__ import annotations

import pytest


class TestSystemHealth:
    """Tests para funciones públicas de core.system_health."""

    def test_system_health_importable(self):
        import core.system_health
        assert core.system_health is not None

    def test_functions_exist(self):
        import core.system_health
        assert callable(core.system_health.get_health_monitor)
        assert callable(core.system_health.quick_health_check)
        assert callable(core.system_health.healthy_count)
        assert callable(core.system_health.degraded_count)
        assert callable(core.system_health.unhealthy_count)
        assert callable(core.system_health.register_check)
        assert callable(core.system_health.run_health_check)
        assert callable(core.system_health.render_health_dashboard)
