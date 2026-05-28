"""Tests para views.pwa_manifest."""
from __future__ import annotations

import pytest


class TestPwaManifest:
    """Tests para funciones públicas de views.pwa_manifest."""

    def test_pwa_manifest_importable(self):
        import views.pwa_manifest
        assert views.pwa_manifest is not None

    def test_functions_exist(self):
        import views.pwa_manifest
        assert callable(views.pwa_manifest.generate_pwa_manifest)
        assert callable(views.pwa_manifest.generate_service_worker)
        assert callable(views.pwa_manifest.inject_pwa_headers)
        assert callable(views.pwa_manifest.save_pwa_files)
        assert callable(views.pwa_manifest.check_pwa_installability)
