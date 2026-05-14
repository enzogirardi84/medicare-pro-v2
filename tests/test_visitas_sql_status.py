from views._visitas_agenda import estado_visitas_sql, registrar_estado_visitas_sql


def test_estado_visitas_sql_registra_lectura_ok():
    ss = {}

    status = registrar_estado_visitas_sql(
        ss,
        ok=True,
        empresa="Clinica Demo",
        rows=5,
    )

    assert estado_visitas_sql(ss) == status
    assert status == {
        "ok": True,
        "empresa": "Clinica Demo",
        "rows": 5,
        "fallback": None,
    }


def test_estado_visitas_sql_registra_fallback_local_con_error_breve():
    ss = {}
    err = TimeoutError("turnos sin respuesta " * 20)

    status = registrar_estado_visitas_sql(
        ss,
        ok=False,
        empresa="Clinica Demo",
        error=err,
    )

    assert estado_visitas_sql(ss) == status
    assert status["ok"] is False
    assert status["fallback"] == "local"
    assert status["error_type"] == "TimeoutError"
    assert len(status["error"]) == 180
