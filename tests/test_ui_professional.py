"""Tests para core.ui_professional."""
from __future__ import annotations

import pytest


class TestUiProfessional:
    """Tests para funciones públicas de core.ui_professional."""

    def test_ui_professional_importable(self):
        import core.ui_professional
        assert core.ui_professional is not None

    def test_functions_exist(self):
        import core.ui_professional
        assert callable(core.ui_professional.apply_professional_theme)
        assert callable(core.ui_professional.card)
        assert callable(core.ui_professional.metric_card)
        assert callable(core.ui_professional.badge)
        assert callable(core.ui_professional.alert)
        assert callable(core.ui_professional.data_table)
        assert callable(core.ui_professional.avatar)
        assert callable(core.ui_professional.render_metrics_row)
        assert callable(core.ui_professional.render_card)
        assert callable(core.ui_professional.render_alert)
