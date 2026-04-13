from datetime import date, datetime

from features.historial.fechas import (
    fecha_registro_o_none,
    parse_registro_fecha_hora,
    registro_en_rango_fechas,
    sort_registros_por_fecha,
)


def test_parse_registro_fecha_hora_desde_fecha_y_hora():
    reg = {"fecha": "15/03/2026", "hora": "10:30"}
    dt = parse_registro_fecha_hora(reg)
    assert dt == datetime(2026, 3, 15, 10, 30)


def test_parse_registro_fecha_hora_iso():
    reg = {"fecha_evento": "2026-01-20 08:00:00"}
    dt = parse_registro_fecha_hora(reg)
    assert dt == datetime(2026, 1, 20, 8, 0, 0)


def test_fecha_registro_o_none():
    assert fecha_registro_o_none({}) is None
    assert fecha_registro_o_none({"fecha": "01/04/2026"}) == date(2026, 4, 1)


def test_registro_en_rango_fechas():
    reg = {"fecha": "10/06/2026"}
    d0 = date(2026, 6, 1)
    d1 = date(2026, 6, 30)
    assert registro_en_rango_fechas(reg, d0, d1, incluir_sin_fecha=False) is True
    assert registro_en_rango_fechas({}, d0, d1, incluir_sin_fecha=False) is False
    assert registro_en_rango_fechas({}, d0, d1, incluir_sin_fecha=True) is True


def test_sort_registros_por_fecha():
    a = {"fecha": "01/01/2026"}
    b = {"fecha": "03/01/2026"}
    c = {"fecha": "02/01/2026"}
    recientes = sort_registros_por_fecha([a, b, c], recientes_primero=True)
    assert recientes[0] == b
    antiguos = sort_registros_por_fecha([a, b, c], recientes_primero=False)
    assert antiguos[0] == a
