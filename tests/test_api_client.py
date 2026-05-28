"""Tests para core.api_client."""
from __future__ import annotations

import pytest


class TestApiClient:
    """Tests para funciones públicas de core.api_client."""

    def test_api_client_importable(self):
        import core.api_client
        assert core.api_client is not None

    def test_functions_exist(self):
        import core.api_client
        assert callable(core.api_client.get_api_base_url)
        assert callable(core.api_client.get_api_headers)
        assert callable(core.api_client.request_with_retry)
        assert callable(core.api_client.get_api)
        assert callable(core.api_client.post_api)
        assert callable(core.api_client.put_api)
        assert callable(core.api_client.delete_api)
