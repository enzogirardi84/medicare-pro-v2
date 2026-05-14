from unittest.mock import MagicMock

from core.notificaciones_superiores import (
    _filtrar_por_fecha,
    _navegar_a_modulo_inventario,
    clasificar_inventario_alerta,
)
from datetime import date, timedelta


def test_clasificar_inventario_agotado_y_bajo():
    db = [
        {"item": "Guantes", "stock": 0, "empresa": "Clinica A"},
        {"item": "Agua", "stock": 3, "empresa": "Clinica A"},
        {"item": "Otro", "stock": 50, "empresa": "Clinica A"},
        {"item": "Externo", "stock": 0, "empresa": "Clinica B"},
    ]
    ag, bj = clasificar_inventario_alerta(db, "Clinica A", stock_bajo_max=10)
    assert [x[0] for x in ag] == ["Guantes"]
    assert [x[0] for x in bj] == ["Agua"]


def test_filtrar_avisos_por_fecha():
    hoy = date.today()
    ayer = hoy - timedelta(days=1)
    manana = hoy + timedelta(days=1)
    avisos = [
        {"texto": "viejo", "nivel": "info", "desde": None, "hasta": ayer},
        {"texto": "ok", "nivel": "info", "desde": None, "hasta": None},
        {"texto": "futuro", "nivel": "info", "desde": manana, "hasta": None},
    ]
    f = _filtrar_por_fecha(avisos)
    assert len(f) == 1
    assert f[0]["texto"] == "ok"


def test_navegar_a_modulo_inventario_preserva_modulo_anterior():
    from core import app_navigation
    from core import notificaciones_superiores

    app_navigation.st.session_state = {"modulo_actual": "Dashboard"}
    app_navigation.st.rerun = MagicMock()
    notificaciones_superiores.st.session_state = app_navigation.st.session_state

    _navegar_a_modulo_inventario()

    assert app_navigation.st.session_state["modulo_actual"] == "Inventario"
    assert app_navigation.st.session_state["modulo_anterior"] == "Dashboard"
    app_navigation.st.rerun.assert_not_called()
