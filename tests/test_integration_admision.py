"""
Tests de integración para flujo de alta de pacientes

EJECUTAR:
    python -m pytest tests/test_integration_admision.py -v
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime


class TestAltaPacienteFlow:
    """Tests de integración para flujo completo de alta de paciente"""
    
    @pytest.fixture
    def mock_session_state(self):
        """Mock de session_state con datos de paciente"""
        return {
            "pacientes_db": {},
            "detalles_pacientes_db": {},
            "evoluciones_db": [],
            "vitales_db": [],
            "logs_db": [],
            "u_actual": {"nombre": "Dr. Test", "matricula": "12345"},
            "mi_empresa": "TestClinica"
        }
    
    def test_alta_paciente_success(self, mock_session_state):
        """Test alta exitosa de paciente nuevo"""
        from core.pacientes import alta_paciente
        
        datos_paciente = {
            "nombre": "Juan",
            "apellido": "Pérez",
            "dni": "12345678",
            "fecha_nacimiento": "1990-05-15",
            "sexo": "M",
            "telefono": "555-1234",
            "email": "juan@test.com",
            "direccion": "Calle 123",
            "obra_social": "OSDE"
        }
        
        resultado = alta_paciente(mock_session_state, datos_paciente)
        
        assert resultado["success"] is True
        assert resultado["paciente_id"] is not None
        assert "12345678" in mock_session_state["pacientes_db"]
    
    def test_alta_paciente_duplicate_dni(self, mock_session_state):
        """Test alta de paciente con DNI duplicado"""
        from core.pacientes import alta_paciente
        
        # Crear paciente existente
        mock_session_state["pacientes_db"]["12345678"] = "Pérez, Juan - 12345678"
        
        datos_paciente = {
            "nombre": "Pedro",
            "apellido": "Gómez",
            "dni": "12345678",  # Mismo DNI
        }
        
        resultado = alta_paciente(mock_session_state, datos_paciente)
        
        assert resultado["success"] is False
        assert "ya existe" in resultado["error"].lower()
    
    def test_alta_paciente_validation_error(self, mock_session_state):
        """Test alta con datos inválidos"""
        from core.pacientes import alta_paciente
        
        datos_invalidos = {
            "nombre": "",  # Vacío
            "apellido": "Pérez",
            "dni": "12345678"
        }
        
        resultado = alta_paciente(mock_session_state, datos_invalidos)
        
        assert resultado["success"] is False
        assert resultado["error"] is not None
    
    def test_alta_paciente_creates_audit_log(self, mock_session_state):
        """Test que el alta registra en logs de auditoría"""
        from core.pacientes import alta_paciente
        
        with patch("core.pacientes.registrar_auditoria") as mock_audit:
            datos_paciente = {
                "nombre": "Juan",
                "apellido": "Pérez",
                "dni": "12345678"
            }
            
            alta_paciente(mock_session_state, datos_paciente)
            
            # Verificar que se registró auditoría
            mock_audit.assert_called_once()


class TestBusquedaPaciente:
    """Tests de integración para búsqueda de pacientes"""
    
    @pytest.fixture
    def pacientes_mock(self):
        return {
            "12345678": "Pérez, Juan - 12345678",
            "87654321": "Gómez, María - 87654321",
            "11111111": "López, Pedro - 11111111"
        }
    
    def test_busqueda_por_dni(self, pacientes_mock):
        """Test búsqueda por DNI"""
        from core.pacientes import buscar_paciente
        
        resultado = buscar_paciente(pacientes_mock, "12345678")
        
        assert len(resultado) == 1
        assert "12345678" in resultado[0]
    
    def test_busqueda_por_apellido(self, pacientes_mock):
        """Test búsqueda por apellido"""
        from core.pacientes import buscar_paciente
        
        resultado = buscar_paciente(pacientes_mock, "perez")
        
        assert len(resultado) == 1
        assert "Pérez" in resultado[0]
    
    def test_busqueda_por_nombre(self, pacientes_mock):
        """Test búsqueda por nombre"""
        from core.pacientes import buscar_paciente
        
        resultado = buscar_paciente(pacientes_mock, "maria")
        
        assert len(resultado) == 1
        assert "María" in resultado[0]
    
    def test_busqueda_no_results(self, pacientes_mock):
        """Test búsqueda sin resultados"""
        from core.pacientes import buscar_paciente
        
        resultado = buscar_paciente(pacientes_mock, "inexistente")
        
        assert len(resultado) == 0


class TestActualizacionPaciente:
    """Tests de integración para actualización de pacientes"""
    
    @pytest.fixture
    def mock_session_state(self):
        return {
            "pacientes_db": {
                "12345678": "Pérez, Juan - 12345678"
            },
            "detalles_pacientes_db": {
                "12345678": {
                    "nombre": "Juan",
                    "apellido": "Pérez",
                    "dni": "12345678",
                    "telefono": "555-1234"
                }
            },
            "logs_db": [],
            "u_actual": {"nombre": "Dr. Test", "matricula": "12345"}
        }
    
    def test_actualizar_datos_paciente(self, mock_session_state):
        """Test actualización de datos de paciente"""
        from core.pacientes import actualizar_paciente
        
        nuevos_datos = {
            "telefono": "555-9999",
            "direccion": "Nueva dirección 456"
        }
        
        resultado = actualizar_paciente(mock_session_state, "12345678", nuevos_datos)
        
        assert resultado["success"] is True
        assert mock_session_state["detalles_pacientes_db"]["12345678"]["telefono"] == "555-9999"
    
    def test_actualizar_paciente_inexistente(self, mock_session_state):
        """Test actualización de paciente inexistente"""
        from core.pacientes import actualizar_paciente
        
        nuevos_datos = {"telefono": "555-9999"}
        
        resultado = actualizar_paciente(mock_session_state, "99999999", nuevos_datos)
        
        assert resultado["success"] is False
        assert "no existe" in resultado["error"].lower()
    
    def test_actualizar_creates_audit_log(self, mock_session_state):
        """Test que la actualización registra en auditoría"""
        from core.pacientes import actualizar_paciente
        
        with patch("core.pacientes.registrar_auditoria") as mock_audit:
            nuevos_datos = {"telefono": "555-9999"}
            actualizar_paciente(mock_session_state, "12345678", nuevos_datos)
            
            mock_audit.assert_called_once()


class TestHistorialPaciente:
    """Tests de integración para historial de paciente"""
    
    @pytest.fixture
    def mock_session_state(self):
        return {
            "evoluciones_db": [
                {"paciente_id": "12345678", "fecha": "2024-01-01", "nota": "Consulta 1"},
                {"paciente_id": "12345678", "fecha": "2024-01-15", "nota": "Consulta 2"},
                {"paciente_id": "87654321", "fecha": "2024-01-10", "nota": "Consulta otro"}
            ],
            "vitales_db": [
                {"paciente_id": "12345678", "fecha": "2024-01-01", "presion": "120/80"},
                {"paciente_id": "12345678", "fecha": "2024-01-15", "presion": "118/78"}
            ]
        }
    
    def test_obtener_historial_paciente(self, mock_session_state):
        """Test obtención de historial completo"""
        from core.pacientes import obtener_historial
        
        historial = obtener_historial(mock_session_state, "12345678")
        
        assert len(historial["evoluciones"]) == 2
        assert len(historial["vitales"]) == 2
    
    def test_historial_ordenado_por_fecha(self, mock_session_state):
        """Test que el historial está ordenado por fecha"""
        from core.pacientes import obtener_historial
        
        historial = obtener_historial(mock_session_state, "12345678")
        
        fechas = [e["fecha"] for e in historial["evoluciones"]]
        assert fechas == sorted(fechas, reverse=True)
    
    def test_historial_paciente_sin_datos(self, mock_session_state):
        """Test historial de paciente sin registros"""
        from core.pacientes import obtener_historial
        
        historial = obtener_historial(mock_session_state, "99999999")
        
        assert len(historial["evoluciones"]) == 0
        assert len(historial["vitales"]) == 0


class TestValidacionDatosPaciente:
    """Tests de integración para validación de datos"""
    
    def test_validar_dni_valido(self):
        """Test validación de DNI válido"""
        from core.input_validation import validar_dni
        
        assert validar_dni("12345678") is True
        assert validar_dni("1234567") is True
    
    def test_validar_dni_invalido(self):
        """Test validación de DNI inválido"""
        from core.input_validation import validar_dni
        
        assert validar_dni("") is False
        assert validar_dni("abc") is False
        assert validar_dni("123") is False  # Muy corto
    
    def test_validar_telefono(self):
        """Test validación de teléfono"""
        from core.input_validation import validar_telefono
        
        assert validar_telefono("555-1234") is True
        assert validar_telefono("+54 9 11 5555-1234") is True
        assert validar_telefono("123") is False  # Muy corto
    
    def test_validar_email(self):
        """Test validación de email"""
        from core.input_validation import validar_email
        
        assert validar_email("test@example.com") is True
        assert validar_email("test@subdomain.example.com") is True
        assert validar_email("invalid") is False
        assert validar_email("@example.com") is False
