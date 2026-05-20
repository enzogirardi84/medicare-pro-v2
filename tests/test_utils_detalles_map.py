"""Acceso seguro al mapa de detalles de pacientes (session_state)."""


from __future__ import annotations

from core import utils
from core.email_2fa import SESSION_KEY as SESSION_KEY_2FA


def test_mapa_detalles_pacientes_tolerante():
    assert utils.mapa_detalles_pacientes({}) == {}
    assert utils.mapa_detalles_pacientes({"detalles_pacientes_db": None}) == {}
    assert utils.mapa_detalles_pacientes({"detalles_pacientes_db": []}) == {}
    assert utils.mapa_detalles_pacientes({"detalles_pacientes_db": {"a": {"dni": "1"}}}) == {"a": {"dni": "1"}}


def test_asegurar_detalles_pacientes_en_sesion():
    ss = {}
    m = utils.asegurar_detalles_pacientes_en_sesion(ss)
    assert m == {}
    assert ss["detalles_pacientes_db"] is m
    m["x"] = {"dni": "9"}
    assert ss["detalles_pacientes_db"]["x"]["dni"] == "9"


def test_session_key_2fa_valor_correcto():
    assert SESSION_KEY_2FA == "_mc_email_2fa"
