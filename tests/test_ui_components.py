"""Tests para core.ui_components."""
from __future__ import annotations

import pytest


class TestUiComponents:
    """Tests para funciones públicas de core.ui_components."""

    def test_ui_components_importable(self):
        import core.ui_components
        assert core.ui_components is not None

    def test_functions_exist(self):
        import core.ui_components
        assert callable(core.ui_components.tooltip)
        assert callable(core.ui_components.render_tooltip)
        assert callable(core.ui_components.badge)
        assert callable(core.ui_components.render_badge)
        assert callable(core.ui_components.status_dot)
        assert callable(core.ui_components.render_status_dot)
        assert callable(core.ui_components.medical_card)
        assert callable(core.ui_components.render_medical_card)
        assert callable(core.ui_components.timeline_item)
        assert callable(core.ui_components.timeline)
