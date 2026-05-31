"""Tests para core.edge_health_scoring — NEWS2 + ECDSA + offline queue."""
from __future__ import annotations


class TestNEWS2Scorer:
    def test_score_respiratory_rate_normal(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_respiratory_rate(16) == 0

    def test_score_respiratory_rate_bradypnea(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_respiratory_rate(6) == 3

    def test_score_respiratory_rate_tachypnea(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_respiratory_rate(26) == 3

    def test_score_oxygen_saturation_normal(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_oxygen_saturation(97, on_oxygen=False) == 0

    def test_score_oxygen_saturation_baja(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_oxygen_saturation(88, on_oxygen=False) == 3

    def test_score_oxygen_requirement_true(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_oxygen_requirement(True) == 2

    def test_score_oxygen_requirement_false(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_oxygen_requirement(False) == 0

    def test_score_systolic_bp_hypotension(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_systolic_bp(85) == 3

    def test_score_systolic_bp_normal(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_systolic_bp(120) == 0

    def test_score_heart_rate_bradycardia(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_heart_rate(35) == 3

    def test_score_heart_rate_normal(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_heart_rate(72) == 0

    def test_score_heart_rate_tachycardia(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_heart_rate(115) == 2

    def test_score_temperature_hipotermia(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_temperature(34.5) == 3

    def test_score_temperature_normal(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_temperature(37.0) == 0

    def test_score_temperature_fiebre(self):
        from core.edge_health_scoring import NEWS2Scorer
        assert NEWS2Scorer.score_temperature(38.5) == 1

    def test_score_consciousness_alert(self):
        from core.edge_health_scoring import NEWS2Scorer, Consciousness
        assert NEWS2Scorer.score_consciousness(Consciousness.ALERT) == 0

    def test_score_consciousness_not_alert(self):
        from core.edge_health_scoring import NEWS2Scorer, Consciousness
        assert NEWS2Scorer.score_consciousness(Consciousness.UNRESPONSIVE) == 3

    def test_calculate_full_score(self):
        from core.edge_health_scoring import NEWS2Scorer, VitalSigns, Consciousness
        vs = VitalSigns(
            respiratory_rate=26,
            oxygen_saturation=88,
            oxygen_therapy=False,
            systolic_bp=85,
            heart_rate=115,
            temperature=38.5,
            consciousness=Consciousness.ALERT,
        )
        result = NEWS2Scorer().calculate(vs)
        assert result["total"] >= 3
        assert "nivel" in result
        assert "recomendacion" in result

    def test_calculate_paciente_sano(self):
        from core.edge_health_scoring import NEWS2Scorer, VitalSigns
        vs = VitalSigns(
            respiratory_rate=16,
            oxygen_saturation=98,
            systolic_bp=120,
            heart_rate=72,
            temperature=36.5,
        )
        result = NEWS2Scorer().calculate(vs)
        assert result["total"] == 0
        assert result["nivel"] == "LEVE"


class TestClinicalTextScorer:
    def test_texto_vacio(self):
        from core.edge_health_scoring import ClinicalTextScorer
        result = ClinicalTextScorer.score_text("")
        assert result["score"] == 0

    def test_texto_sin_alertas(self):
        from core.edge_health_scoring import ClinicalTextScorer
        result = ClinicalTextScorer.score_text("Paciente en buen estado general")
        assert result["score"] == 0

    def test_texto_con_disnea(self):
        from core.edge_health_scoring import ClinicalTextScorer
        result = ClinicalTextScorer.score_text("El paciente presenta disnea severa")
        assert result["score"] >= 2

    def test_texto_con_alerta_critica(self):
        from core.edge_health_scoring import ClinicalTextScorer
        result = ClinicalTextScorer.score_text("Paciente inconsciente con convulsion y sepsis")
        assert result["score"] >= 6
        assert result["nivel"] == "ALTO"

    def test_texto_con_hemorragia(self):
        from core.edge_health_scoring import ClinicalTextScorer
        result = ClinicalTextScorer.score_text("Sangrado activo, hipotenso")
        assert result["score"] >= 3


class TestECDSASigner:
    def test_generate_keypair(self):
        from core.edge_health_scoring import ECDSASigner
        priv, pub = ECDSASigner.generate_keypair()
        assert priv.startswith(b"-----BEGIN PRIVATE KEY-----")
        assert pub.startswith(b"-----BEGIN PUBLIC KEY-----")

    def test_sign_and_verify(self):
        from core.edge_health_scoring import ECDSASigner
        priv, pub = ECDSASigner.generate_keypair()
        payload = {"alert_id": "a1", "score": 7, "paciente": "p1"}
        sig = ECDSASigner.sign_alert(priv, payload)
        assert ECDSASigner.verify_alert(pub, payload, sig) is True

    def test_verify_rechaza_firma_invalida(self):
        from core.edge_health_scoring import ECDSASigner
        priv, pub = ECDSASigner.generate_keypair()
        payload = {"score": 5}
        sig = ECDSASigner.sign_alert(priv, payload)
        assert ECDSASigner.verify_alert(pub, {"score": 999}, sig) is False

    def test_verify_rechaza_clave_incorrecta(self):
        from core.edge_health_scoring import ECDSASigner
        priv1, pub1 = ECDSASigner.generate_keypair()
        _, pub2 = ECDSASigner.generate_keypair()
        payload = {"data": "test"}
        sig = ECDSASigner.sign_alert(priv1, payload)
        assert ECDSASigner.verify_alert(pub2, payload, sig) is False


class TestSignedClinicalAlert:
    def test_alert_id_autogenerado(self):
        from core.edge_health_scoring import SignedClinicalAlert
        alert = SignedClinicalAlert()
        assert len(alert.alert_id) > 0

    def test_to_msgpack_ready_structure(self):
        from core.edge_health_scoring import SignedClinicalAlert
        alert = SignedClinicalAlert(paciente_id="p1", tenant_id="t1", news2_score=7)
        mp = alert.to_msgpack_ready()
        assert mp["tipo"] == "alerta_clinica"
        assert mp["version"] == 2
        assert mp["alerta"]["paciente_id"] == "p1"


class TestEdgeAlertEngine:
    def test_evaluate_genera_alerta(self):
        from core.edge_health_scoring import EdgeAlertEngine, VitalSigns
        engine = EdgeAlertEngine()
        vs = VitalSigns(respiratory_rate=26, oxygen_saturation=88, systolic_bp=85, heart_rate=115, temperature=38.5)
        alert = engine.evaluate("p1", "prof-1", "t1", "dev-1", vs)
        assert alert.paciente_id == "p1"
        assert alert.news2_score > 0
        assert alert.device_signature != ""
        assert alert.alert_id != ""

    def test_evaluate_con_nota(self):
        from core.edge_health_scoring import EdgeAlertEngine, VitalSigns
        engine = EdgeAlertEngine()
        vs = VitalSigns(respiratory_rate=16, oxygen_saturation=98, heart_rate=72, temperature=36.5)
        alert = engine.evaluate("p1", "prof-1", "t1", "dev-1", vs, nota_evolucion="Paciente con disnea y sepsis")
        assert alert.text_score >= 2

    def test_enqueue_and_flush(self):
        from core.edge_health_scoring import EdgeAlertEngine, VitalSigns
        engine = EdgeAlertEngine()
        vs = VitalSigns(respiratory_rate=16, oxygen_saturation=98, heart_rate=72, temperature=36.5)
        alert = engine.evaluate("p1", "prof-1", "t1", "dev-1", vs)
        engine.enqueue_alert(alert)
        engine.enqueue_alert(alert)
        flushed = engine.flush_queue()
        assert len(flushed) == 2
        assert engine.flush_queue() == []  # cola vacia

    def test_public_key_available(self):
        from core.edge_health_scoring import EdgeAlertEngine
        engine = EdgeAlertEngine()
        pk = engine.get_public_key_pem()
        assert pk.startswith("-----BEGIN PUBLIC KEY-----")


class TestPackageAlerts:
    def test_package_alerts_for_sync(self):
        from core.edge_health_scoring import (SignedClinicalAlert,
                                               package_alerts_for_sync)
        alert = SignedClinicalAlert(paciente_id="p1", news2_score=5)
        packed = package_alerts_for_sync([alert])
        import msgpack
        data = msgpack.unpackb(packed, raw=False)
        assert data["type"] == "health_scoring"
        assert len(data["alerts"]) == 1
