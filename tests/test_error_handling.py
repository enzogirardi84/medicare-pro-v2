"""Tests para core.error_handling."""
from __future__ import annotations

import pytest


class TestErrorHandling:
    """Tests para funciones públicas de core.error_handling."""

    def test_error_handling_importable(self):
        import core.error_handling
        assert core.error_handling is not None

    def test_functions_exist(self):
        import core.error_handling
        assert callable(core.error_handling.handle_errors)
        assert callable(core.error_handling.retry_on_error)
        assert callable(core.error_handling.validate_input)
        assert callable(core.error_handling.error_boundary)
        assert callable(core.error_handling.database_transaction)
        assert callable(core.error_handling.log_exception)
        assert callable(core.error_handling.safe_operation)
        assert callable(core.error_handling.validate_and_execute)
        assert callable(core.error_handling.get_error_handler)
        assert callable(core.error_handling.decorator)
