from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_login_expone_marcador_css_para_layout_movil():
    source = (ROOT / "core" / "auth.py").read_text(encoding="utf-8")

    assert "mc-auth-page-marker" in source
