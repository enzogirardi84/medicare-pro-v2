"""Tests para views.legal_docs."""
from __future__ import annotations

import pytest


class TestLegalDocs:
    """Tests para funciones públicas de views.legal_docs."""

    def test_legal_docs_importable(self):
        import views.legal_docs
        assert views.legal_docs is not None

    def test_functions_exist(self):
        import views.legal_docs
        assert callable(views.legal_docs.render_legal_docs)
