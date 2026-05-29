"""Tests for views.pwa_manifest."""
from __future__ import annotations


def test_test_pwa_manifest_importable():
    import views.pwa_manifest
    assert views.pwa_manifest is not None


def test_pwa_manifest_opens_login_on_mobile_install():
    from views.pwa_manifest import generate_pwa_manifest

    manifest = generate_pwa_manifest()

    assert manifest["start_url"] == "/?login=1"
    assert all("?login=1" in item["url"] for item in manifest["shortcuts"])


def test_pwa_service_worker_never_caches_streamlit_navigation():
    from views.pwa_manifest import generate_service_worker

    sw = generate_service_worker()

    static_block = sw.split("const STATIC_ASSETS = [", 1)[1].split("];", 1)[0]
    assert "'/'" not in static_block
    assert 'request.mode === \'navigate\'' in sw
    assert "fetch(request).catch" in sw


def test_legacy_service_worker_bumps_cache_and_skips_navigation_cache():
    from core.service_worker import SW_SCRIPT

    assert 'CACHE_NAME = "medicare-cache-v2"' in SW_SCRIPT
    static_block = SW_SCRIPT.split("const STATIC_RESOURCES = [", 1)[1].split("];", 1)[0]
    assert '"/"' not in static_block
    assert 'event.request.mode === "navigate"' in SW_SCRIPT
