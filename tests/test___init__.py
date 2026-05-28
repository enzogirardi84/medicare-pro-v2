"""Tests para views.__init__."""
from __future__ import annotations


def test___init___importable():
    import views.__init__
    assert views.__init__ is not None
