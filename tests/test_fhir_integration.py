"""Tests for core.fhir_integration."""
from __future__ import annotations


def test_test_fhir_integration_importable():
    import core.fhir_integration
    assert core.fhir_integration is not None
