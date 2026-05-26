"""Tests for sidebar_components._cached_contexto and performance optimizations."""

from core.sidebar_components import _cached_contexto


def test_cached_contexto_empty():
    """Debe manejar paciente_sel vacio sin errores."""
    ctx = _cached_contexto("")
    assert isinstance(ctx, dict)
    assert ctx["detalles"] == {}
    assert ctx["vitales_top3"] == []
    assert ctx["ultima_ev"] is None
    assert ctx["activas"] == []


def test_cached_contexto_transport():
    """Verifica que los datos se transporten correctamente."""
    ctx = _cached_contexto("")
    for key in ("detalles", "vitales_top3", "ultima_ev", "activas"):
        assert key in ctx, f"Falta clave {key}"
