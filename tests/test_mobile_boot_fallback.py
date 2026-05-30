from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_boot_mobile_tiene_fallback_visible_y_sentinel_query_param():
    source = (ROOT / "main_medicare.py").read_text(encoding="utf-8")

    assert "_mc_boot" in source
    assert 'st.query_params.get("login")' in source
    assert "render_publicidad_y_detener" in source
    assert "st.stop()" in source
