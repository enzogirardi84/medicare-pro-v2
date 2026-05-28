"""Tests para core.onboarding."""
from __future__ import annotations

import pytest


class TestOnboarding:
    """Tests para funciones públicas de core.onboarding."""

    def test_onboarding_importable(self):
        import core.onboarding
        assert core.onboarding is not None

    def test_functions_exist(self):
        import core.onboarding
        assert callable(core.onboarding.create_medicare_tour)
        assert callable(core.onboarding.create_first_steps_checklist)
        assert callable(core.onboarding.render_panel_bienvenida)
        assert callable(core.onboarding.add_step)
        assert callable(core.onboarding.start)
        assert callable(core.onboarding.stop)
        assert callable(core.onboarding.is_active)
        assert callable(core.onboarding.is_completed)
        assert callable(core.onboarding.render)
        assert callable(core.onboarding.add_item)
