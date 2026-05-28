"""Tests para core.service_worker."""
from __future__ import annotations

import pytest


class TestServiceWorker:
    """Tests para funciones públicas de core.service_worker."""

    def test_service_worker_importable(self):
        import core.service_worker
        assert core.service_worker is not None

    def test_functions_exist(self):
        import core.service_worker
        assert callable(core.service_worker.inject_service_worker)
