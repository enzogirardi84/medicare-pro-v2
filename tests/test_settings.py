from __future__ import annotations

import re

from views.settings import (
    get_environment,
    get_os_info,
    get_python_version,
    get_version,
    render_settings_page,
)


def test_render_settings_page_imports():
    assert callable(render_settings_page)


def test_get_version_returns_string():
    v = get_version()
    assert isinstance(v, str)


def test_get_environment_returns_string():
    env = get_environment()
    assert isinstance(env, str)


def test_get_python_version_returns_valid():
    v = get_python_version()
    assert re.fullmatch(r"\d+\.\d+\.\d+", v), f"{v!r} does not match major.minor.micro"


def test_get_os_info_returns_string():
    os_info = get_os_info()
    assert isinstance(os_info, str) and len(os_info) > 0


def test_guardar_configuracion_forces_first_save(monkeypatch):
    import views.settings as settings_view

    called = {}

    def fake_guardar_datos(*, spinner=None, force=False):
        called["spinner"] = spinner
        called["force"] = force

    monkeypatch.setattr(settings_view, "guardar_datos", fake_guardar_datos)

    settings_view._guardar_configuracion()

    assert called == {"spinner": False, "force": True}


def test_guardar_datos_force_marks_initial_load_done(monkeypatch):
    import streamlit as st
    import core.database as database

    st.session_state.clear()
    st.session_state["_db_initial_load_done"] = False
    monkeypatch.setattr(database, "_guardar_datos_ejecutar", lambda: None)

    database.guardar_datos(spinner=False, force=True)

    assert st.session_state["_db_initial_load_done"] is True
