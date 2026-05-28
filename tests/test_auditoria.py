"""Tests para views.auditoria."""
from __future__ import annotations

import pytest


class TestAuditoria:
    """Tests para funciones públicas de views.auditoria."""

    def test_auditoria_importable(self):
        import views.auditoria
        assert views.auditoria is not None

    def test_functions_exist(self):
        import views.auditoria
        assert callable(views.auditoria.generar_pdf_auditoria_logs)
        assert callable(views.auditoria.render_auditoria)
        assert callable(views.auditoria.safe)
