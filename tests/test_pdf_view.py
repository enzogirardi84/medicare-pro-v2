"""Tests para views.pdf_view."""
from __future__ import annotations

import pytest


class TestPdfView:
    """Tests para funciones públicas de views.pdf_view."""

    def test_pdf_view_importable(self):
        import views.pdf_view
        assert views.pdf_view is not None

    def test_functions_exist(self):
        import views.pdf_view
        assert callable(views.pdf_view.render_pdf)
