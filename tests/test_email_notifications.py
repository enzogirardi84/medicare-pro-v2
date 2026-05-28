"""Tests para core.email_notifications."""
from __future__ import annotations

import pytest


class TestEmailNotifications:
    """Tests para funciones públicas de core.email_notifications."""

    def test_email_notifications_importable(self):
        import core.email_notifications
        assert core.email_notifications is not None

    def test_functions_exist(self):
        import core.email_notifications
        assert callable(core.email_notifications.get_email_manager)
        assert callable(core.email_notifications.send_welcome_email)
        assert callable(core.email_notifications.send_password_reset)
        assert callable(core.email_notifications.send_appointment_reminder)
        assert callable(core.email_notifications.send_security_alert)
        assert callable(core.email_notifications.validate_email)
        assert callable(core.email_notifications.render_template)
        assert callable(core.email_notifications.send_email)
        assert callable(core.email_notifications.send_template_email)
        assert callable(core.email_notifications.queue_email)
