from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_boot_mobile_tiene_fallback_visible_y_sentinel_query_param():
    source = (ROOT / "main_medicare.py").read_text(encoding="utf-8")

    assert "mc-boot-fallback" in source
    assert "_mc_boot" in source
    assert 'href="?login=1&_mc_boot=1"' in source
    assert "Ingresar al sistema" in source
