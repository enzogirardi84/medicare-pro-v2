"""Tests para core.self_healing."""
from __future__ import annotations

import pytest


class TestSelfHealing:
    """Tests para funciones públicas de core.self_healing."""

    def test_self_healing_importable(self):
        import core.self_healing
        assert core.self_healing is not None

    def test_functions_exist(self):
        import core.self_healing
        assert callable(core.self_healing.run_diagnostic_scan)
        assert callable(core.self_healing.maybe_run_self_healing)
        assert callable(core.self_healing.run_manual_scan)
        assert callable(core.self_healing.auto_fix_finding)
        assert callable(core.self_healing.rollback_fix)
        assert callable(core.self_healing.get_scan_history)
