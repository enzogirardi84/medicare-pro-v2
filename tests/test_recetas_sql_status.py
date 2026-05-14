from views.recetas import estado_recetas_sql, registrar_estado_recetas_sql


def test_estado_recetas_sql_registra_lectura_ok():
    ss = {}

    status = registrar_estado_recetas_sql(
        ss,
        ok=True,
        paciente="Ana Gomez - 111",
        indicaciones=4,
        administraciones=2,
    )

    assert estado_recetas_sql(ss) == status
    assert status == {
        "ok": True,
        "paciente": "Ana Gomez - 111",
        "indicaciones": 4,
        "administraciones": 2,
        "fallback": None,
    }


def test_estado_recetas_sql_registra_fallback_local_con_error_breve():
    ss = {}
    err = RuntimeError("fallo lectura indicaciones " * 20)

    status = registrar_estado_recetas_sql(
        ss,
        ok=False,
        paciente="Ana Gomez - 111",
        error=err,
    )

    assert estado_recetas_sql(ss) == status
    assert status["ok"] is False
    assert status["fallback"] == "local"
    assert status["error_type"] == "RuntimeError"
    assert len(status["error"]) == 180
