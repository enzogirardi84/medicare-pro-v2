from core.module_catalog import ALERTAS_APP_PACIENTE_MODULO
from core.view_registry import VIEW_CONFIG_BASE, build_view_maps
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
