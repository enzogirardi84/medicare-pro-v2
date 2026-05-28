"""Tests para core._db_sql_pacientes."""
from __future__ import annotations

import pytest


class TestDbSqlPacientes:
    """Tests para funciones públicas de core._db_sql_pacientes."""

    def test__db_sql_pacientes_importable(self):
        import core._db_sql_pacientes
        assert core._db_sql_pacientes is not None

    def test_functions_exist(self):
        import core._db_sql_pacientes
        assert callable(core._db_sql_pacientes.check_supabase_connection)
        assert callable(core._db_sql_pacientes.nombre_paciente_sql)
        assert callable(core._db_sql_pacientes.get_pacientes_by_empresa)
        assert callable(core._db_sql_pacientes.get_pacientes_globales)
        assert callable(core._db_sql_pacientes.get_paciente_by_id)
        assert callable(core._db_sql_pacientes.get_empresa_by_nombre)
        assert callable(core._db_sql_pacientes.get_paciente_by_dni_empresa)
        assert callable(core._db_sql_pacientes.upsert_paciente)
        assert callable(core._db_sql_pacientes.update_paciente_by_id)
        assert callable(core._db_sql_pacientes.delete_paciente_by_id)
