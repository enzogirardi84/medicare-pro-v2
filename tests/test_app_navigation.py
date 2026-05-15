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

    assert app_navigation.st.columns.call_args_list[0].args[0] == 3
    assert app_navigation.st.columns.call_args_list[1].args[0] == 3


def test_set_modulo_actual_preserva_modulo_anterior():
    from core import app_navigation

    app_navigation.st.session_state = {"modulo_actual": "Dashboard"}
    app_navigation.st.rerun = MagicMock()

    app_navigation.set_modulo_actual("Admision")

    assert app_navigation.st.session_state["modulo_actual"] == "Admision"
    assert app_navigation.st.session_state["modulo_anterior"] == "Dashboard"
    app_navigation.st.rerun.assert_not_called()


def test_set_modulo_actual_no_cambia_historial_si_es_el_mismo_modulo():
    from core import app_navigation

    app_navigation.st.session_state = {
        "modulo_actual": "Dashboard",
        "modulo_anterior": "Caja",
    }
    app_navigation.st.rerun = MagicMock()

    app_navigation.set_modulo_actual("Dashboard", rerun=True)

    assert app_navigation.st.session_state["modulo_actual"] == "Dashboard"
    assert app_navigation.st.session_state["modulo_anterior"] == "Caja"
    app_navigation.st.rerun.assert_not_called()


def test_procesar_query_params_navegacion_actualiza_historial_y_limpia_param():
    from core import app_navigation

    app_navigation.st.session_state = {"modulo_actual": "Dashboard"}
    app_navigation.st.query_params = {"modulo": "Admision"}
    app_navigation.st.rerun = MagicMock()

    app_navigation.procesar_query_params_navegacion({"Dashboard", "Admision"})

    assert app_navigation.st.session_state["modulo_actual"] == "Admision"
    assert app_navigation.st.session_state["modulo_anterior"] == "Dashboard"
    assert "modulo" not in app_navigation.st.query_params
    app_navigation.st.rerun.assert_called_once()
