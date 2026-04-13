from core.module_catalog import ALERTAS_APP_PACIENTE_MODULO
from core.view_registry import VIEW_CONFIG_BASE, VIEW_NAV_LABELS_BASE, build_view_maps
from core.view_roles import MODULO_ROLES_PERMITIDOS


def test_build_view_maps_respeta_flag_alertas():
    con_vc, con_vn = build_view_maps(alertas_app_visible=True)
    sin_vc, sin_vn = build_view_maps(alertas_app_visible=False)
    assert ALERTAS_APP_PACIENTE_MODULO in con_vc
    assert ALERTAS_APP_PACIENTE_MODULO in con_vn
    assert ALERTAS_APP_PACIENTE_MODULO not in sin_vc
    assert ALERTAS_APP_PACIENTE_MODULO not in sin_vn


def test_view_config_base_incluye_balance_y_visitas():
    assert "Balance" in VIEW_CONFIG_BASE
    assert VIEW_CONFIG_BASE["Balance"] == ("views.balance", "render_balance")


def test_modulo_roles_permitidos_alineado_a_view_registry():
    assert set(MODULO_ROLES_PERMITIDOS) == set(VIEW_CONFIG_BASE)


def test_etiquetas_navegacion_cubren_mismo_conjunto_que_vistas():
    assert set(VIEW_NAV_LABELS_BASE) == set(VIEW_CONFIG_BASE)


def test_build_view_maps_mantiene_paridad_config_y_etiquetas():
    for alertas in (True, False):
        vc, vn = build_view_maps(alertas_app_visible=alertas)
        assert set(vc) == set(vn)


def test_view_config_base_tuplas_modulo_y_render():
    for titulo, spec in VIEW_CONFIG_BASE.items():
        assert isinstance(spec, tuple) and len(spec) == 2, titulo
        mod, fn = spec
        assert isinstance(mod, str) and mod.startswith("views."), titulo
        assert isinstance(fn, str) and fn.startswith("render_"), titulo
        assert "." not in fn, titulo
