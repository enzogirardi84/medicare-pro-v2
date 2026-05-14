from views.estudios import estado_estudios_sql, registrar_estado_estudios_sql


def test_estado_estudios_sql_registra_lectura_ok():
    ss = {}

    status = registrar_estado_estudios_sql(
        ss,
        ok=True,
        paciente="Ana Gomez - 111",
        rows=3,
    )

    assert estado_estudios_sql(ss) == status
    assert status == {
        "ok": True,
        "paciente": "Ana Gomez - 111",
        "rows": 3,
        "fallback": None,
    }


def test_estado_estudios_sql_registra_fallback_local_con_error_breve():
    ss = {}
    err = ConnectionError("sin respuesta de supabase " * 20)

    status = registrar_estado_estudios_sql(
        ss,
        ok=False,
        paciente="Ana Gomez - 111",
        error=err,
    )

    assert estado_estudios_sql(ss) == status
    assert status["ok"] is False
    assert status["fallback"] == "local"
    assert status["error_type"] == "ConnectionError"
    assert len(status["error"]) == 180
