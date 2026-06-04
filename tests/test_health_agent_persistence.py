"""Persistence wiring tests for Agente de Salud."""

from __future__ import annotations


def test_database_template_includes_health_agent_actions():
    from core.database import _estructura_vacia_por_clave

    data = _estructura_vacia_por_clave()

    assert "agente_salud_acciones_db" in data
    assert data["agente_salud_acciones_db"] == []


def test_database_keys_include_health_agent_actions():
    from core.database import _db_keys

    assert "agente_salud_acciones_db" in _db_keys()


def test_audit_event_type_has_health_agent_action():
    from core.audit_trail import AuditEventType

    assert AuditEventType.AGENT_ACTION.name == "AGENT_ACTION"
