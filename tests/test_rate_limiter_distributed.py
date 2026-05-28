"""Tests for core.rate_limiter_distributed."""
from __future__ import annotations


def test_test_rate_limiter_distributed_importable():
    import core.rate_limiter_distributed
    assert core.rate_limiter_distributed is not None
