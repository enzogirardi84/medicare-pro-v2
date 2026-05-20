"""Tests for core/_patient_index.py"""
from __future__ import annotations

import streamlit as st
from core._patient_index import get_patient_records, invalidate_index, _rebuild_index


def test_get_patient_records_empty_on_no_data():
    """Returns empty list when no records exist."""
    st.session_state.pop("_idx_test_db", None)
    st.session_state.pop("test_db", None)
    result = get_patient_records("test_db", "Paciente X")
    assert result == []


def test_get_patient_records_filters_by_patient():
    """Returns only records matching the patient."""
    st.session_state["test_db"] = [
        {"paciente": "Paciente A", "dato": "1"},
        {"paciente": "Paciente B", "dato": "2"},
        {"paciente": "Paciente A", "dato": "3"},
    ]
    st.session_state.pop("_idx_ts_test_db", None)  # force rebuild
    result = get_patient_records("test_db", "Paciente A")
    assert len(result) == 2
    assert all(r["paciente"] == "Paciente A" for r in result)


def test_get_patient_records_empty_paciente():
    """Returns empty list when paciente_sel is empty."""
    assert get_patient_records("test_db", "") == []
    assert get_patient_records("test_db", None) == []


def test_invalidate_index_forces_rebuild():
    """Invalidation resets the timestamp, forcing rebuild."""
    st.session_state["test_db"] = [{"paciente": "P", "dato": "v1"}]
    _ = get_patient_records("test_db", "P")  # build cache
    invalidate_index("test_db")
    ts = st.session_state.get("_idx_ts_test_db", 999)
    assert ts == 0.0


def test_rebuild_index_on_stale_data():
    """Getting records after invalidation returns fresh data."""
    st.session_state["test_db"] = [{"paciente": "P", "dato": "v1"}]
    _ = get_patient_records("test_db", "P")
    invalidate_index("test_db")
    # change data
    st.session_state["test_db"].append({"paciente": "P", "dato": "v2"})
    result = get_patient_records("test_db", "P")
    assert len(result) == 2


def test_rebuild_index_handles_non_list():
    """Does not crash if db_key is not a list."""
    st.session_state["test_db"] = "not a list"
    # should not raise
    result = get_patient_records("test_db", "P")
    assert result == []


def test_rebuild_index_handles_non_dict_items():
    """Skips items that are not dicts."""
    st.session_state["test_db"] = [
        {"paciente": "P", "dato": "ok"},
        "not a dict",
        42,
    ]
    st.session_state.pop("_idx_ts_test_db", None)
    result = get_patient_records("test_db", "P")
    assert len(result) == 1
