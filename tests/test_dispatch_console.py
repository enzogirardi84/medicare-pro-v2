"""Tests para core.dispatch_console — Actionable Dispatch."""
from __future__ import annotations

import asyncio


class TestAlertCard:
    def test_to_card_dict(self):
        from core.dispatch_console import AlertCard, AlertPriority, DispatchAction
        alert = AlertCard(
            priority=AlertPriority.CRITICAL,
            title="Paciente con NEWS2=9",
            patient_name="Juan Perez",
            news2_score=9,
            absent_probability=0.85,
            location_lat=-34.603,
            location_lon=-58.381,
            nearby_professionals=[{"id": "p2", "name": "Dr. Gomez", "distance": 1.2}],
            available_actions=[DispatchAction(label="Re-asignar enfermero", icon="🚀")],
        )
        card = alert.to_card_dict()
        assert card["priority"] == 4
        assert card["news2"] == 9
        assert card["absent_pct"] == 85.0
        assert len(card["nearby"]) == 1
        assert len(card["actions"]) == 1


class TestDispatchConsole:
    def test_add_alert(self):
        from core.dispatch_console import DispatchConsole, AlertCard
        console = DispatchConsole()
        alert = AlertCard(title="Test", patient_name="P1")
        console.add_alert(alert)
        assert console.get_console_stats()["total_alerts"] == 1

    def test_get_critical_alerts(self):
        from core.dispatch_console import DispatchConsole, AlertCard, AlertPriority
        console = DispatchConsole()
        console.add_alert(AlertCard(priority=AlertPriority.LOW, news2_score=2, patient_name="P1"))
        console.add_alert(AlertCard(priority=AlertPriority.CRITICAL, news2_score=9, patient_name="P2"))
        criticals = console.get_critical_alerts()
        assert len(criticals) == 1

    def test_get_high_absent_alerts(self):
        from core.dispatch_console import DispatchConsole, AlertCard
        console = DispatchConsole()
        console.add_alert(AlertCard(absent_probability=0.9, patient_name="P1"))
        console.add_alert(AlertCard(absent_probability=0.3, patient_name="P2"))
        high = console.get_high_absent_alerts(threshold=0.7)
        assert len(high) == 1

    def test_dispatch_action_no_alert(self):
        from core.dispatch_console import DispatchConsole
        console = DispatchConsole()
        result = asyncio.run(console.dispatch_action("action1", "nonexistent"))
        assert result["success"] is False

    def test_dispatch_action_success(self):
        from core.dispatch_console import DispatchConsole, AlertCard, DispatchAction
        console = DispatchConsole()
        action = DispatchAction(label="Test action", icon="🚀")
        alert = AlertCard(
            title="Test",
            patient_name="P1",
            available_actions=[action],
        )
        console.add_alert(alert)
        result = asyncio.run(console.dispatch_action(action.action_id, alert.alert_id))
        assert result["success"] is True
        assert result["action_label"] == "Test action"

    def test_dispatch_hook(self):
        from core.dispatch_console import DispatchConsole, AlertCard, DispatchAction
        console = DispatchConsole()
        hook_results = []

        def test_hook(action, alert):
            hook_results.append(action.label)
            return True

        console.add_dispatch_hook(test_hook)
        action = DispatchAction(label="Hook action")
        alert = AlertCard(title="Test", patient_name="P1", available_actions=[action])
        console.add_alert(alert)
        asyncio.run(console.dispatch_action(action.action_id, alert.alert_id))
        assert len(hook_results) == 1

    def test_get_dispatch_history(self):
        from core.dispatch_console import DispatchConsole, AlertCard, DispatchAction
        console = DispatchConsole()
        action = DispatchAction(label="Hist action")
        alert = AlertCard(title="T", patient_name="P", available_actions=[action])
        console.add_alert(alert)
        asyncio.run(console.dispatch_action(action.action_id, alert.alert_id))
        history = console.get_dispatch_history()
        assert len(history) == 1

    def test_get_console_stats(self):
        from core.dispatch_console import DispatchConsole
        console = DispatchConsole()
        stats = console.get_console_stats()
        assert "total_alerts" in stats
        assert "critical" in stats
