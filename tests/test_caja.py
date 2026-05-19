from __future__ import annotations

from views.caja import FPDF_DISPONIBLE, render_caja


def test_caja_imports():
    assert callable(render_caja)
    assert isinstance(FPDF_DISPONIBLE, bool)


def test_render_caja_exists():
    assert render_caja.__name__ == "render_caja"
