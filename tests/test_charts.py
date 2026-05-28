"""Tests para core.charts."""
from __future__ import annotations

import pytest


class TestCharts:
    """Tests para funciones públicas de core.charts."""

    def test_charts_importable(self):
        import core.charts
        assert core.charts is not None

    def test_functions_exist(self):
        import core.charts
        assert callable(core.charts.chart_barras)
        assert callable(core.charts.chart_linea)
        assert callable(core.charts.chart_area)
        assert callable(core.charts.render_metric_card)
        assert callable(core.charts.render_chart_card)
        assert callable(core.charts.render_kpi_row)
        assert callable(core.charts.placeholder_chart)
        assert callable(core.charts.plotly_chart_barras)
        assert callable(core.charts.plotly_chart_linea)
        assert callable(core.charts.plotly_chart_donut)
