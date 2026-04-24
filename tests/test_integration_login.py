"""
Tests de integración para flujo de login

EJECUTAR:
    python -m pytest tests/test_integration_login.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestLoginFlow:
    """Tests de integración para flujo completo de login"""
    
    @pytest.fixture
    def mock_session_state(self):
        """Mock de session_state de Streamlit"""
        return {
            "usuarios_db": {
                "admin": {
                    "nombre": "Administrador",
                    "password_hash": "hashed_password",
                    "pin": "1234",
                    "rol": "admin",
                    "empresa": "TestClinica",
                    "activo": True
                }
            },
            "logeado": False,
            "u_actual": None,
            "logs_db": []
        }
    
    def test_login_success(self, mock_session_state):
        """Test login exitoso con credenciales válidas"""
        from core.auth import verificar_login
        
        # Simular verificación de password
        with patch("core.auth._verify_password", return_value=True):
            with patch("core.auth._pin_coincide", return_value=True):
                resultado = verificar_login(
                    mock_session_state,
                    "admin",
                    "password123",
                    "1234",
                    "TestClinica"
                )
                
                assert resultado is True
                assert mock_session_state["logeado"] is True
                assert mock_session_state["u_actual"] is not None
    
    def test_login_invalid_password(self, mock_session_state):
        """Test login fallido con password incorrecto"""
        from core.auth import verificar_login
        
        with patch("core.auth._verify_password", return_value=False):
            resultado = verificar_login(
                mock_session_state,
                "admin",
                "wrong_password",
                "1234",
                "TestClinica"
            )
            
            assert resultado is False
            assert mock_session_state["logeado"] is False
    
    def test_login_invalid_pin(self, mock_session_state):
        """Test login fallido con PIN incorrecto"""
        from core.auth import verificar_login
        
        with patch("core.auth._verify_password", return_value=True):
            with patch("core.auth._pin_coincide", return_value=False):
                resultado = verificar_login(
                    mock_session_state,
                    "admin",
                    "password123",
                    "9999",  # PIN incorrecto
                    "TestClinica"
                )
                
                assert resultado is False
    
    def test_login_user_not_found(self, mock_session_state):
        """Test login con usuario inexistente"""
        from core.auth import verificar_login
        
        resultado = verificar_login(
            mock_session_state,
            "nonexistent_user",
            "password123",
            "1234",
            "TestClinica"
        )
        
        assert resultado is False
    
    def test_login_user_inactive(self, mock_session_state):
        """Test login con usuario inactivo"""
        from core.auth import verificar_login
        
        # Marcar usuario como inactivo
        mock_session_state["usuarios_db"]["admin"]["activo"] = False
        
        resultado = verificar_login(
            mock_session_state,
            "admin",
            "password123",
            "1234",
            "TestClinica"
        )
        
        assert resultado is False
    
    def test_login_logs_audit(self, mock_session_state):
        """Test que el login registra en auditoría"""
        from core.auth import verificar_login
        
        with patch("core.auth._verify_password", return_value=True):
            with patch("core.auth._pin_coincide", return_value=True):
                with patch("core.auth.registrar_auditoria") as mock_audit:
                    verificar_login(
                        mock_session_state,
                        "admin",
                        "password123",
                        "1234",
                        "TestClinica"
                    )
                    
                    # Verificar que se registró auditoría
                    mock_audit.assert_called_once()


class TestPasswordResetFlow:
    """Tests de integración para flujo de reset de password"""
    
    def test_password_reset_token_generation(self):
        """Test generación de token de reset"""
        from core.password_reset_token import generar_token_reset
        
        token = generar_token_reset("admin")
        assert token is not None
        assert len(token) > 20
    
    def test_password_reset_token_validation(self):
        """Test validación de token de reset"""
        from core.password_reset_token import generar_token_reset, validar_token_reset
        
        token = generar_token_reset("admin")
        usuario = validar_token_reset(token)
        
        assert usuario == "admin"
    
    def test_password_reset_token_invalid(self):
        """Test validación de token inválido"""
        from core.password_reset_token import validar_token_reset
        
        usuario = validar_token_reset("token_invalido")
        assert usuario is None
    
    def test_password_reset_token_expired(self):
        """Test expiración de token"""
        from core.password_reset_token import generar_token_reset, validar_token_reset
        import time
        
        # Generar token con TTL muy corto
        token = generar_token_reset("admin", ttl_seconds=0)
        time.sleep(0.1)
        
        usuario = validar_token_reset(token)
        assert usuario is None


class Test2FAFlow:
    """Tests de integración para 2FA"""
    
    def test_2fa_code_generation(self):
        """Test generación de código 2FA"""
        from core.email_2fa import generar_codigo_2fa
        
        codigo = generar_codigo_2fa()
        assert len(codigo) == 6
        assert codigo.isdigit()
    
    def test_2fa_verification_success(self):
        """Test verificación exitosa de código 2FA"""
        from core.email_2fa import generar_codigo_2fa, verificar_codigo_2fa
        
        codigo = generar_codigo_2fa()
        resultado = verificar_codigo_2fa(codigo, codigo)
        
        assert resultado is True
    
    def test_2fa_verification_failure(self):
        """Test verificación fallida de código 2FA"""
        from core.email_2fa import generar_codigo_2fa, verificar_codigo_2fa
        
        codigo_real = generar_codigo_2fa()
        resultado = verificar_codigo_2fa("000000", codigo_real)
        
        assert resultado is False


class TestSessionManagement:
    """Tests de integración para manejo de sesiones"""
    
    def test_session_creation(self):
        """Test creación de sesión de usuario"""
        from core.auth import crear_sesion
        
        usuario = {
            "nombre": "Test User",
            "rol": "medico",
            "empresa": "TestClinica"
        }
        
        session_state = {}
        crear_sesion(session_state, usuario)
        
        assert session_state["logeado"] is True
        assert session_state["u_actual"] == usuario
    
    def test_session_logout(self):
        """Test cierre de sesión"""
        from core.auth import cerrar_sesion
        
        session_state = {
            "logeado": True,
            "u_actual": {"nombre": "Test"},
            "_last_activity": "some_time"
        }
        
        cerrar_sesion(session_state)
        
        assert session_state["logeado"] is False
        assert session_state["u_actual"] is None
    
    def test_session_timeout_detection(self):
        """Test detección de timeout de sesión"""
        from core.auth import verificar_timeout_sesion
        import time
        
        session_state = {
            "_last_activity": time.time() - 3600  # 1 hora atrás
        }
        
        timeout_excedido = verificar_timeout_sesion(session_state, timeout_minutes=30)
        assert timeout_excedido is True
