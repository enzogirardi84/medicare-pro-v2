"""Tests para core.release_notes."""
from __future__ import annotations


def test_release_notes_importable():
    import core.release_notes
    assert core.release_notes is not None
