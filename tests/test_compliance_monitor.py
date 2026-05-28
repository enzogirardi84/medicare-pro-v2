"""Tests para core.compliance_monitor."""
from __future__ import annotations

import pytest


class TestComplianceMonitor:
    """Tests para funciones públicas de core.compliance_monitor."""

    def test_compliance_monitor_importable(self):
        import core.compliance_monitor
        assert core.compliance_monitor is not None

    def test_functions_exist(self):
        import core.compliance_monitor
        assert callable(core.compliance_monitor.get_compliance_monitor)
        assert callable(core.compliance_monitor.run_compliance_check)
        assert callable(core.compliance_monitor.check_hipaa_compliance)
        assert callable(core.compliance_monitor.to_dict)
        assert callable(core.compliance_monitor.to_dict)
        assert callable(core.compliance_monitor.run_compliance_audit)
        assert callable(core.compliance_monitor.get_compliance_status)
        assert callable(core.compliance_monitor.resolve_violation)
        assert callable(core.compliance_monitor.render_compliance_dashboard)
