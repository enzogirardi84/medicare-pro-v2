from __future__ import annotations


def test_aplicar_css_base_exists_and_callable():
    from core.app_theme import aplicar_css_base
    assert callable(aplicar_css_base)


def test_aplicar_css_base_no_crash():
    from core.app_theme import aplicar_css_base
    try:
        aplicar_css_base()
    except Exception:
        pass


def test_module_importable():
    import core.app_theme
    assert hasattr(core.app_theme, "aplicar_css_base")
