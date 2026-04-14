from core.alert_toasts import firma_alertas_por_ids, firma_avisos_sistema, firma_inventario_alerta


def test_firma_alertas_vacia():
    assert firma_alertas_por_ids([]) == ""


def test_firma_alertas_orden_ids():
    a = firma_alertas_por_ids([{"id": "b"}, {"id": "a"}])
    b = firma_alertas_por_ids([{"id": "a"}, {"id": "b"}])
    assert a == b == "2:a|b"


def test_firma_inventario_estable():
    ag = [("Guantes", 0)]
    bj = [("Jeringa", 2)]
    assert firma_inventario_alerta(ag, bj) == firma_inventario_alerta(list(ag), list(bj))


def test_firma_avisos_sistema_vacia():
    assert firma_avisos_sistema([]) == ""
