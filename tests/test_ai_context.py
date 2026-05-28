"""Tests para core.ai_context."""
from __future__ import annotations

import pytest


class TestAiContext:
    """Tests para funciones públicas de core.ai_context."""

    def test_ai_context_importable(self):
        import core.ai_context
        assert core.ai_context is not None

    def test_functions_exist(self):
        import core.ai_context
        assert callable(core.ai_context.get_view_help)
        assert callable(core.ai_context.get_view_tips)
        assert callable(core.ai_context.get_quick_actions)
