"""Tests para core.analytics_reports."""
from __future__ import annotations

import pytest


class TestAnalyticsReports:
    """Tests para funciones públicas de core.analytics_reports."""

    def test_analytics_reports_importable(self):
        import core.analytics_reports
        assert core.analytics_reports is not None

    def test_functions_exist(self):
        import core.analytics_reports
        assert callable(core.analytics_reports.get_analytics_engine)
        assert callable(core.analytics_reports.get_dashboard_summary)
        assert callable(core.analytics_reports.compare_to_benchmark)
        assert callable(core.analytics_reports.to_dict)
        assert callable(core.analytics_reports.calculate_clinical_kpis)
        assert callable(core.analytics_reports.calculate_operational_metrics)
        assert callable(core.analytics_reports.calculate_financial_summary)
        assert callable(core.analytics_reports.calculate_quality_metrics)
        assert callable(core.analytics_reports.generate_trend_analysis)
        assert callable(core.analytics_reports.generate_dashboard)
