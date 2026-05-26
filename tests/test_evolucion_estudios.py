"""Tests para views/evolucion.py y views/estudios.py."""
from __future__ import annotations


def test_render_evolucion_importable():
    from views.evolucion import render_evolucion
    assert callable(render_evolucion)


def test_evolucion_panel_importable():
    from views._evolucion_panel import _render_panel_evolucion_clinica
    assert callable(_render_panel_evolucion_clinica)


def test_evolucion_cuidador_importable():
    from views._evolucion_cuidador import _render_panel_cuidador
    assert callable(_render_panel_cuidador)


def test_render_estudios_importable():
    from views.estudios import render_estudios
    assert callable(render_estudios)
