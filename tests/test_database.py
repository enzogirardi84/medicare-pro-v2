"""Tests para core.database."""
from __future__ import annotations

import pytest


class TestDatabase:
    """Tests para funciones públicas de core.database."""

    def test_database_importable(self):
        import core.database
        assert core.database is not None

    def test_functions_exist(self):
        import core.database
        assert callable(core.database.with_auto_healing)
        assert callable(core.database.modo_shard_activo)
        assert callable(core.database.logins_monolito_allowlist)
        assert callable(core.database.login_usa_monolito_legacy)
        assert callable(core.database.tenant_key_normalizado)
        assert callable(core.database.sesion_usa_monolito_legacy)
        assert callable(core.database.completar_claves_db_session)
        assert callable(core.database.obtener_estado_guardado)
        assert callable(core.database.procesar_guardado_pendiente)
        assert callable(core.database.get_cache_size_estimate)
