import streamlit as st

from core import empresa_config
from core import nextgen_sync
from core import _db_sql_pacientes as db_sql_pacientes


class _EmptySecrets:
    def get(self, _key, default=""):
        return default


class _SecretsMap(dict):
    def get(self, key, default=""):
        return super().get(key, default)


def test_empresa_uuid_configurada_usa_default_si_no_hay_override(monkeypatch):
    monkeypatch.setattr(st, "secrets", _EmptySecrets())
    monkeypatch.delenv("EMPRESA_ID", raising=False)
    monkeypatch.delenv("DEFAULT_EMPRESA_ID", raising=False)
    monkeypatch.delenv("NEXTGEN_DEFAULT_EMPRESA_ID", raising=False)
    monkeypatch.delenv("empresa_id", raising=False)

    assert (
        empresa_config.empresa_uuid_configurada("Clinica Demo")
        == "15b42b80-83a4-41c4-82e0-23df2dec7497"
    )


def test_empresa_uuid_configurada_prioriza_secrets_sobre_env(monkeypatch):
    monkeypatch.setenv("EMPRESA_ID", "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    monkeypatch.setattr(
        st,
        "secrets",
        _SecretsMap({"EMPRESA_ID": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"}),
    )

    assert (
        empresa_config.empresa_uuid_configurada("Clinica Demo")
        == "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"
    )


def test_obtener_uuid_empresa_usa_fallback_configurado_si_no_hay_supabase(monkeypatch):
    monkeypatch.setattr(st, "session_state", {})
    monkeypatch.setattr(st, "secrets", _EmptySecrets())
    monkeypatch.setattr("core.database.supabase", None, raising=False)

    assert nextgen_sync._obtener_uuid_empresa("Clinica Demo") == "15b42b80-83a4-41c4-82e0-23df2dec7497"


def test_get_empresa_by_nombre_devuelve_registro_sintetico_si_no_hay_supabase(monkeypatch):
    monkeypatch.setattr(st, "session_state", {})
    monkeypatch.setattr(st, "secrets", _EmptySecrets())
    monkeypatch.setattr(db_sql_pacientes, "supabase", None)

    empresa = db_sql_pacientes.get_empresa_by_nombre("Clinica Demo")

    assert empresa == {
        "id": "15b42b80-83a4-41c4-82e0-23df2dec7497",
        "nombre": "Clinica Demo",
    }
