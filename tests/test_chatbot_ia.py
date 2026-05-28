"""Tests para views.chatbot_ia."""
from __future__ import annotations

import pytest


class TestChatbotIa:
    """Tests para funciones públicas de views.chatbot_ia."""

    def test_chatbot_ia_importable(self):
        import views.chatbot_ia
        assert views.chatbot_ia is not None

    def test_functions_exist(self):
        import views.chatbot_ia
        assert callable(views.chatbot_ia.buscar_en_web)
        assert callable(views.chatbot_ia.preguntar_a_ia)
        assert callable(views.chatbot_ia.render_chatbot_ia)
