from core.notificaciones_superiores import clasificar_inventario_alerta, _filtrar_por_fecha
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
