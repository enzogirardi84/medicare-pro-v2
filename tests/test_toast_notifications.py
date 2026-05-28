"""Tests para core.toast_notifications."""
from __future__ import annotations

import pytest


class TestToastNotifications:
    """Tests para funciones públicas de core.toast_notifications."""

    def test_toast_notifications_importable(self):
        import core.toast_notifications
        assert core.toast_notifications is not None

    def test_functions_exist(self):
        import core.toast_notifications
        assert callable(core.toast_notifications.get_toast_styles)
        assert callable(core.toast_notifications.generate_toast_html)
        assert callable(core.toast_notifications.inject_toast_css)
        assert callable(core.toast_notifications.show_toast)
        assert callable(core.toast_notifications.toast_success)
        assert callable(core.toast_notifications.toast_error)
        assert callable(core.toast_notifications.toast_warning)
        assert callable(core.toast_notifications.toast_info)
        assert callable(core.toast_notifications.queue_toast)
        assert callable(core.toast_notifications.render_queued_toasts)
