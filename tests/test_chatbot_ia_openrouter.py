from __future__ import annotations

import sys
from types import SimpleNamespace
from unittest.mock import patch


def test_preguntar_a_ia_uses_openrouter_base_url_and_headers(monkeypatch):
    from views.chatbot_ia import preguntar_a_ia

    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["create_kwargs"] = kwargs
            message = SimpleNamespace(content="Respuesta OK")
            choice = SimpleNamespace(message=message)
            return SimpleNamespace(choices=[choice])

    class FakeChat:
        completions = FakeCompletions()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            captured["client_kwargs"] = kwargs
            self.chat = FakeChat()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))

    with patch("core.ai_assistant.is_llm_enabled", return_value=True), patch(
        "core.ai_assistant._get_llm_config",
        return_value=("openrouter", "sk-or-test", "deepseek/deepseek-chat"),
    ):
        result = preguntar_a_ia("Que medicacion tiene?", "Paciente de prueba")

    assert result == "Respuesta OK"
    assert captured["client_kwargs"]["base_url"] == "https://openrouter.ai/api/v1"
    assert captured["client_kwargs"]["api_key"] == "sk-or-test"
    assert captured["create_kwargs"]["model"] == "deepseek/deepseek-chat"
    assert captured["create_kwargs"]["extra_headers"] == {
        "HTTP-Referer": "https://medicare-pro.app",
        "X-Title": "Medicare Pro",
    }
