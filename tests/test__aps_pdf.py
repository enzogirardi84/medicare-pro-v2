"""Tests para views._aps_pdf."""
from __future__ import annotations

import pytest


class TestApsPdf:
    """Tests para funciones públicas de views._aps_pdf."""

    def test__aps_pdf_importable(self):
        import views._aps_pdf
        assert views._aps_pdf is not None

    def test_functions_exist(self):
        import views._aps_pdf
        assert callable(views._aps_pdf.generar_pdf_historial_paciente)
        assert callable(views._aps_pdf.generar_pdf_reporte_aps)
        assert callable(views._aps_pdf.header)
        assert callable(views._aps_pdf.footer)
