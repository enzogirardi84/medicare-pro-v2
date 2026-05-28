"""Tests para views.feature_flags_admin."""
from __future__ import annotations

import pytest


class TestFeatureFlagsAdmin:
    """Tests para funciones públicas de views.feature_flags_admin."""

    def test_feature_flags_admin_importable(self):
        import views.feature_flags_admin
        assert views.feature_flags_admin is not None

    def test_functions_exist(self):
        import views.feature_flags_admin
        assert callable(views.feature_flags_admin.render_feature_flags_admin)
        assert callable(views.feature_flags_admin.render_global_flags)
        assert callable(views.feature_flags_admin.render_user_flags)
        assert callable(views.feature_flags_admin.render_flags_analytics)
        assert callable(views.feature_flags_admin.render_flags_history)
        assert callable(views.feature_flags_admin.render_feature_flag_toggles)
