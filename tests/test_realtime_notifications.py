"""Tests para core.realtime_notifications."""
from __future__ import annotations

import pytest


class TestRealtimeNotifications:
    """Tests para funciones públicas de core.realtime_notifications."""

    def test_realtime_notifications_importable(self):
        import core.realtime_notifications
        assert core.realtime_notifications is not None

    def test_functions_exist(self):
        import core.realtime_notifications
        assert callable(core.realtime_notifications.get_notification_manager)
        assert callable(core.realtime_notifications.send_critical_alert)
        assert callable(core.realtime_notifications.send_appointment_reminder)
        assert callable(core.realtime_notifications.send_team_message)
        assert callable(core.realtime_notifications.render_notification_badge)
        assert callable(core.realtime_notifications.to_dict)
        assert callable(core.realtime_notifications.create)
        assert callable(core.realtime_notifications.send_notification)
        assert callable(core.realtime_notifications.subscribe)
        assert callable(core.realtime_notifications.unsubscribe)
