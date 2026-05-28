"""Tests para core.security_middleware."""
from __future__ import annotations

import pytest


class TestSecurityMiddleware:
    """Tests para funciones públicas de core.security_middleware."""

    def test_security_middleware_importable(self):
        import core.security_middleware
        assert core.security_middleware is not None

    def test_functions_exist(self):
        import core.security_middleware
        assert callable(core.security_middleware.generar_csp_header)
        assert callable(core.security_middleware.detectar_api_key_en_texto)
        assert callable(core.security_middleware.sanitize_clinical_text)
        assert callable(core.security_middleware.sanitize_search_term)
        assert callable(core.security_middleware.detect_sql_injection)
        assert callable(core.security_middleware.detect_xss)
        assert callable(core.security_middleware.sanitize_string)
        assert callable(core.security_middleware.sanitize_dict)
        assert callable(core.security_middleware.sanitize_list)
        assert callable(core.security_middleware.validate_dni)
