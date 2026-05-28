"""Tests para core.i18n."""
from __future__ import annotations

import pytest


class TestI18N:
    """Tests para funciones públicas de core.i18n."""

    def test_i18n_importable(self):
        import core.i18n
        assert core.i18n is not None

    def test_functions_exist(self):
        import core.i18n
        assert callable(core.i18n.get_i18n)
        assert callable(core.i18n.set_locale)
        assert callable(core.i18n.render_language_selector)
        assert callable(core.i18n.init_i18n)
        assert callable(core.i18n.current_locale)
        assert callable(core.i18n.set_locale)
        assert callable(core.i18n.get_locale_from_session)
        assert callable(core.i18n.detect_browser_locale)
        assert callable(core.i18n.translate)
        assert callable(core.i18n.get_available_locales)
