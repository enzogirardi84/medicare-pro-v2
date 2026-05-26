"""Tests para views/clinica.py -- signos vitales."""
from __future__ import annotations


def test_render_clinica_importable():
    """Verifica que render_clinica sea importable."""
    from views.clinica import render_clinica
    assert callable(render_clinica)


def test_rangos_vitales_completos():
    """Verifica que los rangos vitales tengan todas las claves esperadas."""
    from views.clinica import _RANGOS_VIT
    for clave, rango in _RANGOS_VIT.items():
        assert "min" in rango, f"{clave} falta min"
        assert "max" in rango, f"{clave} falta max"
        assert "crit_min" in rango, f"{clave} falta crit_min"
        assert "crit_max" in rango, f"{clave} falta crit_max"
        assert "unidad" in rango, f"{clave} falta unidad"
        assert rango["min"] <= rango["max"], f"{clave}: min > max"
        assert rango["crit_min"] <= rango["min"], f"{clave}: crit_min > min"
        assert rango["max"] <= rango["crit_max"], f"{clave}: max > crit_max"


def test_evaluar_vit_returns_string():
    """Verifica que _evaluar_vit retorne un string de estado."""
    from views.clinica import _evaluar_vit
    from views._dashboard_utils import _RANGOS_DASH
    estados_validos = {"normal", "alerta", "critico", "sin_dato"}
    for clave in _RANGOS_DASH:
        resultado = _evaluar_vit(clave, 75)
        assert resultado in estados_validos, f"{clave}: {resultado!r} no es valido"
