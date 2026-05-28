"""Tests for core.service_worker."""
from __future__ import annotations


def test_test_service_worker_importable():
    import core.service_worker
    assert core.service_worker is not None
