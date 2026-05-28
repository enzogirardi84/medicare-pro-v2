"""Tests para core._database_local."""
from __future__ import annotations


def test__database_local_importable():
    import core._database_local
    assert core._database_local is not None
