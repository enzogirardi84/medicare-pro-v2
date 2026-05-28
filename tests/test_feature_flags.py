"""Tests para core.feature_flags."""
from __future__ import annotations

import pytest


class TestFeatureFlags:
    """Tests para funciones públicas de core.feature_flags."""

    def test_feature_flags_importable(self):
        import core.feature_flags
        assert core.feature_flags is not None

    def test_functions_exist(self):
        import core.feature_flags
        assert callable(core.feature_flags.get_feature_flags)
        assert callable(core.feature_flags.from_module)
