from __future__ import annotations

from core.drug_interactions import (
    DrugInteractionDatabase,
    DrugInteractionMonitor,
    InteractionSeverity,
    DrugInteraction,
    InteractionAlert,
    get_interaction_monitor,
)


def test_interaction_severity_enum_values():
    assert InteractionSeverity.CONTRAINDICATED.value == "contraindicated"
    assert InteractionSeverity.MAJOR.value == "major"
    assert InteractionSeverity.MODERATE.value == "moderate"
    assert InteractionSeverity.MINOR.value == "minor"
    assert InteractionSeverity.UNKNOWN.value == "unknown"


def test_drug_interaction_dataclass():
    entry = DrugInteraction(
        drug_a="warfarina",
        drug_b="ibuprofeno",
        severity=InteractionSeverity.MAJOR,
        description="Riesgo de sangrado",
    )
    assert entry.drug_a == "warfarina"
    assert entry.drug_b == "ibuprofeno"
    assert entry.severity == InteractionSeverity.MAJOR
    assert entry.alternative_drugs == []
    assert entry.references == []


def test_interaction_alert_dataclass():
    alert = InteractionAlert(
        id="alert-1",
        patient_id="p1",
        prescription_id="rx1",
        interaction=DrugInteraction(
            drug_a="a", drug_b="b", severity=InteractionSeverity.MINOR, description="test"
        ),
        triggered_at="2024-01-01T00:00:00",
    )
    assert alert.id == "alert-1"
    assert alert.acknowledged is False
    assert alert.acknowledged_by is None


def test_drug_interaction_database_get_interaction():
    result = DrugInteractionDatabase.get_interaction("warfarina", "ibuprofeno")
    assert result is not None
    assert result.severity == InteractionSeverity.MAJOR
    result_rev = DrugInteractionDatabase.get_interaction("ibuprofeno", "warfarina")
    assert result_rev is not None
    assert DrugInteractionDatabase.get_interaction("xxx", "yyy") is None


def test_check_interactions():
    results = DrugInteractionDatabase.check_interactions(["warfarina", "ibuprofeno", "enalapril"])
    assert len(results) > 0
    assert DrugInteractionDatabase.check_interactions([]) == []
    assert DrugInteractionDatabase.check_interactions(["warfarina"]) == []


def test_drug_interaction_monitor_constructs():
    monitor = DrugInteractionMonitor()
    assert monitor._alerts == {}
    assert monitor._dismissed_combinations == set()


def test_get_interaction_monitor_returns_singleton():
    m1 = get_interaction_monitor()
    m2 = get_interaction_monitor()
    assert m1 is m2
