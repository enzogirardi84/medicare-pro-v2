from views._visitas_secciones import estado_checkins_sql, registrar_estado_checkins_sql


def test_estado_checkins_sql_registra_lectura_ok():
    ss = {}

    status = registrar_estado_checkins_sql(
        ss,
        ok=True,
        empresa="Clinica Demo",
        rows=8,
    )

    assert estado_checkins_sql(ss) == status
    assert status == {
        "ok": True,
        "empresa": "Clinica Demo",
        "rows": 8,
        "fallback": None,
    }


def test_estado_checkins_sql_registra_fallback_local_con_error_breve():
    ss = {}
    err = ConnectionError("checkins sin respuesta " * 20)

    status = registrar_estado_checkins_sql(
        ss,
        ok=False,
        empresa="Clinica Demo",
        error=err,
    )

    assert estado_checkins_sql(ss) == status
    assert status["ok"] is False
    assert status["fallback"] == "local"
    assert status["error_type"] == "ConnectionError"
    assert len(status["error"]) == 180
