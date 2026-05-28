"""Tests para core._db_sql_clinico."""
from __future__ import annotations

import pytest


class TestDbSqlClinico:
    """Tests para funciones públicas de core._db_sql_clinico."""

    def test__db_sql_clinico_importable(self):
        import core._db_sql_clinico
        assert core._db_sql_clinico is not None

    def test_functions_exist(self):
        import core._db_sql_clinico
        assert callable(core._db_sql_clinico.get_evoluciones_by_paciente)
        assert callable(core._db_sql_clinico.insert_evolucion)
        assert callable(core._db_sql_clinico.get_indicaciones_activas)
        assert callable(core._db_sql_clinico.get_indicaciones_paciente)
        assert callable(core._db_sql_clinico.insert_indicacion)
        assert callable(core._db_sql_clinico.update_estado_indicacion)
        assert callable(core._db_sql_clinico.get_estudios_by_paciente)
        assert callable(core._db_sql_clinico.insert_estudio)
        assert callable(core._db_sql_clinico.delete_estudio)
        assert callable(core._db_sql_clinico.get_signos_vitales)
