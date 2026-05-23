from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MOBILE_CSS = ROOT / "assets" / "mobile.css"


def test_mobile_css_no_merge_conflict_markers_or_debug_badge():
    css = MOBILE_CSS.read_text(encoding="utf-8")

    lines = css.splitlines()

    assert not any(line.startswith("<<<<<<<") for line in lines)
    assert not any(line.startswith("=======") for line in lines)
    assert not any(line.startswith(">>>>>>>") for line in lines)
    assert "Mobile fix activo" not in css


def test_mobile_css_keeps_touch_critical_rules():
    css = MOBILE_CSS.read_text(encoding="utf-8")

    required_snippets = [
        '@media screen and (max-width: 768px)',
        '[data-testid="stHorizontalBlock"]',
        '[data-testid="stDataEditor"]',
        'touch-action: pan-x pan-y',
        'div[data-baseweb="popover"]',
        'env(safe-area-inset-bottom)',
        '[data-testid="stFileUploader"]',
        '[data-testid="stPlotlyChart"]',
        '[data-testid="stSlider"]',
        '[data-testid="stTextInputRootElement"]',
        'div[data-testid="stForm"] [data-testid="stElementContainer"]',
        'stBaseButton-secondaryFormSubmit',
        'overflow-wrap: anywhere',
        '.mc-module-linkbar',
        '.mc-empty-mobile',
    ]

    for snippet in required_snippets:
        assert snippet in css
