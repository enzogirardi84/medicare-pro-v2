"""Tests para core._db_sql_operativo."""
from __future__ import annotations

import pytest


class TestDbSqlOperativo:
    """Tests para funciones públicas de core._db_sql_operativo."""

    def test__db_sql_operativo_importable(self):
        import core._db_sql_operativo
        assert core._db_sql_operativo is not None

    def test_functions_exist(self):
        import core._db_sql_operativo
        assert callable(core._db_sql_operativo.insert_auditoria)
        assert callable(core._db_sql_operativo.get_auditoria_by_empresa)
        assert callable(core._db_sql_operativo.get_turnos_by_empresa)
        assert callable(core._db_sql_operativo.insert_turno)
        assert callable(core._db_sql_operativo.update_estado_turno)
        assert callable(core._db_sql_operativo.get_administraciones_dia)
        assert callable(core._db_sql_operativo.get_administraciones_by_fecha)
        assert callable(core._db_sql_operativo.insert_administracion)
        assert callable(core._db_sql_operativo.get_emergencias_by_paciente)
        assert callable(core._db_sql_operativo.get_emergencias_by_empresa)
