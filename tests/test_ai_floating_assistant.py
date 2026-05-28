"""Tests para views.ai_floating_assistant."""
from __future__ import annotations

import pytest


class TestAiFloatingAssistant:
    """Tests para funciones públicas de views.ai_floating_assistant."""

    def test_ai_floating_assistant_importable(self):
        import views.ai_floating_assistant
        assert views.ai_floating_assistant is not None

    def test_functions_exist(self):
        import views.ai_floating_assistant
        assert callable(views.ai_floating_assistant.render_ai_floating_assistant)
