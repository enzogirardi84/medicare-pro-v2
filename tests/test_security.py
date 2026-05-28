"""Tests para core.security."""
from __future__ import annotations

import pytest


class TestSecurity:
    """Tests para funciones públicas de core.security."""

    def test_security_importable(self):
        import core.security
        assert core.security is not None

    def test_functions_exist(self):
        import core.security
        assert callable(core.security.encrypt_field)
        assert callable(core.security.decrypt_field)
