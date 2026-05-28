"""Tests para core.async_generators."""
from __future__ import annotations

import pytest


class TestAsyncGenerators:
    """Tests para funciones públicas de core.async_generators."""

    def test_async_generators_importable(self):
        import core.async_generators
        assert core.async_generators is not None

    def test_functions_exist(self):
        import core.async_generators
        assert callable(core.async_generators.get_task_manager)
        assert callable(core.async_generators.generate_pdf_background)
        assert callable(core.async_generators.generate_backup_background)
        assert callable(core.async_generators.generate_historia_clinica_pdf_background)
        assert callable(core.async_generators.export_excel_background)
        assert callable(core.async_generators.render_pending_tasks_dashboard)
        assert callable(core.async_generators.render_async_pdf_button)
        assert callable(core.async_generators.start)
        assert callable(core.async_generators.stop)
        assert callable(core.async_generators.submit)
