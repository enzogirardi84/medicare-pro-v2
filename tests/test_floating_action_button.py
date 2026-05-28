"""Tests para core.floating_action_button."""
from __future__ import annotations

import pytest


class TestFloatingActionButton:
    """Tests para funciones públicas de core.floating_action_button."""

    def test_floating_action_button_importable(self):
        import core.floating_action_button
        assert core.floating_action_button is not None

    def test_functions_exist(self):
        import core.floating_action_button
        assert callable(core.floating_action_button.create_medicare_fab)
        assert callable(core.floating_action_button.render_quick_actions_bar)
        assert callable(core.floating_action_button.demo_floating_action_button)
        assert callable(core.floating_action_button.add_action)
        assert callable(core.floating_action_button.render)
