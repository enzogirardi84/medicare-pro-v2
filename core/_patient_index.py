"""Patient-indexed cache for session_state lists. Eliminates O(n) full scans on every rerun."""
from __future__ import annotations

import time

import streamlit as st


def get_patient_records(db_key: str, paciente_sel: str) -> list[dict]:
    """Get records for a specific patient using indexed cache. ~O(1) instead of O(n)."""
    if not paciente_sel:
        return []

    idx_key = f"_idx_{db_key}"
    ts_key = f"_idx_ts_{db_key}"
    src_hash = str(id(st.session_state.get(db_key, [])))

    cached_ts = st.session_state.get(ts_key, 0.0)
    cached_src = st.session_state.get(ts_key + "_src", "")

    if cached_src != src_hash or (time.monotonic() - cached_ts) > 5.0:
        _rebuild_index(db_key)

    return st.session_state.get(idx_key, {}).get(paciente_sel, [])


def _rebuild_index(db_key: str) -> None:
    """Rebuild the patient index for a given db_key."""
    idx_key = f"_idx_{db_key}"
    ts_key = f"_idx_ts_{db_key}"
    src_key = ts_key + "_src"

    raw = st.session_state.get(db_key, [])
    if not isinstance(raw, list):
        st.session_state[idx_key] = {}
        st.session_state[ts_key] = time.monotonic()
        st.session_state[src_key] = str(id(raw))
        return

    index: dict[str, list[dict]] = {}
    for record in raw:
        if isinstance(record, dict):
            paciente = record.get("paciente", "")
            if paciente:
                index.setdefault(paciente, []).append(record)

    st.session_state[idx_key] = index
    st.session_state[ts_key] = time.monotonic()
    st.session_state[src_key] = str(id(raw))


def invalidate_index(db_key: str) -> None:
    """Force index rebuild on next access. Call this after mutating the list."""
    ts_key = f"_idx_ts_{db_key}"
    st.session_state[ts_key] = 0.0


def get_all_patient_records_paginated(db_key: str, paciente_sel: str, limit: int = 200) -> list[dict]:
    """Get records with limit. Uses index."""
    records = get_patient_records(db_key, paciente_sel)
    return records[-limit:] if len(records) > limit else records
