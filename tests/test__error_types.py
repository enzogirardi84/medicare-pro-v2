"""Tests para core._error_types."""
from __future__ import annotations

import pytest


class TestErrorTypes:
    """Tests para funciones públicas de core._error_types."""

    def test__error_types_importable(self):
        import core._error_types
        assert core._error_types is not None

    def test_functions_exist(self):
        import core._error_types
        assert callable(core._error_types.to_dict)
