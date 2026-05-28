"""Tests for core.health_check."""
from __future__ import annotations


def test_test_health_check_importable():
    import core.health_check
    assert core.health_check is not None
