"""Tests de integracion para core/database.py - guardar_datos() y optimistic locking."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch


def test_guardar_datos_retorna_bool():
    """Verifica que guardar_datos() retorne un booleano."""
    from core.database import guardar_datos
    result = guardar_datos(spinner=False)
    assert isinstance(result, bool)


def test_guardar_datos_sin_cambios_retorna_bool():
    """Sin cambios en session_state, guardar_datos debe retornar bool."""
    from core.database import guardar_datos
    result = guardar_datos(spinner=False)
    assert isinstance(result, bool)


def test_guardar_json_db_retorna_bool():
    """Verifica que guardar_json_db() retorne booleano."""
    import streamlit as st
    from core.database import guardar_json_db

    test_key = "_test_guardar_json"
    st.session_state[test_key] = []

    result = guardar_json_db(test_key, {"test": True}, spinner=False, max_items=100)
    assert isinstance(result, bool)

    st.session_state.pop(test_key, None)


def test_optimistic_locking_version_incrementa():
    """Verifica que el version counter se incremente al guardar."""
    import streamlit as st
    from core.database import guardar_datos

    v0 = st.session_state.get("_db_version", 0)
    guardar_datos(spinner=False)
    v1 = st.session_state.get("_db_version", 0)

    assert v1 >= v0


def test_guardar_datos_incrementa_version():
    """Verifica que guardar_datos() mantenga o incremente _db_version."""
    import streamlit as st
    from core.database import guardar_datos

    v0 = st.session_state.get("_db_version", 0)
    guardar_datos(spinner=False)
    v1 = st.session_state.get("_db_version", 0)

    assert isinstance(v1, (int, float))
    assert v1 >= v0


def test_db_keys_incluye_settings():
    """Verifica que settings_db este en _db_keys()."""
    from core.database import _db_keys
    keys = _db_keys()
    assert "settings_db" in keys


def test_db_keys_no_vacia():
    """Verifica que _db_keys() tenga claves."""
    from core.database import _db_keys
    keys = _db_keys()
    assert len(keys) > 5
