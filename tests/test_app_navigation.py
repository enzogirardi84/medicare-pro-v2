from unittest.mock import MagicMock, patch


def test_render_modulos_grid_desktop_usa_cuatro_columnas():
    from core import app_navigation

    app_navigation.st.session_state = {}
    app_navigation.st.columns = MagicMock(return_value=[MagicMock() for _ in range(4)])
    app_navigation.st.button = MagicMock()

    with patch("core.app_navigation.cliente_es_movil_probable", return_value=False):
        app_navigation.render_modulos_grid(
            ["Dashboard", "Visitas y Agenda", "Admision", "Caja", "Auditoria"],
            modulo_actual="Dashboard",
            view_nav_labels={},
        )

    assert app_navigation.st.columns.call_args_list[0].args[0] == 4
    assert app_navigation.st.columns.call_args_list[1].args[0] == 4
