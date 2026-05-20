"""Tests for views/admin_usuarios.py"""
from __future__ import annotations

from views.admin_usuarios import render_admin_usuarios


def test_render_admin_usuarios_imports():
    """render_admin_usuarios is a callable function."""
    assert callable(render_admin_usuarios)
