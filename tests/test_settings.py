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
