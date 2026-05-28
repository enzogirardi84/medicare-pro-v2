"""Tests para core.health_monitor."""
from __future__ import annotations

import pytest


class TestHealthMonitor:
    """Tests para funciones públicas de core.health_monitor."""

    def test_health_monitor_importable(self):
        import core.health_monitor
        assert core.health_monitor is not None

    def test_functions_exist(self):
        import core.health_monitor
        assert callable(core.health_monitor.create_db_health_check)
        assert callable(core.health_monitor.create_cache_health_check)
        assert callable(core.health_monitor.create_rate_limiter_health_check)
        assert callable(core.health_monitor.get_health_monitor)
        assert callable(core.health_monitor.quick_health_check)
        assert callable(core.health_monitor.run)
        assert callable(core.health_monitor.should_run)
        assert callable(core.health_monitor.register_check)
        assert callable(core.health_monitor.set_alert_threshold)
        assert callable(core.health_monitor.run_all_checks)
