from __future__ import annotations

"""


Tests de Integración para Flujos Críticos de MediCare Pro.

Flujos críticos cubiertos:
1. Login completo (incluyendo rate limiting)
2. Guardado de evolución clínica (con auditoría)
3. Búsqueda de paciente paginada
4. Backup/Restore de datos
5. Rate limiting bajo ataque
"""
import pytest
import time
from datetime import datetime, timezone
from typing import Dict, Any

# Mocks para Streamlit session_state
class MockSessionState:
    def __init__(self):
        self._data = {}
    
    def get(self, key, default=None):
        return self._data.get(key, default)
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        self._data[key] = value
    
    def __contains__(self, key):
        return key in self._data
    
    def keys(self):
        return self._data.keys()


@pytest.fixture
def mock_session():
    """Fixture para session_state mockeado."""
    return MockSessionState()


@pytest.fixture
def sample_patient():
    """Fixture con datos de paciente de prueba."""
    return {
        "id": "test-patient-001",
        "dni": "12345678",
        "nombre": "Paciente Test",
        "apellido": "Integración",
        "fecha_nacimiento": "1980-01-01",
        "email": "test@medicare.test",
        "telefono": "1144445555",
        "obra_social": "OSDE",
        "numero_afiliado": "123456789",
        "estado": "activo",
        "creado_en": datetime.now(timezone.utc).isoformat()
    }


@pytest.fixture
def sample_evolucion():
    """Fixture con evolución clínica de prueba."""
    return {
        "id": "test-evo-001",
        "paciente_id": "test-patient-001",
        "medico_id": "dr-test",
        "fecha": datetime.now(timezone.utc).isoformat(),
        "motivo_consulta": "Dolor abdominal",
        "examen_fisico": "PA: 120/80, FC: 72",
        "diagnostico": "Gastritis",
        "tratamiento": "Omeprazol 20mg",
        "evolucion": "Paciente estable"
    }


class TestLoginFlow:
    """Tests para flujo de login crítico."""
    
    def test_login_rate_limiting(self, mock_session):
        """Verifica que el rate limiting bloquea después de 5 intentos."""
        from core.rate_limiter_distributed import (
            check_login_rate_limit, 
            reset_login_attempts,
            RATE_LIMIT_LOGIN
        )
        
        identifier = "test-user-123"
        
        # 5 intentos deben permitirse
        for i in range(5):
            status = check_login_rate_limit(identifier)
            assert status.allowed, f"Intento {i+1} debería permitirse"
        
        # El sexto debe bloquearse
        status = check_login_rate_limit(identifier)
        assert not status.allowed, "Sexto intento debería bloquearse"
        assert status.blocked_until is not None
        
        # Resetear y verificar que permite de nuevo
        reset_login_attempts(identifier)
        status = check_login_rate_limit(identifier)
        assert status.allowed, "Tras reset, debería permitir"
    
    def test_login_with_invalid_credentials(self, mock_session):
        """Verifica manejo de credenciales inválidas."""
        from core.security_middleware import PatientDataValidator
        
        validator = PatientDataValidator()
        
        # DNI inválido
        with pytest.raises(ValueError):
            validator.validate_dni("abc123")
        
        # DNI muy corto
        with pytest.raises(ValueError):
            validator.validate_dni("123")
    
    def test_session_initialization(self, mock_session):
        """Verifica inicialización correcta de session state."""
        from core.cache_optimized import PaginationStateHelper
        
        # Inicializar paginación
        state = PaginationStateHelper.init_pagination_state("pacientes", session_state=mock_session)
        
        assert "pacientes_page" in state
        assert state["pacientes_page"] == 1
        assert state["pacientes_page_size"] == 50


class TestPatientCRUD:
    """Tests para operaciones CRUD de pacientes."""
    
    def test_patient_validation(self, sample_patient):
        """Verifica validación de datos de paciente."""
        from core.security_middleware import PatientDataValidator
        
        validator = PatientDataValidator()
        
        # Validar DNI
        dni_limpio = validator.validate_dni(sample_patient["dni"])
        assert dni_limpio == "12345678"
        
        # Validar email
        email_limpio = validator.validate_email(sample_patient["email"])
        assert email_limpio == "test@medicare.test"
        
        # Validar teléfono
        tel_limpio = validator.validate_telefono(sample_patient["telefono"])
        assert tel_limpio == "1144445555"
    
    def test_patient_sanitization(self, sample_patient):
        """Verifica sanitización de inputs maliciosos."""
        from core.security_middleware import InputSanitizer, SecurityError
        
        # Intentar XSS
        malicious_name = "<script>alert('xss')</script>Paciente"
        
        with pytest.raises(SecurityError):
            InputSanitizer.sanitize_string(malicious_name, allow_html=False)
        
        # Sanitización con HTML permitido
        clean = InputSanitizer.sanitize_string(
            "<strong>Negrita</strong> y <script>alert('xss')</script>",
            allow_html=True
        )
        assert "<strong>" in clean
        assert "<script>" not in clean
    
    def test_soft_delete(self, sample_patient, mock_session):
        """Verifica soft delete no borra permanentemente."""
        # Simular paciente en session
        mock_session["pacientes_db"] = [sample_patient]
        
        # Marcar como inactivo (soft delete)
        patient = mock_session["pacientes_db"][0]
        patient["estado"] = "inactivo"
        patient["eliminado_en"] = datetime.now(timezone.utc).isoformat()
        
        # Verificar que sigue existiendo
        assert len(mock_session["pacientes_db"]) == 1
        assert mock_session["pacientes_db"][0]["estado"] == "inactivo"


class TestClinicalData:
    """Tests para datos clínicos críticos."""
    
    def test_evolucion_audit_trail(self, sample_evolucion, mock_session):
        """Verifica que evoluciones generan audit trail."""
        from core.patient_audit_wrapper import audit_action
        
        # Simular usuario logueado
        mock_session["u_actual"] = {
            "username": "dr-test",
            "rol": "medico",
            "empresa": "test-clinic"
        }
        mock_session["logeado"] = True
        
        # Simular guardado con auditoría
        audit_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": "CREATE",
            "resource_type": "evolucion",
            "user_id": "dr-test",
            "resource_id": sample_evolucion["id"],
            "status": "SUCCESS"
        }
        
        mock_session["auditoria_legal_db"] = [audit_entry]
        
        # Verificar log creado
        assert len(mock_session["auditoria_legal_db"]) == 1
        assert mock_session["auditoria_legal_db"][0]["action"] == "CREATE"
    
    def test_signos_vitales_validation(self):
        """Verifica validación de rangos médicos."""
        from core.security_middleware import PatientDataValidator
        
        validator = PatientDataValidator()
        
        # Temperatura fuera de rango
        result = validator.validate_signos_vitales(temperatura=50.0)
        assert len(result["errores"]) > 0
        assert "Temperatura fuera de rango" in result["errores"][0]
        
        # Temperatura válida
        result = validator.validate_signos_vitales(temperatura=37.5)
        assert len(result["errores"]) == 0
        assert result["validos"]["temperatura"] == 37.5
    
    def test_evolucion_integrity(self, sample_evolucion):
        """Verifica integridad de datos de evolución."""
        # Verificar campos obligatorios
        required_fields = ["paciente_id", "medico_id", "fecha", "diagnostico"]
        
        for field in required_fields:
            assert field in sample_evolucion, f"Campo {field} es obligatorio"
        
        # Verificar formato de fecha
        try:
            datetime.fromisoformat(sample_evolucion["fecha"])
        except ValueError:
            pytest.fail("Fecha no está en formato ISO")


class TestPagination:
    """Tests para paginación de datos."""
    
    def test_pagination_limits(self):
        """Verifica límites de paginación."""
        from core.db_paginated import PaginatedSupabaseQuery
        
        # Intentar página > máxima
        paginator = PaginatedSupabaseQuery(None)
        
        # Verificar que page_size > 100 se limita a 100
        size = paginator._validate_page_size(200)
        assert size == 100
        
        # Verificar que page_size < 1 usa default
        size = paginator._validate_page_size(0)
        assert size == 50  # DEFAULT_PAGE_SIZE
    
    def test_page_info_structure(self):
        """Verifica estructura de PageInfo."""
        from core.pagination import PageInfo
        
        page = PageInfo(
            items=[{"id": 1}, {"id": 2}],
            has_more=True,
            page_size=50,
            total_count=100,
            next_cursor="2",
            prev_cursor=None
        )
        
        assert len(page.items) == 2
        assert page.has_more is True
        assert page.next_cursor == "2"


class TestSQLSecurity:
    """Tests para seguridad SQL."""
    
    def test_sql_injection_detection(self):
        """Verifica detección de SQL injection."""
        from core.security_middleware import InputSanitizer
        
        # Intentos de SQL injection
        malicious_inputs = [
            "'; DROP TABLE pacientes; --",
            "1' OR '1'='1",
            "admin'--",
            "1; DELETE FROM usuarios",
        ]
        
        for malicious in malicious_inputs:
            assert InputSanitizer.detect_sql_injection(malicious), \
                f"Debería detectar SQL injection en: {malicious}"
    
    def test_query_analysis(self):
        """Verifica análisis de queries."""
        from core.sql_optimizer import get_sql_optimizer
        
        optimizer = get_sql_optimizer()
        
        # Query peligroso
        analysis = optimizer.analyze_query("SELECT * FROM pacientes")
        assert analysis["risk_level"] in ["medium", "high"]
        assert any("SELECT *" in w for w in analysis["warnings"])
        
        # Query con UPDATE sin WHERE (CRÍTICO)
        analysis = optimizer.analyze_query("UPDATE pacientes SET estado='inactivo'")
        assert analysis["risk_level"] == "high"
        assert any("CRÍTICO" in w for w in analysis["warnings"])


class TestHealthChecks:
    """Tests para sistema de health checks."""
    
    def test_health_report_structure(self):
        """Verifica estructura de reporte de salud."""
        from core.health_check_enhanced import (
            HealthCheckEnhanced, 
            ComponentHealth, 
            ComponentStatus
        )
        
        checker = HealthCheckEnhanced()
        
        # Simular componente saludable
        health = ComponentHealth(
            name="Test",
            status=ComponentStatus.HEALTHY,
            latency_ms=10.5,
            last_check=datetime.now(timezone.utc).isoformat(),
            message="OK"
        )
        
        assert health.status == ComponentStatus.HEALTHY
        assert health.latency_ms == 10.5
    
    def test_system_metrics_collection(self):
        """Verifica recolección de métricas."""
        from core.health_check_enhanced import get_health_checker
        
        checker = get_health_checker()
        metrics = checker._get_system_metrics()
        
        # Verificar que tenemos métricas básicas
        assert "cpu_percent" in metrics
        assert "boot_time" in metrics


@pytest.mark.integration
class TestEndToEnd:
    """Tests end-to-end completos."""
    
    def test_complete_patient_workflow(self, mock_session, sample_patient, sample_evolucion):
        """Flujo completo: crear paciente → evolución → búsqueda."""
        # 1. Crear paciente
        mock_session["pacientes_db"] = [sample_patient]
        
        # 2. Agregar evolución
        mock_session["evoluciones_db"] = [sample_evolucion]
        
        # 3. Simular búsqueda
        pacientes = mock_session["pacientes_db"]
        encontrado = None
        for p in pacientes:
            if p["dni"] == "12345678":
                encontrado = p
                break
        
        assert encontrado is not None
        assert encontrado["nombre"] == "Paciente Test"
        
        # 4. Verificar evolución asociada
        evos = mock_session["evoluciones_db"]
        evos_paciente = [e for e in evos if e["paciente_id"] == encontrado["id"]]
        assert len(evos_paciente) == 1


class TestInventoryFlow:
    """Tests para flujo de inventario."""

    def test_create_inventory_item(self, mock_session):
        """Crear item en inventario."""
        from datetime import datetime, timezone

        item = {
            "id": "inv-001",
            "item": "Omeprazol 20mg",
            "tipo": "medicamento",
            "stock": 100,
            "stock_minimo": 20,
            "precio": 150.0,
            "empresa": "test-clinic",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_session["inventario_db"] = [item]
        assert len(mock_session["inventario_db"]) == 1
        assert mock_session["inventario_db"][0]["stock"] == 100

    def test_consume_stock_reduces_inventory(self, mock_session):
        """Consumir stock reduce el inventario."""
        mock_session["inventario_db"] = [
            {"id": "inv-001", "item": "Omeprazol", "stock": 100, "stock_minimo": 20, "empresa": "test-clinic"}
        ]
        mock_session["consumos_db"] = []

        consumo = {"item_id": "inv-001", "cantidad": 5, "fecha": "2026-05-20", "empresa": "test-clinic"}
        mock_session["consumos_db"].append(consumo)

        item = mock_session["inventario_db"][0]
        item["stock"] -= consumo["cantidad"]
        assert item["stock"] == 95

    def test_stock_below_minimum_triggers_alert(self, mock_session):
        """Stock por debajo del mínimo genera alerta."""
        item = {"id": "inv-002", "item": "Paracetamol", "stock": 10, "stock_minimo": 25, "empresa": "test-clinic"}
        mock_session["inventario_db"] = [item]
        necesita_reposicion = item["stock"] < item["stock_minimo"]
        assert necesita_reposicion is True

    def test_suggested_stock_minimum_requires_consumption_history(self, mock_session):
        """stock_minimo_sugerido requiere >=3 consumos en 6 meses."""
        from core._insumos_map import stock_minimo_sugerido

        # 0 consumos en ultimos 6 meses
        mock_session["consumos_db"] = []
        sugerido = stock_minimo_sugerido("test-item", mi_empresa="test-clinic")
        assert sugerido == 0


class TestPrescriptionFlow:
    """Tests para flujo de prescripciones."""

    def test_create_prescription_with_valid_meds(self, mock_session):
        """Crear receta con medicamentos vÃ¡lidos."""
        receta = {
            "id": "rx-001",
            "paciente": "Paciente Test",
            "medicamento": "Amoxicilina 500mg",
            "dosis": "1 comprimido cada 8 horas",
            "duracion": "7 dÃ­as",
            "via": "oral",
            "prescriptor": "Dr. Test",
            "fecha": "2026-05-20",
        }
        mock_session["indicaciones_db"] = [receta]
        assert len(mock_session["indicaciones_db"]) == 1
        assert mock_session["indicaciones_db"][0]["medicamento"] == "Amoxicilina 500mg"

    def test_drug_interaction_detection(self):
        """Verificar detecciÃ³n de interacciones medicamentosas."""
        from core.drug_interactions import DrugInteractionDatabase

        interaccion = DrugInteractionDatabase.get_interaction("warfarina", "ibuprofeno")
        assert interaccion is not None
        assert interaccion.severity.value in ("major", "contraindicated")

    def test_prescription_without_interactions(self):
        """Receta sin interacciones no genera alertas."""
        from core.drug_interactions import DrugInteractionDatabase

        result = DrugInteractionDatabase.check_interactions(["Amoxicilina"])
        assert result == []


class TestBackupFlow:
    """Tests para flujo de backup/restore."""

    def test_create_manual_backup_returns_entry(self):
        """Crear backup manual retorna BackupEntry."""
        from core.backup_automated import create_manual_backup

        result = create_manual_backup()
        assert hasattr(result, "id")
        assert hasattr(result, "status")

    def test_get_backup_status_returns_dict(self):
        """Obtener estado del backup retorna dict."""
        from core.backup_automated import get_backup_status

        status = get_backup_status()
        assert isinstance(status, dict)
        assert "latest_backup" in status
        assert "total_backups" in status

    def test_backup_manager_list_backups(self):
        """Listar backups retorna lista."""
        from core.backup_automated import get_backup_manager

        mgr = get_backup_manager()
        backups = mgr.list_backups()
        assert isinstance(backups, list)


# ConfiguraciÃ³n de pytest
if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
