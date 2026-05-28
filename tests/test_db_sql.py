"""Tests para core.db_sql."""
from __future__ import annotations


def test_db_sql_importable():
    import core.db_sql
    assert core.db_sql is not None
