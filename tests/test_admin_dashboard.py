"""Tests para views.admin_dashboard."""
from __future__ import annotations

import pytest


class TestAdminDashboard:
    """Tests para funciones públicas de views.admin_dashboard."""

    def test_admin_dashboard_importable(self):
        import views.admin_dashboard
        assert views.admin_dashboard is not None

    def test_functions_exist(self):
        import views.admin_dashboard
        assert callable(views.admin_dashboard.render_admin_dashboard)
        assert callable(views.admin_dashboard.render_metrics_tab)
        assert callable(views.admin_dashboard.render_users_tab)
        assert callable(views.admin_dashboard.render_audit_tab)
        assert callable(views.admin_dashboard.render_performance_tab)
        assert callable(views.admin_dashboard.render_cache_tab)
        assert callable(views.admin_dashboard.render_alerts_tab)
        assert callable(views.admin_dashboard.render_admin_page)
