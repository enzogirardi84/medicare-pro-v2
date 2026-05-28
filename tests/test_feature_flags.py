"""Tests for core.feature_flags."""
from __future__ import annotations


def test_test_feature_flags_importable():
    import core.feature_flags
    assert core.feature_flags is not None
