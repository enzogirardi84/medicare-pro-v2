"""Tests para core._patient_index."""
from __future__ import annotations

import pytest


class TestPatientIndex:
    """Tests para funciones públicas de core._patient_index."""

    def test__patient_index_importable(self):
        import core._patient_index
        assert core._patient_index is not None

    def test_functions_exist(self):
        import core._patient_index
        assert callable(core._patient_index.get_patient_records)
        assert callable(core._patient_index.invalidate_index)
        assert callable(core._patient_index.get_all_patient_records_paginated)
