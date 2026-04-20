"""Fachada de db_sql: re-exporta todas las funciones desde submódulos temáticos.

Submódulos:
  _db_sql_pacientes  — pacientes y empresas
  _db_sql_clinico    — evoluciones, indicaciones, estudios, vitales, cuidados,
                       consentimientos, pediatría, escalas
  _db_sql_operativo  — emergencias, auditoría, turnos, administraciones MAR,
                       inventario, facturación, balance, checkins
"""
from core._db_sql_pacientes import (
    check_supabase_connection,
    get_pacientes_by_empresa,
    get_paciente_by_id,
    get_empresa_by_nombre,
    get_paciente_by_dni_empresa,
    upsert_paciente,
    update_paciente_by_id,
    delete_paciente_by_id,
)
from core._db_sql_clinico import (
    get_evoluciones_by_paciente,
    insert_evolucion,
    get_indicaciones_activas,
    insert_indicacion,
    update_estado_indicacion,
    get_estudios_by_paciente,
    insert_estudio,
    delete_estudio,
    get_signos_vitales,
    insert_signo_vital,
    get_cuidados_enfermeria,
    insert_cuidado_enfermeria,
    get_consentimientos_by_paciente,
    insert_consentimiento,
    get_pediatria_by_paciente,
    insert_pediatria,
    get_escalas_by_paciente,
    insert_escala,
)
from core._db_sql_operativo import (
    insert_auditoria,
    get_auditoria_by_empresa,
    get_turnos_by_empresa,
    insert_turno,
    update_estado_turno,
    get_administraciones_dia,
    insert_administracion,
    get_emergencias_by_paciente,
    get_emergencias_by_empresa,
    insert_emergencia,
    update_estado_emergencia,
    get_inventario_by_empresa,
    insert_inventario,
    get_facturacion_by_empresa,
    insert_facturacion,
    get_balance_by_empresa,
    insert_balance,
    get_checkins_by_empresa,
    insert_checkin,
)

__all__ = [
    "check_supabase_connection",
    "get_pacientes_by_empresa", "get_paciente_by_id", "get_empresa_by_nombre",
    "get_paciente_by_dni_empresa", "upsert_paciente", "update_paciente_by_id", "delete_paciente_by_id",
    "get_evoluciones_by_paciente", "insert_evolucion",
    "get_indicaciones_activas", "insert_indicacion", "update_estado_indicacion",
    "get_estudios_by_paciente", "insert_estudio", "delete_estudio",
    "get_signos_vitales", "insert_signo_vital",
    "get_cuidados_enfermeria", "insert_cuidado_enfermeria",
    "get_consentimientos_by_paciente", "insert_consentimiento",
    "get_pediatria_by_paciente", "insert_pediatria",
    "get_escalas_by_paciente", "insert_escala",
    "insert_auditoria", "get_auditoria_by_empresa",
    "get_turnos_by_empresa", "insert_turno", "update_estado_turno",
    "get_administraciones_dia", "insert_administracion",
    "get_emergencias_by_paciente", "get_emergencias_by_empresa", "insert_emergencia", "update_estado_emergencia",
    "get_inventario_by_empresa", "insert_inventario",
    "get_facturacion_by_empresa", "insert_facturacion",
    "get_balance_by_empresa", "insert_balance",
    "get_checkins_by_empresa", "insert_checkin",
]
