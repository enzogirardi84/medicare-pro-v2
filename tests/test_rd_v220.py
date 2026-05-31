"""Tests para módulos R&D v2.2.0 — SLM Edge, PQC, React Console, Cost Operator."""
from __future__ import annotations

import json
import time


class TestOfflineSLMEngine:
    def test_load_model(self):
        from core.edge_slm_engine import OfflineSLMEngine
        engine = OfflineSLMEngine()
        assert engine.load_model() is True
        assert engine._loaded is True

    def test_generate_soap_returns_note(self):
        from core.edge_slm_engine import OfflineSLMEngine
        engine = OfflineSLMEngine()
        engine.load_model()
        note = engine.generate_soap("Paciente con dolor de cabeza y fiebre de 38 grados")
        assert note.subjective != ""
        assert note.processing_time_ms > 0
        assert note.note_id is not None

    def test_soap_note_to_delta_payload(self):
        from core.edge_slm_engine import OfflineSLMEngine
        engine = OfflineSLMEngine()
        engine.load_model()
        note = engine.generate_soap("Tos seca y fatiga")
        payload = note.to_delta_payload()
        assert payload["tipo"] == "evolucion_soap"
        assert "soap" in payload
        assert payload["modelo"] == "phi-3-mini-4k-instruct-q4"

    def test_soap_validation_warnings(self):
        from core.edge_slm_engine import SOAPNote
        note = SOAPNote(subjective="Corto")
        warnings = note.validate()
        assert len(warnings) > 0

    def test_soap_validation_ok(self):
        from core.edge_slm_engine import SOAPNote
        note = SOAPNote(
            subjective="Paciente refiere dolor lumbar",
            objective="T° 37.5°C, PA 120/80",
            assessment="Lumbalgia mecánica",
            plan="AINES x 5 días, reposo 48h",
        )
        warnings = note.validate()
        assert len(warnings) == 0

    def test_delta_integrator(self):
        from core.edge_slm_engine import DeltaSOAPIntegrator
        integrator = DeltaSOAPIntegrator()
        note = integrator.process_voice_note("Dolor abdominal")
        assert note.note_id is not None
        packed = integrator.flush_to_msgpack()
        assert len(packed) > 0
        import msgpack
        data = msgpack.unpackb(packed, raw=False)
        assert data["tipo"] == "evoluciones_soap"

    def get_stats(self):
        from core.edge_slm_engine import OfflineSLMEngine
        engine = OfflineSLMEngine()
        engine.load_model()
        engine.generate_soap("test")
        stats = engine.get_stats()
        assert stats["model_loaded"] is True
        assert stats["inferences"] == 1


class TestPostQuantumCryptoEngine:
    def test_generate_ml_dsa_keypair(self):
        from core.pqc_hybrid_engine import PostQuantumCryptoEngine
        pqc = PostQuantumCryptoEngine()
        secret, public = pqc.generate_ml_dsa_keypair()
        assert len(secret) > 0
        assert len(public) > 0

    def test_generate_hybrid_keypair(self):
        from core.pqc_hybrid_engine import PostQuantumCryptoEngine
        pqc = PostQuantumCryptoEngine()
        kp = pqc.generate_hybrid_keypair()
        assert "ecdsa_private_pem" in kp
        assert "ml_dsa_secret" in kp
        assert "ml_dsa_public" in kp

    def test_sign_hybrid(self):
        from core.pqc_hybrid_engine import PostQuantumCryptoEngine
        pqc = PostQuantumCryptoEngine()
        kp = pqc.generate_hybrid_keypair()
        sig = pqc.sign_hybrid({"diagnostico": "neumonia"}, kp["ecdsa_private_pem"], kp["ml_dsa_secret"])
        assert sig.ecdsa_signature != ""
        assert sig.ml_dsa_signature != ""
        assert sig.scheme_version == "pqc-v1"

    def test_verify_hybrid_valid(self):
        from core.pqc_hybrid_engine import PostQuantumCryptoEngine
        pqc = PostQuantumCryptoEngine()
        kp = pqc.generate_hybrid_keypair()
        payload = {"diagnostico": "neumonia", "paciente_id": "p1"}
        sig = pqc.sign_hybrid(payload, kp["ecdsa_private_pem"], kp["ml_dsa_secret"])
        result = pqc.verify_hybrid(payload, sig)
        assert result["valid"] is True
        assert result["ecdsa"] is True

    def test_sign_hybrid_to_json(self):
        from core.pqc_hybrid_engine import PostQuantumCryptoEngine
        pqc = PostQuantumCryptoEngine()
        kp = pqc.generate_hybrid_keypair()
        sig = pqc.sign_hybrid({"test": "data"}, kp["ecdsa_private_pem"], kp["ml_dsa_secret"])
        j = sig.to_json()
        assert "ecdsa" in j
        assert "mldsa" in j

    def test_hybrid_column_sql(self):
        from core.pqc_hybrid_engine import PostQuantumCryptoEngine
        sql = PostQuantumCryptoEngine.get_hybrid_column_sql()
        assert "ALTER TABLE" in sql
        assert "hybrid_signature" in sql

    def test_migration_check_sql(self):
        from core.pqc_hybrid_engine import PostQuantumCryptoEngine
        sql = PostQuantumCryptoEngine.get_migration_check_sql()
        assert "clinical_event_store" in sql


class TestMedicareConsoleProxy:
    def test_import(self):
        from core.react_console_component import MedicareConsoleProxy, REACT_COMPONENT_SPEC
        assert MedicareConsoleProxy is not None
        assert "MedicareConsole" in REACT_COMPONENT_SPEC
        assert "WebSocket" in REACT_COMPONENT_SPEC
        assert "mapboxgl" in REACT_COMPONENT_SPEC
        assert "requestAnimationFrame" in REACT_COMPONENT_SPEC

    def test_component_not_built_fallback(self):
        from core.react_console_component import MedicareConsoleProxy
        proxy = MedicareConsoleProxy()
        assert proxy._component_available is False  # No hay build

    def test_streamlit_integration_code(self):
        from core.react_console_component import STREAMLIT_INTEGRATION_CODE
        assert "MedicareConsoleProxy" in STREAMLIT_INTEGRATION_CODE
        assert "WebSocket" in STREAMLIT_INTEGRATION_CODE


class TestCostAllocatorOperator:
    def test_import(self):
        from core.cost_allocator_operator import CostAllocatorSimulator, TenantCostDecision
        assert CostAllocatorSimulator is not None
        assert TenantCostDecision is not None

    def test_tenant_cost_decision_defaults(self):
        from core.cost_allocator_operator import TenantCostDecision
        d = TenantCostDecision(tenant_id="t1", estimated_cost_usd=50.0, is_unprofitable=False, p95_latency_ms=100)
        assert d.action == ""
        assert d.reason == ""

    def test_tenant_cost_decision_annotation(self):
        from core.cost_allocator_operator import TenantCostDecision
        d = TenantCostDecision(tenant_id="t1", estimated_cost_usd=150.0, is_unprofitable=True,
                                p95_latency_ms=200, action="evict_low_priority", reason="Costo elevado")
        ann = d.to_kubernetes_annotation()
        assert ann["medicare-pro/tenant-id"] == "t1"
        assert ann["medicare-pro/cost-decision"] == "evict_low_priority"

    def test_simulator_evaluate(self):
        from core.cost_allocator_operator import CostAllocatorSimulator
        sim = CostAllocatorSimulator()
        decisions = sim.get_decisions_summary()
        assert "total_tenants_evaluated" in decisions

    def test_kopf_operator_code(self):
        from core.cost_allocator_operator import KOPF_OPERATOR_CODE
        assert "kopf" in KOPF_OPERATOR_CODE
        assert "reconcile_cost" in KOPF_OPERATOR_CODE
        assert "handle_expensive_tenant" in KOPF_OPERATOR_CODE
        assert "handle_high_latency" in KOPF_OPERATOR_CODE
        assert "mutate_pod" in KOPF_OPERATOR_CODE
