"""Tests para core.user_feedback."""
from __future__ import annotations

import pytest


class TestUserFeedback:
    """Tests para funciones públicas de core.user_feedback."""

    def test_user_feedback_importable(self):
        import core.user_feedback
        assert core.user_feedback is not None

    def test_functions_exist(self):
        import core.user_feedback
        assert callable(core.user_feedback.render_modulo_fallo_ui)
        assert callable(core.user_feedback.render_carga_modulo_fallo)
