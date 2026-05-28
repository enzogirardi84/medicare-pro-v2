"""Tests para core.workflow_engine."""
from __future__ import annotations

import pytest


class TestWorkflowEngine:
    """Tests para funciones públicas de core.workflow_engine."""

    def test_workflow_engine_importable(self):
        import core.workflow_engine
        assert core.workflow_engine is not None

    def test_functions_exist(self):
        import core.workflow_engine
        assert callable(core.workflow_engine.get_workflow_engine)
        assert callable(core.workflow_engine.can_start)
        assert callable(core.workflow_engine.is_overdue)
        assert callable(core.workflow_engine.get_current_task)
        assert callable(core.workflow_engine.get_progress_percentage)
        assert callable(core.workflow_engine.to_dict)
        assert callable(core.workflow_engine.get_template)
        assert callable(core.workflow_engine.list_templates)
        assert callable(core.workflow_engine.create_workflow)
        assert callable(core.workflow_engine.start_workflow)
