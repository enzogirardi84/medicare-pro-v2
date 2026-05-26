"""Tests para views/recetas.py -- regresiones en módulo de recetas."""
from __future__ import annotations


def test_render_recetas_importable():
    """Verifica que render_recetas sea importable."""
    from views.recetas import render_recetas
    assert callable(render_recetas)


def test_recetas_utils_importable():
    """Verifica que _recetas_utils tenga las funciones esperadas."""
    from views._recetas_utils import render_tabla_clinica
    assert callable(render_tabla_clinica)


def test_recetas_mar_importable():
    """Verifica que _recetas_mar tenga las funciones esperadas."""
    from views._recetas_mar import (
        render_cortina_mar_hospitalaria,
        registrar_administracion_dosis,
        guardar_administracion_medicacion,
    )
    for fn in (render_cortina_mar_hospitalaria, registrar_administracion_dosis,
               guardar_administracion_medicacion):
        assert callable(fn)
