"""Tests para views.financial_reports."""
from __future__ import annotations

import pytest


class TestFinancialReports:
    """Tests para funciones públicas de views.financial_reports."""

    def test_financial_reports_importable(self):
        import views.financial_reports
        assert views.financial_reports is not None

    def test_functions_exist(self):
        import views.financial_reports
        assert callable(views.financial_reports.render_financial_reports)
        assert callable(views.financial_reports.render_financial_dashboard)
        assert callable(views.financial_reports.render_productivity_dashboard)
        assert callable(views.financial_reports.render_patients_analytics)
        assert callable(views.financial_reports.render_insurance_analytics)
        assert callable(views.financial_reports.render_trends_forecast)
        assert callable(views.financial_reports.calculate_period_start)
        assert callable(views.financial_reports.parse_date)
        assert callable(views.financial_reports.filter_by_date_range)
        assert callable(views.financial_reports.export_to_excel)
