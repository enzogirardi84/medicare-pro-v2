"""Tests for core.plugin_system."""
from __future__ import annotations


def test_test_plugin_system_importable():
    import core.plugin_system
    assert core.plugin_system is not None
