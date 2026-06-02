"""Tests for core.app_theme."""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_test_app_theme_importable():
    import core.app_theme
    assert core.app_theme is not None


def test_layout_compacto_final_keeps_sidebar_within_viewport():
    source = (ROOT / "core" / "app_theme.py").read_text(encoding="utf-8")

    assert "def aplicar_layout_compacto_final" in source
    assert "--mc-layout-sidebar-desktop: min(280px, 22vw)" in source
    assert "--mc-layout-sidebar-tablet: min(260px, 35vw)" in source
    assert "max-width: 100vw" in source
    assert "overflow-x: hidden" in source
    assert '[data-testid="stTabs"] [role="tablist"]' in source
    assert '[data-testid="stDataFrame"]' in source
    assert '[data-testid="stMetric"]' in source


def test_main_starts_with_expanded_sidebar_and_applies_final_layout():
    source = (ROOT / "main_medicare.py").read_text(encoding="utf-8")

    assert 'initial_sidebar_state="expanded"' in source
    assert "aplicar_layout_compacto_final()" in source
