"""Tests for core.module_catalog."""
from __future__ import annotations


def test_test_module_catalog_importable():
    import core.module_catalog
    assert core.module_catalog is not None
