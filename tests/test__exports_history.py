"""Tests para core._exports_history."""
from __future__ import annotations

import pytest


class TestExportsHistory:
    """Tests para funciones públicas de core._exports_history."""

    def test__exports_history_importable(self):
        import core._exports_history
        assert core._exports_history is not None

    def test_functions_exist(self):
        import core._exports_history
        assert callable(core._exports_history.build_history_pdf_bytes)
