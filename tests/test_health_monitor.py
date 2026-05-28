"""Tests for core.health_monitor."""
from __future__ import annotations


def test_test_health_monitor_importable():
    import core.health_monitor
    assert core.health_monitor is not None
