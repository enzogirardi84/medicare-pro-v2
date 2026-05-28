"""Tests para views.auditoria_legal."""
from __future__ import annotations

import pytest


class TestAuditoriaLegal:
    """Tests para funciones públicas de views.auditoria_legal."""

    def test_auditoria_legal_importable(self):
        import views.auditoria_legal
        assert views.auditoria_legal is not None

    def test_functions_exist(self):
        import views.auditoria_legal
        assert callable(views.auditoria_legal.generar_pdf_auditoria_legal)
        assert callable(views.auditoria_legal.render_auditoria_legal)
