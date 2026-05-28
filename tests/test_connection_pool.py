"""Tests for core.connection_pool."""
from __future__ import annotations


def test_test_connection_pool_importable():
    import core.connection_pool
    assert core.connection_pool is not None
