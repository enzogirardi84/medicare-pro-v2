"""Tests for core.sql_optimizer."""
from __future__ import annotations


def test_test_sql_optimizer_importable():
    import core.sql_optimizer
    assert core.sql_optimizer is not None
