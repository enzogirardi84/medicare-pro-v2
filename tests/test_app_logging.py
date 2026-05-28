"""Tests para core.app_logging."""
from __future__ import annotations

import pytest


class TestAppLogging:
    """Tests para funciones públicas de core.app_logging."""

    def test_app_logging_importable(self):
        import core.app_logging
        assert core.app_logging is not None

    def test_functions_exist(self):
        import core.app_logging
        assert callable(core.app_logging.configurar_logging_basico)
        assert callable(core.app_logging.log_event)
        assert callable(core.app_logging.get_recent_errors)
        assert callable(core.app_logging.emit)
