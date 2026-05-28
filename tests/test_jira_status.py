"""Tests para core.jira_status."""
from __future__ import annotations

import pytest


class TestJiraStatus:
    """Tests para funciones públicas de core.jira_status."""

    def test_jira_status_importable(self):
        import core.jira_status
        assert core.jira_status is not None

    def test_functions_exist(self):
        import core.jira_status
        assert callable(core.jira_status.load_jira_config)
        assert callable(core.jira_status.fetch_jira_issues)
        assert callable(core.jira_status.jira_setup_hint)
