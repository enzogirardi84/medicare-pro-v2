from __future__ import annotations

from core.clinical_alerts import (
    AlertSeverity,
    AlertCategory,
    ClinicalAlert,
    AlertRule,
    ClinicalAlertEngine,
    get_alert_engine,
    check_vitals_alerts,
    check_labs_alerts,
    check_prescription_alerts,
)


def test_alert_severity_enum_values():
    assert AlertSeverity.CRITICAL.value == "critical"
    assert AlertSeverity.HIGH.value == "high"
    assert AlertSeverity.MEDIUM.value == "medium"
    assert AlertSeverity.LOW.value == "low"


def test_alert_category_enum_values():
    assert AlertCategory.VITALS_ABNORMAL.name == "VITALS_ABNORMAL"
    assert AlertCategory.LAB_CRITICAL.name == "LAB_CRITICAL"
    assert AlertCategory.SEPSIS_RISK.name == "SEPSIS_RISK"
    assert AlertCategory.DRUG_INTERACTION.name == "DRUG_INTERACTION"
    assert AlertCategory.DRUG_DOSAGE.name == "DRUG_DOSAGE"


def test_clinical_alert_dataclass():
    alert = ClinicalAlert(
        id="a1",
        patient_id="p1",
        patient_name="Test",
        severity="high",
        category="VITALS_ABNORMAL",
        title="Alerta",
        message="Mensaje",
        triggered_by="system",
        triggered_at="2024-01-01T00:00:00",
        rule_name="fever_high",
        relevant_data={},
    )
    assert alert.id == "a1"
    assert alert.acknowledged is False
    assert alert.resolved is False


def test_alert_rule_dataclass():
    rule = AlertRule(
        name="test_rule",
        category=AlertCategory.VITALS_ABNORMAL,
        severity=AlertSeverity.HIGH,
        description="Descripción",
        condition=lambda d: True,
        message_template="Test: {value}",
        suggestion="Sugerencia",
    )
    assert rule.name == "test_rule"
    assert rule.requires_ack is True
    assert rule.auto_notify is True
    assert callable(rule.condition)


def test_clinical_alert_engine_constructs():
    engine = ClinicalAlertEngine()
    assert len(engine._rules) > 0


def test_evaluate_vitals_returns_list():
    engine = ClinicalAlertEngine()
    result = engine.evaluate_vitals("p1", "Test", {"temperatura": 40})
    assert isinstance(result, list)


def test_evaluate_labs_returns_list():
    engine = ClinicalAlertEngine()
    result = engine.evaluate_labs("p1", "Test", {"glucosa": 30})
    assert isinstance(result, list)


def test_get_alert_engine_returns_singleton():
    e1 = get_alert_engine()
    e2 = get_alert_engine()
    assert e1 is e2


def test_helper_functions_exist():
    assert callable(check_vitals_alerts)
    assert callable(check_labs_alerts)
    assert callable(check_prescription_alerts)
