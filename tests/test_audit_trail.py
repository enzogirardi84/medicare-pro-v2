"""
Tests para el sistema de auditoría inmutable.

EJECUTAR:
    python -m pytest tests/test_audit_trail.py -v
"""

import pytest
import json
from datetime import datetime
from unittest.mock import Mock, patch


class TestAuditEntry:
    """Tests para AuditEntry"""
    
    def test_audit_entry_immutable(self):
        """Test que AuditEntry es inmutable"""
        from core.audit_trail import AuditEntry
        
        entry = AuditEntry(
            id="test-id",
            timestamp="2024-01-01T00:00:00Z",
            event_type="LOGIN_SUCCESS",
            event_category="auth",
            user_id="user1",
            user_role="admin",
            user_empresa="clinica1",
            session_id="session1",
            ip_address="127.0.0.1",
            user_agent="Mozilla/5.0",
            resource_type="user",
            resource_id="user1",
            action="LOGIN",
            description="Login exitoso",
            metadata={},
            previous_hash="0" * 64,
            entry_hash="abc123",
            signature="sig456"
        )
        
        # Intentar modificar debe fallar
        with pytest.raises(Exception):
            entry.user_id = "user2"


class TestAuditTrail:
    """Tests para AuditTrail"""
    
    def test_audit_trail_creation(self):
        """Test creación de AuditTrail"""
        from core.audit_trail import AuditTrail
        
        trail = AuditTrail(secret_key="test-secret")
        assert trail._secret == "test-secret"
        assert trail._last_hash == "0" * 64
    
    def test_log_creates_entry(self):
        """Test que log crea una entrada"""
        from core.audit_trail import AuditTrail, AuditEventType
        
        trail = AuditTrail(secret_key="test-secret")
        
        with patch.object(trail, '_persist_entry'):
            entry = trail.log(
                event_type=AuditEventType.LOGIN_SUCCESS,
                user_id="user1",
                resource_type="user",
                resource_id="user1",
                action="LOGIN",
                description="Login exitoso"
            )
        
        assert entry.event_type == "LOGIN_SUCCESS"
        assert entry.user_id == "user1"
        assert entry.entry_hash is not None
        assert entry.signature is not None
    
    def test_chain_integrity(self):
        """Test integridad de la cadena"""
        from core.audit_trail import AuditTrail, AuditEventType
        
        trail = AuditTrail(secret_key="test-secret")
        
        with patch.object(trail, '_persist_entry'):
            # Crear múltiples entradas
            trail.log(
                event_type=AuditEventType.LOGIN_SUCCESS,
                user_id="user1",
                resource_type="user",
                resource_id="user1",
                action="LOGIN",
                description="Login 1"
            )
            trail.log(
                event_type=AuditEventType.LOGIN_SUCCESS,
                user_id="user2",
                resource_type="user",
                resource_id="user2",
                action="LOGIN",
                description="Login 2"
            )
        
        # Verificar cadena
        assert len(trail._entries) == 2
        assert trail._entries[1].previous_hash == trail._entries[0].entry_hash
        assert trail.verify_chain() is True
    
    def test_tampering_detection(self):
        """Test detección de modificación"""
        from core.audit_trail import AuditTrail, AuditEntry, AuditEventType
        import dataclasses
        
        trail = AuditTrail(secret_key="test-secret")
        
        with patch.object(trail, '_persist_entry'):
            entry = trail.log(
                event_type=AuditEventType.LOGIN_SUCCESS,
                user_id="user1",
                resource_type="user",
                resource_id="user1",
                action="LOGIN",
                description="Login"
            )
        
        # Crear entrada modificada (simular tampering)
        tampered = dataclasses.replace(entry, user_id="attacker")
        
        # Verificación debe fallar
        assert trail._verify_entry(tampered) is False


class TestQueryAudit:
    """Tests para consultas de auditoría"""
    
    def test_query_by_event_type(self):
        """Test filtro por tipo de evento"""
        from core.audit_trail import AuditTrail, AuditEventType
        
        trail = AuditTrail(secret_key="test-secret")
        
        with patch.object(trail, '_persist_entry'):
            trail.log(AuditEventType.LOGIN_SUCCESS, "user1", "user", "u1", "LOGIN", "L1")
            trail.log(AuditEventType.LOGIN_FAILURE, "user2", "user", "u2", "LOGIN", "L2")
            trail.log(AuditEventType.LOGIN_SUCCESS, "user3", "user", "u3", "LOGIN", "L3")
        
        results = trail.query(event_type=AuditEventType.LOGIN_SUCCESS)
        
        assert len(results) == 2
        for r in results:
            assert r.event_type == "LOGIN_SUCCESS"
    
    def test_query_by_user(self):
        """Test filtro por usuario"""
        from core.audit_trail import AuditTrail, AuditEventType
        
        trail = AuditTrail(secret_key="test-secret")
        
        with patch.object(trail, '_persist_entry'):
            trail.log(AuditEventType.LOGIN_SUCCESS, "user1", "user", "u1", "LOGIN", "L1")
            trail.log(AuditEventType.LOGIN_SUCCESS, "user2", "user", "u2", "LOGIN", "L2")
        
        results = trail.query(user_id="user1")
        
        assert len(results) == 1
        assert results[0].user_id == "user1"
    
    def test_query_limit(self):
        """Test límite de resultados"""
        from core.audit_trail import AuditTrail, AuditEventType
        
        trail = AuditTrail(secret_key="test-secret")
        
        with patch.object(trail, '_persist_entry'):
            for i in range(150):
                trail.log(AuditEventType.LOGIN_SUCCESS, f"user{i}", "user", f"u{i}", "LOGIN", f"L{i}")
        
        results = trail.query(limit=50)
        
        assert len(results) == 50


class TestDataRetentionPolicy:
    """Tests para política de retención"""
    
    def test_retention_periods(self):
        """Test períodos de retención definidos"""
        from core.audit_trail import DataRetentionPolicy
        
        assert DataRetentionPolicy.get_retention_days("clinical_data") == 365 * 10
        assert DataRetentionPolicy.get_retention_days("audit_logs") == 365 * 7
        assert DataRetentionPolicy.get_retention_days("session_logs") == 90
    
    def test_should_delete(self):
        """Test detección de datos a eliminar"""
        from core.audit_trail import DataRetentionPolicy
        from datetime import datetime, timedelta
        
        old_date = datetime.utcnow() - timedelta(days=400)
        assert DataRetentionPolicy.should_delete("session_logs", old_date) is True
        
        recent_date = datetime.utcnow() - timedelta(days=30)
        assert DataRetentionPolicy.should_delete("session_logs", recent_date) is False
    
    def test_anonymize_patient_data(self):
        """Test anonimización de datos"""
        from core.audit_trail import DataRetentionPolicy
        
        patient_data = {
            "dni": "12345678",
            "nombre": "Juan",
            "apellido": "Pérez",
            "email": "juan@test.com",
            "edad": 35,
            "sexo": "M"
        }
        
        anonymized = DataRetentionPolicy.anonymize_patient_data(patient_data)
        
        assert anonymized["dni"] == "[REDACTED]"
        assert anonymized["nombre"] == "[REDACTED]"
        assert anonymized["edad"] == 35  # No sensible, se preserva
        assert anonymized["sexo"] == "M"


class TestGDPRCompliance:
    """Tests para cumplimiento GDPR/LGPD"""
    
    def test_check_gdpr_compliance(self):
        """Test verificación de consentimientos"""
        from core.audit_trail import check_gdpr_compliance
        
        consents = {
            "data_processing": True,
            "medical_records": True,
            "data_sharing": False,
            "marketing": False
        }
        
        result = check_gdpr_compliance(consents)
        
        assert result["data_processing"] is True
        assert result["medical_records"] is True
        assert result["data_sharing"] is False
        assert "marketing" in result
    
    def test_check_gdpr_missing_consents(self):
        """Test verificación con consentimientos faltantes"""
        from core.audit_trail import check_gdpr_compliance
        
        consents = {}  # Sin consentimientos
        
        result = check_gdpr_compliance(consents)
        
        # Todos deben ser False
        assert all(v is False for v in result.values())


class TestAuditExport:
    """Tests para exportación de auditoría"""
    
    def test_export_json_format(self):
        """Test exportación a JSON"""
        from core.audit_trail import AuditTrail, AuditEventType
        import json
        
        trail = AuditTrail(secret_key="test-secret")
        
        with patch.object(trail, '_persist_entry'):
            trail.log(
                event_type=AuditEventType.LOGIN_SUCCESS,
                user_id="user1",
                resource_type="user",
                resource_id="u1",
                action="LOGIN",
                description="Test login"
            )
        
        export = trail.export_for_compliance(
            start_date="2024-01-01",
            end_date="2024-12-31",
            format="json"
        )
        
        data = json.loads(export)
        assert len(data) == 1
        assert data[0]["event_type"] == "LOGIN_SUCCESS"
    
    def test_export_csv_format(self):
        """Test exportación a CSV"""
        from core.audit_trail import AuditTrail, AuditEventType
        
        trail = AuditTrail(secret_key="test-secret")
        
        with patch.object(trail, '_persist_entry'):
            trail.log(
                event_type=AuditEventType.LOGIN_SUCCESS,
                user_id="user1",
                resource_type="user",
                resource_id="u1",
                action="LOGIN",
                description="Test"
            )
        
        export = trail.export_for_compliance(
            start_date="2024-01-01",
            end_date="2024-12-31",
            format="csv"
        )
        
        lines = export.split("\n")
        assert len(lines) == 3  # Header + 1 data + empty
        assert "id,timestamp" in lines[0]
