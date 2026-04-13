from core.module_catalog import categorias_navegacion_sidebar
from core.view_registry import VIEW_CONFIG_BASE


def test_categorias_solo_referencian_vistas_registradas():
    for alertas in (True, False):
        cats = categorias_navegacion_sidebar(alertas_app_visible=alertas)
        known = set(VIEW_CONFIG_BASE)
        for area, mods in cats.items():
            for m in mods:
                assert m in known, f"'{m}' en área '{area}' no está en VIEW_CONFIG_BASE"


def test_cada_modulo_aparece_en_una_sola_categoria():
    cats = categorias_navegacion_sidebar(alertas_app_visible=True)
    seen = set()
    for mods in cats.values():
        for m in mods:
            assert m not in seen, f"duplicado en categorías: {m}"
            seen.add(m)
