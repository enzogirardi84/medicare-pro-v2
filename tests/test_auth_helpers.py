"""Tests reales para helpers de core.auth (extraídos del refactor render_login)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

# Las funciones refactorizadas se testean desde sus helpers públicos


class TestAuthHelperFunctions:
    """Prueba funciones auxiliares de auth que no dependen de Streamlit runtime."""

    @patch("core.auth.st")
    def test_intentar_login_emergencia_exitoso(self, mock_st):
        """Emergency login con credenciales correctas llama a _completar_login_exitoso."""
        from core.auth import _intentar_login_emergencia, DEFAULT_ADMIN_USER, logins_clave_default_superadmin

        # Simular usuario admin y emergency password
        admin_logins = logins_clave_default_superadmin()
        emergency_pwd = "emergencia123"
        mock_st.session_state = {}

        with (
            patch("core.auth.obtener_emergency_password", return_value=emergency_pwd),
            patch("core.auth.secrets.compare_digest", return_value=True),
            patch("core.auth.limpiar_fallos_login") as mock_limpiar,
            patch("core.auth._completar_login_exitoso") as mock_completar,
            patch("core.auth.aplicar_hash_tras_login_ok"),
            patch("core.auth.bcrypt_rounds_config", return_value=12),
        ):
            result = _intentar_login_emergencia("admin", emergency_pwd, None)
            assert result is True or mock_completar.called
            mock_limpiar.assert_called_once_with("admin")
            assert mock_st.session_state["usuarios_db"]["admin"]["usuario_login"] == "admin"

    def test_login_emergencia_se_intenta_antes_de_cargar_db(self):
        """Permite recuperar acceso aunque Supabase no responda."""
        from core.auth import _procesar_login

        with (
            patch("core.auth.puede_intentar_login", return_value=(True, "")),
            patch("core.auth._intentar_login_emergencia", return_value=True) as mock_emergency,
            patch("core.auth._cargar_db_login") as mock_cargar,
        ):
            _procesar_login("Clinica", "enzogirardi", "clave")

        mock_emergency.assert_called_once_with("enzogirardi", "clave", None)
        mock_cargar.assert_not_called()

    def test_intentar_login_emergencia_falla_sin_emergency_pwd(self):
        """Si no hay emergency password configurada, retorna False."""
        from core.auth import _intentar_login_emergencia

        with patch("core.auth.obtener_emergency_password", return_value=""):
            result = _intentar_login_emergencia("admin", "cualquier", None)
            assert result is False

    def test_session_timeout_default(self):
        """Timeout por defecto 480 min (8h), clamp entre 15 y 720."""
        with patch("core.auth.st.secrets", {"SESSION_TIMEOUT_MINUTES": 480}, create=True):
            from core.auth import _session_timeout_minutes
            assert _session_timeout_minutes() == 480

    def test_session_timeout_clamp_low(self):
        with patch("core.auth.st.secrets", {"SESSION_TIMEOUT_MINUTES": 5}, create=True):
            from core.auth import _session_timeout_minutes
            assert _session_timeout_minutes() == 15  # clamp mínimo

    def test_session_timeout_clamp_high(self):
        with patch("core.auth.st.secrets", {"SESSION_TIMEOUT_MINUTES": 9999}, create=True):
            from core.auth import _session_timeout_minutes
            assert _session_timeout_minutes() == 720  # clamp máximo

    def test_session_timeout_fallback_on_error(self):
        with patch("core.auth.st.secrets", {}, create=True):
            from core.auth import _session_timeout_minutes
            assert _session_timeout_minutes() == 480

    def test_auth_strip_pwreset_query_param_no_qp(self):
        """No falla si st.query_params no está disponible."""
        from core.auth import _auth_strip_pwreset_query_param
        with patch("core.auth.st.query_params", None, create=True):
            _auth_strip_pwreset_query_param()  # no debe lanzar
